from dataclasses import asdict
from typing import Any

from capture.domain import Capture, CaptureRepository


class CaptureApplicationService:
    def __init__(self, repository: CaptureRepository):
        self.repository = repository

    async def create(self, owner: str, ident: str, content: str) -> dict[str, Any]:
        return asdict(await self.repository.create(Capture.create(ident, owner, content)))

    async def list(
        self, owner: str, query: str, archived: bool, offset: int
    ) -> list[dict[str, Any]]:
        return [asdict(item) for item in await self.repository.list(owner, query, archived, offset)]

    async def update(self, owner: str, ident: str, changes: dict[str, bool]) -> dict[str, Any]:
        if not changes or set(changes) - {"pinned", "archived"}:
            raise ValueError("请选择置顶或归档操作")
        return asdict(await self.repository.update(owner, ident, changes))
