from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class AIConnectionSettings:
    base_url: str
    model: str
    api_key: str


class AISettingsReader(Protocol):
    async def read_ai_settings(self) -> AIConnectionSettings | None: ...
