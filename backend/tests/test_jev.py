import asyncio
from dataclasses import asdict
from unittest.mock import AsyncMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from pydantic import ValidationError
from pydantic_ai import CancellationToken, Tool
from pydantic_ai.exceptions import RunCancelled
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.test import TestModel

from ai_settings.application import AISettingsApplicationService
from ai_settings.domain import AISettings, AISettingsDomainService
from ai_settings.jev import JevConnectionSettings
from ai_settings.ports import AIConnectionSettings
from ai_settings.routes import register_routes
from api.http import auth_middleware, error_middleware
from progress.ai_tools import progress_ai_contribution
from pulse.agent import ALWAYS_AVAILABLE_TOOLS, PydanticPulseAgent, prepare_tools
from pulse.tool_router import preload_tools, routing_state
from shared.jev import evaluate_tools
from shared.security import SecurityService
from shared.web_keys import AI_SETTINGS, SECURITY
from tests.fakes import MemoryAISettingsRepository
from tests.test_ai import build_service


@pytest.fixture
def service():
    return AISettingsApplicationService(
        AISettingsDomainService(MemoryAISettingsRepository()),
        SecurityService("test-secret-with-at-least-32-characters", 60),
    )


MAIN = {"base_url": "https://example.test/v1", "model": "main", "api_key": "main-secret"}


async def test_settings_migrate_encrypt_preserve_replace_disable(service):
    await service.configure(MAIN)
    saved = await service.domain.get()
    legacy = asdict(saved)
    legacy.pop("jev")
    await service.domain.repository.save(AISettings(**legacy))
    assert (await service.get())["jev"]["enabled"] is False
    assert (await service.read_ai_settings()).jev is None

    public = await service.configure({**MAIN, "jev": {"enabled": True, "api_key": "jev-secret"}})
    assert "jev-secret" not in str(public)
    assert "encrypted_api_key" not in str(public)
    stored = (await service.domain.get()).jev
    assert stored["encrypted_api_key"] != "jev-secret"
    assert service.security.decrypt(stored["encrypted_api_key"]) == "jev-secret"
    # Returning masked settings must not mutate the stored secret.
    await service.get()
    await service.configure({"base_url": MAIN["base_url"], "model": "changed"})
    connection = await service.read_ai_settings()
    assert connection.api_key == "main-secret" and connection.jev.api_key == "jev-secret"
    await service.configure({**MAIN, "jev": {"api_key": "", "threshold": 0.9}})
    assert (await service.read_ai_settings()).jev.api_key == "jev-secret"
    await service.configure({**MAIN, "jev": {"api_key": "replacement"}})
    assert (await service.read_ai_settings()).jev.api_key == "replacement"
    await service.configure({**MAIN, "jev": {"enabled": False}})
    assert (await service.read_ai_settings()).jev is None
    await service.configure({**MAIN, "jev": {"enabled": True}})
    assert (await service.read_ai_settings()).jev.api_key == "replacement"


@pytest.mark.parametrize(
    "jev",
    [
        {"enabled": True},
        {"model": " "},
        {"base_url": "not-a-url"},
        {"base_url": "https://user:secret@example.test"},
        {"threshold": 1.1},
        {"threshold": float("nan")},
        {"timeout_seconds": 0},
    ],
)
async def test_invalid_configuration_is_not_saved(service, jev):
    await service.configure(MAIN)
    with pytest.raises((ValueError, ValidationError)):
        await service.configure({**MAIN, "jev": jev})
    assert (await service.domain.get()).jev is None


async def test_jev_http_contract_and_draft_test_does_not_save(service):
    calls = []

    async def handler(request):
        payload = await request.json()
        calls.append(payload)
        assert request.headers["Authorization"] == "Bearer jev-secret"
        assert payload["model"] == "jev-latest"
        assert payload["questions"]["create_task"]["type"] == "noul"
        assert "create_task" in str(payload["questions"]["create_task"]["instructions"])
        return web.json_response({"answers": {"create_task": {"type": "noul", "noul": 0.95}}})

    app = web.Application()
    app.router.add_post("/v1/systemone", handler)
    async with TestServer(app) as server:
        base_url = str(server.make_url("/v1"))
        # Connection tests work even before primary settings are saved.
        result = await service.test_jev_connection({"base_url": base_url, "api_key": "jev-secret"})
        assert result == {"ok": True, "model": "jev-latest"}
        assert await service.get() is None
        await service.configure({**MAIN, "jev": {"base_url": base_url, "api_key": "jev-secret"}})
        await service.test_jev_connection({})
        assert (await service.get())["jev"]["enabled"] is False
        assert len(calls) == 2


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"answers": None},
        {"answers": {"x": {"type": "choice", "noul": 1}}},
        {"answers": {"x": {"type": "noul", "noul": 1.1}}},
        {"answers": {"x": {"type": "noul", "noul": "0.9"}}},
        {"answers": {"x": {"type": "noul", "noul": True}}},
    ],
)
async def test_invalid_answers_are_rejected(payload):
    async def handler(request):
        return web.json_response(payload)

    app = web.Application()
    app.router.add_post("/systemone", handler)
    async with TestServer(app) as server:
        settings = JevConnectionSettings(str(server.make_url("/")), "jev-latest", "secret")
        with pytest.raises(ValueError, match="无效"):
            await evaluate_tools(settings, {"request": "test"}, {"x": "tool"})


