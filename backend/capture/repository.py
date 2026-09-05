import re
from dataclasses import asdict
from datetime import UTC
from typing import Any

from pymongo import AsyncMongoClient, ReturnDocument

from capture.domain import Capture


class MongoCaptureRepository:
    def __init__(self, client: AsyncMongoClient[Any], database: str):
        self.collection = client[database]["captures"]

    @staticmethod
    def decode(doc: dict[str, Any]) -> Capture:
        item = Capture(**{key: value for key, value in doc.items() if key != "_id"})
        if item.created_at.tzinfo is None:
            item.created_at = item.created_at.replace(tzinfo=UTC)
        return item

    async def create(self, item: Capture) -> Capture:
        # A stable client ID makes retries after a lost response safe.
        key = f"{item.owner_id}:{item.id}"
        doc = await self.collection.find_one_and_update(
            {"_id": key}, {"$setOnInsert": asdict(item)},
            upsert=True, return_document=ReturnDocument.AFTER,
        )
        assert doc is not None
        result = self.decode(doc)
        if result.content != item.content:
            raise ValueError("该记录编号已被使用，请重新保存")
        return result

    async def list(
        self, owner: str, query: str, archived: bool, offset: int
    ) -> list[Capture]:
        filters: dict[str, Any] = {"owner_id": owner, "archived": archived}
        if query:
            filters["content"] = {"$regex": re.escape(query), "$options": "i"}
        cursor = self.collection.find(filters).sort(
            [("pinned", -1), ("created_at", -1), ("id", -1)]
        ).skip(offset).limit(50)
        return [self.decode(doc) async for doc in cursor]

    async def update(self, owner: str, ident: str, changes: dict[str, bool]) -> Capture:
        doc = await self.collection.find_one_and_update(
            {"_id": f"{owner}:{ident}"}, {"$set": changes},
            return_document=ReturnDocument.AFTER,
        )
        if doc is None:
            raise LookupError("记录不存在")
        return self.decode(doc)
