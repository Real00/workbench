import re
from dataclasses import asdict, fields
from typing import Any

from pymongo import AsyncMongoClient

from knowledge.domain import KnowledgeDocument, KnowledgeEntry, KnowledgeTag


def _from_document(cls: type, data: dict[str, Any]) -> Any:
    allowed = {item.name for item in fields(cls)}
    payload = {key: data[key] for key in allowed if key in data}
    return cls(**payload)


class MongoTagRepository:
    def __init__(self, client: AsyncMongoClient, database: str):
        self.collection = client[database]["knowledge_tags"]

    async def save(self, tag: KnowledgeTag) -> None:
        await self.collection.replace_one({"id": tag.id}, asdict(tag), upsert=True)

    async def by_id(self, tag_id: str) -> KnowledgeTag | None:
        data = await self.collection.find_one({"id": tag_id}, {"_id": 0})
        return _from_document(KnowledgeTag, data) if data else None

    async def by_name(self, name: str) -> KnowledgeTag | None:
        data = await self.collection.find_one(
            {"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}, {"_id": 0}
        )
        return _from_document(KnowledgeTag, data) if data else None

    async def list(self) -> list[KnowledgeTag]:
        cursor = self.collection.find({}, {"_id": 0}).sort("name")
        return [_from_document(KnowledgeTag, row) async for row in cursor]

    async def delete(self, tag_id: str) -> bool:
        return (await self.collection.delete_one({"id": tag_id})).deleted_count > 0

    async def ensure_indexes(self) -> None:
        await self.collection.create_index("id", unique=True)
        await self.collection.create_index("name", unique=True)


class MongoEntryRepository:
    def __init__(self, client: AsyncMongoClient, database: str):
        self.collection = client[database]["knowledge_entries"]

    async def save(self, entry: KnowledgeEntry) -> None:
        await self.collection.replace_one({"id": entry.id}, asdict(entry), upsert=True)

    async def by_id(self, entry_id: str) -> KnowledgeEntry | None:
        data = await self.collection.find_one({"id": entry_id}, {"_id": 0})
        return _from_document(KnowledgeEntry, data) if data else None

    async def by_key(self, key: str) -> KnowledgeEntry | None:
        data = await self.collection.find_one(
            {"key": {"$regex": f"^{re.escape(key)}$", "$options": "i"}}, {"_id": 0}
        )
        return _from_document(KnowledgeEntry, data) if data else None

    async def list(self) -> list[KnowledgeEntry]:
        cursor = self.collection.find({}, {"_id": 0}).sort("key")
        return [_from_document(KnowledgeEntry, row) async for row in cursor]

    async def delete(self, entry_id: str) -> bool:
        return (await self.collection.delete_one({"id": entry_id})).deleted_count > 0

    async def ensure_indexes(self) -> None:
        await self.collection.create_index("id", unique=True)
        await self.collection.create_index("key", unique=True)


class MongoDocumentRepository:
    def __init__(self, client: AsyncMongoClient, database: str):
        self.collection = client[database]["knowledge_documents"]

    async def save(self, document: KnowledgeDocument) -> None:
        await self.collection.replace_one({"id": document.id}, asdict(document), upsert=True)

    async def by_id(self, document_id: str) -> KnowledgeDocument | None:
        data = await self.collection.find_one({"id": document_id}, {"_id": 0})
        return _from_document(KnowledgeDocument, data) if data else None

    async def list(self) -> list[KnowledgeDocument]:
        cursor = self.collection.find({}, {"_id": 0}).sort("title")
        return [_from_document(KnowledgeDocument, row) async for row in cursor]

    async def delete(self, document_id: str) -> bool:
        return (await self.collection.delete_one({"id": document_id})).deleted_count > 0

    async def ensure_indexes(self) -> None:
        await self.collection.create_index("id", unique=True)