@pytest.mark.parametrize("status", [401, 429, 529, 302])
async def test_http_errors_are_safe(status):
    async def handler(request):
        return web.Response(status=status, text="secret-body")

    app = web.Application()
    app.router.add_post("/systemone", handler)
    async with TestServer(app) as server:
        settings = JevConnectionSettings(str(server.make_url("/")), "jev-latest", "secret")
        with pytest.raises(ValueError, match=f"HTTP {status}") as error:
            await evaluate_tools(settings, {}, {"x": "tool"})
        assert "secret-body" not in str(error.value)


async def test_http_timeout():
    async def handler(request):
        await asyncio.sleep(0.2)
        return web.json_response({})

    app = web.Application()
    app.router.add_post("/systemone", handler)
    async with TestServer(app) as server:
        settings = JevConnectionSettings(
            str(server.make_url("/")),
            "jev-latest",
            "secret",
            timeout_seconds=0.01,
        )
        with pytest.raises(ValueError, match="超时"):
            await evaluate_tools(settings, {}, {"x": "tool"})


async def test_preloading_multitool_and_fallback(monkeypatch):
    contributions = [progress_ai_contribution()]
    evaluate = AsyncMock(
        return_value={"create_task": 0.99, "update_project": 0.85, "record_member_evaluation": 0.5}
    )
    monkeypatch.setattr("pulse.tool_router.evaluate_tools", evaluate)
    settings = JevConnectionSettings("https://example.test/v1", "jev-latest", "secret")
    assert await preload_tools(None, contributions, ALWAYS_AVAILABLE_TOOLS, "你好", []) == set()
    evaluate.assert_not_called()
    selected = await preload_tools(
        settings, contributions, ALWAYS_AVAILABLE_TOOLS, "创建任务并更新项目", []
    )
    assert selected == {"create_task", "update_project"}
    tools = prepare_tools(contributions, selected)
    by_name = {item.name if isinstance(item, Tool) else item.__name__: item for item in tools}
    assert not isinstance(by_name["create_task"], Tool)
    assert not isinstance(by_name["list_tasks"], Tool)
    assert by_name["record_member_evaluation"].defer_loading
    assert "list_tasks" not in evaluate.call_args.args[2]
    evaluate.return_value = {"create_task": 0.5}
    assert await preload_tools(settings, contributions, ALWAYS_AVAILABLE_TOOLS, "你好", []) == set()
    evaluate.side_effect = ValueError("service failed")
    assert (
        await preload_tools(settings, contributions, ALWAYS_AVAILABLE_TOOLS, "创建任务", [])
        == set()
    )
    evaluate.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await preload_tools(settings, contributions, ALWAYS_AVAILABLE_TOOLS, "创建任务", [])


def test_routing_history_includes_references_but_no_tool_results():
    from pydantic_ai.messages import ToolReturnPart

    state = routing_state(
        "继续",
        [
            ModelRequest(parts=[UserPromptPart(content="创建任务")]),
            ModelResponse(parts=[TextPart(content="还需要负责人")]),
            ModelRequest(
                parts=[ToolReturnPart(tool_name="list_tasks", content="private tool data")]
            ),
        ],
    )
    assert state["request"] == "继续"
    assert len(state["recent_messages"]) == 2
    assert "private tool data" not in str(state)


