from urllib.parse import urlparse

from openai import Timeout
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

from ai_settings.ports import AIConnectionSettings

_RESPONSES_API_HOSTS = {"api.openai.com", "chatgpt.com"}


def _provider(settings: AIConnectionSettings) -> OpenAIProvider:
    provider = OpenAIProvider(base_url=settings.base_url, api_key=settings.api_key)
    # The provider defaults to a 5s connection timeout, which is too short for
    # some compatible gateways. Bound each stage and retry the HTTP request once;
    # the Pulse application still limits the complete multi-step run to 240s.
    provider.client.timeout = Timeout(connect=20, read=90, write=30, pool=20)
    provider.client.max_retries = 1
    return provider


def openai_responses_model(settings: AIConnectionSettings) -> OpenAIResponsesModel:
    return OpenAIResponsesModel(
        settings.model,
        provider=_provider(settings),
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
        provider=_provider(settings),
    )
