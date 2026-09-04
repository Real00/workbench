from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol


@dataclass
class AISettings:
    base_url: str
    model: str
    encrypted_api_key: str
    updated_at: datetime

    @classmethod
    def create(cls, base_url: str, model: str, encrypted_api_key: str) -> "AISettings":
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("base_url must be http(s)")
        if not model.strip() or not encrypted_api_key:
            raise ValueError("model and api_key are required")
        return cls(base_url.rstrip("/"), model.strip(), encrypted_api_key, datetime.now(UTC))


class AISettingsRepository(Protocol):
    async def get(self) -> AISettings | None: ...
    async def save(self, settings: AISettings) -> None: ...
    async def ensure_indexes(self) -> None: ...


class AISettingsDomainService:
    def __init__(self, repository: AISettingsRepository):
        self.repository = repository

    async def configure(self, base_url: str, model: str, encrypted_api_key: str) -> AISettings:
        settings = AISettings.create(base_url, model, encrypted_api_key)
        await self.repository.save(settings)
        return settings

    async def get(self) -> AISettings | None:
        return await self.repository.get()

    async def ensure_indexes(self) -> None:
        await self.repository.ensure_indexes()
