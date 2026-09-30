from datetime import UTC, datetime
from typing import Any, Protocol

from pymongo import AsyncMongoClient

from ai_settings.skills import SkillInput


class SkillRecord:
    """存储层记录：application 负责翻译成运行时 SkillDefinition。"""

    def __init__(self, data: dict[str, Any]):
        self.id: str = str(data["_id"])
        self.name: str = data["name"]
        self.trigger: str = data["trigger"]
        self.instructions: str = data["instructions"]
        self.script: str | None = data.get("script")
        self.enabled: bool = bool(data.get("enabled", True))
        self.updated_at: datetime = data.get("updated_at") or datetime.now(UTC)

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "trigger": self.trigger,
            "instructions": self.instructions,
            "script": self.script,
            "enabled": self.enabled,
            "updated_at": self.updated_at,
        }


class SkillRepository(Protocol):
    async def list(self) -> list[SkillRecord]: ...
    async def get(self, skill_id: str) -> SkillRecord | None: ...
    async def create(self, data: SkillInput) -> SkillRecord: ...
    async def update(self, skill_id: str, data: dict[str, Any]) -> SkillRecord | None: ...
    async def delete(self, skill_id: str) -> bool: ...
    async def ensure_indexes(self) -> None: ...


class MongoSkillRepository:
    def __init__(self, client: AsyncMongoClient, database: str):
        self.collection = client[database]["ai_skills"]

    async def list(self) -> list[SkillRecord]:
        cursor = self.collection.find().sort("updated_at", 1)
        return [SkillRecord(item) async for item in cursor]

    async def get(self, skill_id: str) -> SkillRecord | None:
        from bson import ObjectId

        if not ObjectId.is_valid(skill_id):
            return None
        data = await self.collection.find_one({"_id": ObjectId(skill_id)})
        return SkillRecord(data) if data else None

    async def create(self, data: SkillInput) -> SkillRecord:
        now = datetime.now(UTC)
        inserted = await self.collection.insert_one(
            {"created_at": now, "updated_at": now, **data.model_dump()}
        )
        return await self.get(str(inserted.inserted_id))  # type: ignore[return-value]

    async def update(self, skill_id: str, changes: dict[str, Any]) -> SkillRecord | None:
        from bson import ObjectId

        if not ObjectId.is_valid(skill_id):
            return None
        await self.collection.update_one(
            {"_id": ObjectId(skill_id)},
            {"$set": {"updated_at": datetime.now(UTC), **changes}},
        )
        return await self.get(skill_id)

    async def delete(self, skill_id: str) -> bool:
        from bson import ObjectId

        if not ObjectId.is_valid(skill_id):
            return False
        return (await self.collection.delete_one({"_id": ObjectId(skill_id)})).deleted_count > 0

    async def ensure_indexes(self) -> None:
        await self.collection.create_index([("name", 1)], unique=True)
