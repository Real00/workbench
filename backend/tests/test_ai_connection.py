import json
from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from pydantic_ai.exceptions import UnexpectedModelBehavior

from ai_settings.application import AISettingsApplicationService
from ai_settings.domain import AISettingsDomainService
from shared.security import SecurityService
from tests.fakes import MemoryAISettingsRepository
from tests.test_ai import build_service


async def test_connection_checks_stream_and_reports_html_endpoint() -> None:
    requests: list[str] = []

    async def html(request: web.Request) -> web.Response:
        requests.append(request.path)
        return web.Response(text="<html>Gateway homepage</html>", content_type="text/html")

    async def stream(request: web.Request) -> web.Response:
        requests.append(request.path)
        payload = await request.json()
        assert payload["stream"] is True
        assert payload["model"] == "test-model"
        chunks = [
            {"index": 0, "delta": {"role": "assistant", "content": "OK"},
             "finish_reason": None},
            {"index": 0, "delta": {}, "finish_reason": "stop"},
        ]
        data = "".join("data: " + json.dumps({
            "id": "chat-test", "object": "chat.completion.chunk", "created": 1,
            "model": "test-model", "choices": [choice],
        }) + "\n\n" for choice in chunks)
        return web.Response(text=data + "data: [DONE]\n\n", content_type="text/event-stream")

    app = web.Application()
    app.router.add_post("/chat/completions", html)
    app.router.add_post("/v1/chat/completions", stream)
    server = TestServer(app)
    await server.start_server()
    security = SecurityService("test-secret-with-at-least-32-characters", 60)
    service = AISettingsApplicationService(
        AISettingsDomainService(MemoryAISettingsRepository()), security
    )
    try:
        root = str(server.make_url("/")).rstrip("/")
        await service.configure({"base_url": root, "model": "test-model", "api_key": "test"})
        with pytest.raises(ValueError, match="API 前缀"):
            await service.test_connection()
        result = await service.test_connection({"base_url": root + "/v1"})
        assert result == {"ok": True, "model": "test-model", "streaming": True}
        assert requests == ["/chat/completions", "/v1/chat/completions"]
        # Testing a draft connection must not replace saved settings.
        assert (await service.get())["base_url"] == root
    finally:
        await server.close()


async def test_pulse_empty_stream_is_actionable_and_never_confirms_pending_changes() -> None:
    class EmptyAgent:
        async def stream(self, *args: Any, **kwargs: Any):
            args[1].pending.append({"op": "create_task", "changes": {"title": "pending"}})
            raise UnexpectedModelBehavior("Streamed response ended without content or tool calls")
            yield  # pragma: no cover

    service, _, _, _ = await build_service()
    service.agent = EmptyAgent()
    events = [event async for event in service.stream("test")]
    assert len(events) == 1
    assert events[0]["type"] == "error"
    assert "API 前缀" in events[0]["message"]
    assert "confirmation_token" not in events[0]