async def test_pulse_stream_uses_preloaded_tools_and_preserves_history(monkeypatch):
    from pulse.deps import AgentDeps

    _, progress, _, _ = await build_service()
    model = TestModel(custom_output_text="可以继续")
    monkeypatch.setattr("pulse.agent.ai_model", lambda _: model)
    router = AsyncMock(return_value={"create_task"})
    monkeypatch.setattr("pulse.agent.preload_tools", router)
    agent = PydanticPulseAgent([progress_ai_contribution()])
    settings = AIConnectionSettings("https://example.test/v1", "test", "secret")
    deps = AgentDeps(progress=progress)
    history = [
        ModelRequest(parts=[UserPromptPart(content="你好")]),
        ModelResponse(parts=[TextPart(content="你好")]),
    ]
    events = [
        event async for event in agent.stream("继续", deps, settings, message_history=history)
    ]
    assert any(event["type"] == "text" for event in events)
    assert model.last_model_request_parameters.visibility_of("create_task") == "visible"
    assert model.last_model_request_parameters.visibility_of("update_project") == "withheld"
    assert router.call_args.args[-1] == history
    assert deps.produced_messages[:2] == history
    token = CancellationToken()
    token.cancel()
    router.reset_mock()
    with pytest.raises(RunCancelled):
        _ = [event async for event in agent.stream("创建任务", deps, settings, token)]
    router.assert_not_called()


async def test_jev_api_requires_admin_and_validates_input(service):
    app = web.Application(middlewares=[error_middleware, auth_middleware])
    app[AI_SETTINGS] = service
    app[SECURITY] = service.security
    register_routes(app)
    path = "/api/v1/ai-settings/jev/test"
    async with TestClient(TestServer(app)) as client:
        assert (await client.post(path, json={})).status == 401
        member = {"Authorization": "Bearer " + service.security.issue_access_token("u", "member")}
        assert (await client.post(path, json={}, headers=member)).status == 403
        admin = {"Authorization": "Bearer " + service.security.issue_access_token("u", "admin")}
        assert (await client.post(path, json={"timeout_seconds": -1}, headers=admin)).status == 422
        assert (await client.post(path, json={}, headers=admin)).status == 400
        response = await client.put(
            "/api/v1/ai-settings",
            headers=admin,
            json={
                **MAIN,
                "jev": {"enabled": True, "api_key": "jev-secret"},
            },
        )
        assert response.status == 200
        assert "jev-secret" not in await response.text()


async def test_preloading_is_bounded_and_skips_long_requests(monkeypatch):
    contribution = progress_ai_contribution()
    candidates = [
        fn.__name__ for fn in contribution.tools if fn.__name__ not in ALWAYS_AVAILABLE_TOOLS
    ]
    evaluate = AsyncMock(return_value={name: 0.99 for name in candidates})
    monkeypatch.setattr("pulse.tool_router.evaluate_tools", evaluate)
    settings = JevConnectionSettings("https://example.test/v1", "jev-latest", "secret")
    selected = await preload_tools(settings, [contribution], ALWAYS_AVAILABLE_TOOLS, "整理项目", [])
    assert len(selected) == min(5, len(candidates))
    evaluate.reset_mock()
    assert (
        await preload_tools(settings, [contribution], ALWAYS_AVAILABLE_TOOLS, "字" * 12001, [])
        == set()
    )
    evaluate.assert_not_called()


async def test_legacy_timeout_is_capped_without_overwriting_other_settings(service):
    await service.configure({**MAIN, "jev": {"enabled": True, "api_key": "jev-secret"}})
    stored = await service.domain.get()
    stored.jev["timeout_seconds"] = 15
    assert (await service.get())["jev"]["timeout_seconds"] == 5
    assert (await service.read_ai_settings()).jev.timeout_seconds == 5
    await service.configure({**MAIN, "jev": {"threshold": 0.9}})
    assert (await service.get())["jev"]["timeout_seconds"] == 5
    assert (await service.read_ai_settings()).jev.api_key == "jev-secret"


async def test_hard_deadline_applies_even_to_legacy_connection(monkeypatch):
    from shared.jev import JevTimeoutError

    monkeypatch.setattr("shared.jev.JEV_MAX_TIMEOUT_SECONDS", 0.02)

    async def handler(request):
        await asyncio.sleep(0.1)
        return web.json_response({"answers": {"x": {"type": "noul", "noul": 0.99}}})

    app = web.Application()
    app.router.add_post("/systemone", handler)
    async with TestServer(app) as server:
        settings = JevConnectionSettings(
            str(server.make_url("/")), "jev-latest", "secret", timeout_seconds=15
        )
        with pytest.raises(JevTimeoutError):
            await evaluate_tools(settings, {}, {"x": "tool"})


@pytest.mark.parametrize("status", [408, 504])
async def test_upstream_timeouts_are_eligible_for_circuit_breaking(status):
    from shared.jev import JevTimeoutError

    async def handler(request):
        return web.Response(status=status)

    app = web.Application()
    app.router.add_post("/systemone", handler)
    async with TestServer(app) as server:
        settings = JevConnectionSettings(str(server.make_url("/")), "jev-latest", "secret")
        with pytest.raises(JevTimeoutError):
            await evaluate_tools(settings, {}, {"x": "tool"})
