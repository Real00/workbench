from dataclasses import asdict
from typing import Any

from openai import AsyncOpenAI

from ai_settings.domain import AISettingsDomainService
from ai_settings.ports import AIConnectionSettings
from shared.security import SecurityService, mask_secret


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
        client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        models = await client.models.list()
        return {"ok": True, "models": [item.id for item in models.data[:10]]}

    def _public(self, settings: Any) -> dict[str, Any]:
        data = asdict(settings)
        key = self.security.decrypt(data.pop("encrypted_api_key"))
        data["api_key_masked"] = mask_secret(key)
        return data
