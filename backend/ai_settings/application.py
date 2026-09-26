import asyncio
from dataclasses import asdict
from typing import Any

from openai import APITimeoutError
from pydantic_ai import Agent
from pydantic_ai.exceptions import UnexpectedModelBehavior

from ai_settings.domain import AISettingsDomainService
from ai_settings.jev import JEV_MAX_TIMEOUT_SECONDS, JevConnectionSettings, JevInput, JevOptions
from ai_settings.ports import AIConnectionSettings
from shared.jev import evaluate_tools
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
        jev = current.jev if current else None
        if data.get("jev") is not None:
            jev = self._prepare_jev(data["jev"], jev)
        settings = await self.domain.configure(data["base_url"], data["model"], encrypted, jev)
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
            jev=self._jev_connection(settings.jev),
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
        except (UnexpectedModelBehavior, APITimeoutError) as exc:
            raise ValueError(model_error_message(exc)) from exc
        except TimeoutError as exc:
            raise ValueError("模型流式测试超时，请检查服务状态或稍后重试") from exc
        return {"ok": True, "model": model, "streaming": True}

    def _prepare_jev(
        self,
        data: dict[str, Any],
        current: dict[str, Any] | None,
    ) -> dict[str, Any]:
        values = dict(current or {})
        if "timeout_seconds" in values:
            values["timeout_seconds"] = min(values["timeout_seconds"], JEV_MAX_TIMEOUT_SECONDS)
        encrypted = values.pop("encrypted_api_key", "")
        values.update(data)
        draft = JevInput.model_validate(values)
        draft.validate_connection()
        if draft.api_key:
            encrypted = self.security.encrypt(draft.api_key)
        if draft.enabled and not encrypted:
            raise ValueError("启用 Jev 需要填写独立的 TypeSafe API Key")
        return {
            **draft.model_dump(exclude={"api_key"}),
            "base_url": draft.base_url.rstrip("/"),
            "encrypted_api_key": encrypted,
        }

    def _jev_connection(self, data: dict[str, Any] | None) -> JevConnectionSettings | None:
        if not data or not data.get("enabled"):
            return None
        return JevConnectionSettings(
            base_url=data["base_url"],
            model=data["model"],
            api_key=self.security.decrypt(data["encrypted_api_key"]),
            threshold=data["threshold"],
            timeout_seconds=min(data["timeout_seconds"], JEV_MAX_TIMEOUT_SECONDS),
        )

    async def test_jev_connection(self, override: dict[str, Any]) -> dict[str, Any]:
        current = await self.domain.get()
        data = self._prepare_jev({**override, "enabled": True}, current.jev if current else None)
        connection = self._jev_connection(data)
        assert connection is not None
        await evaluate_tools(
            connection,
            {"request": "创建一个任务"},
            {"create_task": "Create a task with a title."},
        )
        return {"ok": True, "model": connection.model}

    def _public(self, settings: Any) -> dict[str, Any]:
        data = asdict(settings)
        key = self.security.decrypt(data.pop("encrypted_api_key"))
        data["api_key_masked"] = mask_secret(key)
        jev = data.get("jev") or JevOptions().model_dump()
        jev["timeout_seconds"] = min(jev["timeout_seconds"], JEV_MAX_TIMEOUT_SECONDS)
        jev_key = jev.pop("encrypted_api_key", "")
        jev["api_key_masked"] = mask_secret(self.security.decrypt(jev_key)) if jev_key else ""
        data["jev"] = jev
        return data
