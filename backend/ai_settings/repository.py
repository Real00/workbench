from dataclasses import asdict

from pymongo import AsyncMongoClient

from ai_settings.domain import AISettings, AISettingsRepository


class MongoAISettingsRepository(AISettingsRepository):
    def __init__(self, client: AsyncMongoClient, database: str):
        self.collection = client[database]["ai_settings"]

    async def get(self) -> AISettings | None:
        data = await self.collection.find_one({"_id": "global"})
        if not data:
            return None
        data.pop("_id")
        return AISettings(**data)

    async def save(self, settings: AISettings) -> None:
        await self.collection.replace_one(
            {"_id": "global"}, {"_id": "global", **asdict(settings)}, upsert=True
        )

    async def ensure_indexes(self) -> None:
        await self.collection.create_index("updated_at")
