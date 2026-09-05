import asyncio
from dataclasses import asdict
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.exceptions import UnexpectedModelBehavior

from ai_settings.domain import AISettingsDomainService
from ai_settings.ports import AIConnectionSettings
from shared.model_errors import model_error_message
from shared.security import SecurityService, mask_secret
from shared.structured_llm import ai_model


class AISettingsApplicationService:
    def __init__(
        self,
        domain: AISettingsDomainService,
        security: SecurityService,
    ):
        self.domain = domain
        self.security = security

    async def initialize(self) -> None:
        await self.domain.ensure_indexes()

    async def configure(self, data: dict[str, Any]) -> dict[str, Any]:
        current = await self.domain.get()
        api_key = data.get("api_key")
        if not api_key and current:
            encrypted = current.encrypted_api_key
        elif api_key:
            encrypted = self.security.encrypt(api_key)
        else:
            raise ValueError("api_key is required")
        settings = await self.domain.configure(data["base_url"], data["model"], encrypted)
        return self._public(settings)

    async def get(self) -> dict[str, Any] | None:
        settings = await self.domain.get()
        return self._public(settings) if settings else None

    async def get_secret(self) -> dict[str, str]:
        settings = await self.domain.get()
        if not settings:
            raise LookupError("AI settings not configured")
        return {"api_key": self.security.decrypt(settings.encrypted_api_key)}

    async def read_ai_settings(self) -> AIConnectionSettings | None:
        settings = await self.domain.get()
        if not settings:
            return None
        return AIConnectionSettings(
            base_url=settings.base_url,
            model=settings.model,
            api_key=self.security.decrypt(settings.encrypted_api_key),
        )

    async def test_connection(self, override: dict[str, Any] | None = None) -> dict[str, Any]:
        settings = await self.domain.get()
        override = override or {}
        if not settings and not (override.get("api_key") and override.get("base_url")):
            raise LookupError("AI settings not configured")
        base_url = override.get("base_url") or (settings.base_url if settings else "")
        api_key = override.get("api_key") or self.security.decrypt(
            settings.encrypted_api_key if settings else ""
        )
        model = override.get("model") or (settings.model if settings else "")
        if not model.strip():
            raise ValueError("请填写要测试的模型名称")
        connection = AIConnectionSettings(base_url=base_url, model=model, api_key=api_key)
        agent = Agent(ai_model(connection), output_type=str)
        try:
            async with asyncio.timeout(45):
                async with agent.run_stream("Reply only OK.") as result:
                    output = await result.get_output()
                    if not output.strip():
                        raise ValueError("模型返回了空内容，请检查模型配置")
        except UnexpectedModelBehavior as exc:
            raise ValueError(model_error_message(exc)) from exc
        except TimeoutError as exc:
            raise ValueError("模型流式测试超时，请检查服务状态或稍后重试") from exc
        return {"ok": True, "model": model, "streaming": True}

    def _public(self, settings: Any) -> dict[str, Any]:
        data = asdict(settings)
        key = self.security.decrypt(data.pop("encrypted_api_key"))
        data["api_key_masked"] = mask_secret(key)
        return data
