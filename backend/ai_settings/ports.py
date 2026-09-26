from dataclasses import dataclass
from typing import Protocol

from ai_settings.jev import JevConnectionSettings


@dataclass(frozen=True)
class AIConnectionSettings:
    base_url: str
    model: str
    api_key: str
    jev: JevConnectionSettings | None = None


class AISettingsReader(Protocol):
    async def read_ai_settings(self) -> AIConnectionSettings | None: ...
