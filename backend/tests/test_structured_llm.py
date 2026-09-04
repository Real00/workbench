from pydantic_ai.models.openai import OpenAIChatModel, OpenAIResponsesModel

from ai_settings.ports import AIConnectionSettings
from shared.structured_llm import ai_model


def _settings(base_url: str, model: str = "test-model") -> AIConnectionSettings:
    return AIConnectionSettings(base_url=base_url, model=model, api_key="sk-test")


def test_openai_endpoint_keeps_responses_api() -> None:
    model = ai_model(_settings("https://api.openai.com/v1", "gpt-4.1"))
    assert isinstance(model, OpenAIResponsesModel)
    assert model.model_name == "gpt-4.1"


def test_compatible_provider_uses_chat_completions() -> None:
    for base_url in (
        "https://api.deepseek.com/v1",
        "https://api.moonshot.cn/v1",
        "https://openrouter.ai/api/v1",
    ):
        model = ai_model(_settings(base_url, "deepseek-chat"))
        assert isinstance(model, OpenAIChatModel), base_url
        assert model.model_name == "deepseek-chat"
