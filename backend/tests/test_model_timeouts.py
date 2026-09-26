
import httpx2
import pytest
from openai import APITimeoutError
from pydantic_ai.providers.openai import OpenAIProvider

from ai_settings.ports import AIConnectionSettings
from shared.model_errors import model_error_message
from shared.structured_llm import ai_model
from tests.test_ai import build_service


@pytest.mark.parametrize("base_url", ["https://api.openai.com/v1", "https://gateway.test/v1"])
async def test_timeout_budget_reaches_transport_and_retries_once(monkeypatch, base_url):
    attempts = []

    async def fail(request):
        attempts.append(request.extensions["timeout"])
        raise httpx2.ConnectTimeout("test timeout", request=request)

    async with httpx2.AsyncClient(transport=httpx2.MockTransport(fail)) as client:
        monkeypatch.setattr(
            "shared.structured_llm.OpenAIProvider",
            lambda **kwargs: OpenAIProvider(**kwargs, http_client=client),
        )
        model = ai_model(AIConnectionSettings(base_url, "test-model", "test-secret"))
        with pytest.raises(APITimeoutError) as error:
            await model.provider.client.models.list()
        assert len(attempts) == 2
        assert attempts == [{"connect": 20, "read": 90, "write": 30, "pool": 20}] * 2
        assert "连接主模型服务超时" in model_error_message(error.value)


@pytest.mark.parametrize("cause, expected", [
    (httpx2.ConnectTimeout, "连接主模型服务超时"),
    (httpx2.ReadTimeout, "主模型服务响应超时"),
    (httpx2.WriteTimeout, "主模型请求超时"),
])
def test_timeout_messages_describe_the_failure_phase(cause, expected):
    request = httpx2.Request("POST", "https://gateway.test/v1/chat/completions")
    error = APITimeoutError(request)
    error.__cause__ = cause("private upstream details", request=request)
    assert expected in model_error_message(error)
    assert "private" not in model_error_message(error)


async def test_timeout_after_partial_output_does_not_issue_confirmation(caplog):
    request = httpx2.Request("POST", "https://gateway.test/v1/chat/completions")

    class TimeoutAgent:
        async def stream(self, prompt, deps, *args, **kwargs):
            deps.pending.append({"op": "create_task", "changes": {"title": "private title"}})
            yield {"type": "text", "delta": "正在处理"}
            raise APITimeoutError(request) from httpx2.ReadTimeout("private details")

    service, _, _, _ = await build_service()
    service.agent = TimeoutAgent()
    events = [event async for event in service.stream("private user prompt")]
    assert [event["type"] for event in events] == ["text", "error"]
    assert "响应超时" in events[-1]["message"]
    assert all("confirmation_token" not in event for event in events)
    assert "ReadTimeout" in caplog.text
    assert "private" not in caplog.text
