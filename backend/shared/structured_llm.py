from urllib.parse import urlparse

from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

from ai_settings.ports import AIConnectionSettings

_RESPONSES_API_HOSTS = {"api.openai.com", "chatgpt.com"}


def openai_responses_model(settings: AIConnectionSettings) -> OpenAIResponsesModel:
    return OpenAIResponsesModel(
        settings.model,
        provider=OpenAIProvider(base_url=settings.base_url, api_key=settings.api_key),
    )


def _supports_responses_api(settings: AIConnectionSettings) -> bool:
    return (urlparse(settings.base_url).hostname or "") in _RESPONSES_API_HOSTS


def ai_model(settings: AIConnectionSettings) -> Model:
    """OpenAI keeps its proprietary Responses API; every other OpenAI-compatible
    provider (DeepSeek, Kimi, GLM, Qwen, OpenRouter, ...) speaks Chat Completions."""
    if _supports_responses_api(settings):
        return openai_responses_model(settings)
    return OpenAIChatModel(
        settings.model,
        provider=OpenAIProvider(base_url=settings.base_url, api_key=settings.api_key),
    )
