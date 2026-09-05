from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID


@dataclass
class Capture:
    id: str
    owner_id: str
    content: str
    pinned: bool
    archived: bool
    created_at: datetime

    @classmethod
    def create(cls, ident: str, owner: str, content: str) -> "Capture":
        UUID(ident)
        text = content.strip()
        if not text or len(text) > 20000:
            raise ValueError("记录需包含 1 到 20000 个字符")
        return cls(ident, owner, text, False, False, datetime.now(UTC))


class CaptureRepository(Protocol):
    async def create(self, item: Capture) -> Capture: ...
    async def list(
        self, owner: str, query: str, archived: bool, offset: int
    ) -> list[Capture]: ...
    async def update(self, owner: str, ident: str, changes: dict[str, bool]) -> Capture: ...
