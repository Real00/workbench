from __future__ import annotations

import re
from dataclasses import asdict, fields
from datetime import UTC, datetime
from typing import Any

from pymongo import ASCENDING, DESCENDING, AsyncMongoClient

from subscription.domain import Article, Plugin, Source


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _decode(cls: type, doc: dict[str, Any]) -> Any:
    allowed = {item.name for item in fields(cls)}
    data = {key: value for key, value in doc.items() if key in allowed}
    return cls(**data)


class MongoPluginRepository:
    def __init__(self, client: AsyncMongoClient[Any], database: str):
        self.collection = client[database]["subscription_plugins"]

    def decode(self, doc: dict[str, Any]) -> Plugin:
        plugin = _decode(Plugin, doc)
        plugin.created_at = _aware(plugin.created_at) or datetime.now(UTC)
        plugin.updated_at = _aware(plugin.updated_at) or plugin.created_at
        return plugin

    async def save(self, plugin: Plugin) -> None:
        await self.collection.replace_one({"id": plugin.id}, asdict(plugin), upsert=True)

    async def by_id(self, plugin_id: str) -> Plugin | None:
        doc = await self.collection.find_one({"id": plugin_id}, {"_id": 0})
        return None if doc is None else self.decode(doc)

    async def list(self) -> list[Plugin]:
        cursor = self.collection.find({}, {"_id": 0}).sort(
            [("builtin", DESCENDING), ("name", ASCENDING)]
        )
        return [self.decode(doc) async for doc in cursor]

    async def delete(self, plugin_id: str) -> bool:
        result = await self.collection.delete_one({"id": plugin_id})
        return result.deleted_count > 0

    async def ensure_indexes(self) -> None:
        await self.collection.create_index("id", unique=True)
        await self.collection.create_index("name")


class MongoSourceRepository:
    def __init__(self, client: AsyncMongoClient[Any], database: str):
        self.collection = client[database]["subscription_sources"]

    def decode(self, doc: dict[str, Any]) -> Source:
        source = _decode(Source, doc)
        source.created_at = _aware(source.created_at) or datetime.now(UTC)
        source.updated_at = _aware(source.updated_at) or source.created_at
        source.last_fetched_at = _aware(source.last_fetched_at)
        return source

    async def save(self, source: Source) -> None:
        await self.collection.replace_one({"id": source.id}, asdict(source), upsert=True)

    async def by_id(self, source_id: str) -> Source | None:
        doc = await self.collection.find_one({"id": source_id}, {"_id": 0})
        return None if doc is None else self.decode(doc)

    async def list(self) -> list[Source]:
        cursor = self.collection.find({}, {"_id": 0}).sort([("name", ASCENDING)])
        return [self.decode(doc) async for doc in cursor]

    async def delete(self, source_id: str) -> bool:
        result = await self.collection.delete_one({"id": source_id})
        return result.deleted_count > 0

    async def ensure_indexes(self) -> None:
        await self.collection.create_index("id", unique=True)
        await self.collection.create_index("plugin_id")
        await self.collection.create_index([("enabled", ASCENDING), ("last_fetched_at", ASCENDING)])


class MongoArticleRepository:
    def __init__(self, client: AsyncMongoClient[Any], database: str):
        self.collection = client[database]["subscription_articles"]

    def decode(self, doc: dict[str, Any]) -> Article:
        article = _decode(Article, doc)
        article.fetched_at = _aware(article.fetched_at) or datetime.now(UTC)
        article.published_at = _aware(article.published_at)
        return article

    async def upsert(self, article: Article) -> Article:
        existing = await self.collection.find_one(
            {"source_id": article.source_id, "external_id": article.external_id},
            {"_id": 0},
        )
        if existing is not None:
            merged = self.decode(existing).merge_from(article)
            await self.collection.replace_one({"id": merged.id}, asdict(merged), upsert=True)
            return merged
        await self.collection.replace_one({"id": article.id}, asdict(article), upsert=True)
        return article

    async def by_id(self, article_id: str) -> Article | None:
        doc = await self.collection.find_one({"id": article_id}, {"_id": 0})
        return None if doc is None else self.decode(doc)

    async def list(
        self,
        *,
        source_id: str | None = None,
        query: str = "",
        offset: int = 0,
        limit: int = 50,
    ) -> list[Article]:
        filters: dict[str, Any] = {}
        if source_id:
            filters["source_id"] = source_id
        if query:
            escaped = re.escape(query)
            filters["$or"] = [
                {"title": {"$regex": escaped, "$options": "i"}},
                {"author": {"$regex": escaped, "$options": "i"}},
                {"content": {"$regex": escaped, "$options": "i"}},
            ]
        cursor = (
            self.collection.find(filters, {"_id": 0})
            .sort([("published_at", DESCENDING), ("fetched_at", DESCENDING)])
            .skip(max(0, offset))
            .limit(min(max(1, limit), 100))
        )
        return [self.decode(doc) async for doc in cursor]

    async def delete_by_source(self, source_id: str) -> int:
        result = await self.collection.delete_many({"source_id": source_id})
        return int(result.deleted_count)

    async def ensure_indexes(self) -> None:
        await self.collection.create_index("id", unique=True)
        await self.collection.create_index(
            [("source_id", ASCENDING), ("external_id", ASCENDING)], unique=True
        )
        await self.collection.create_index([("published_at", DESCENDING)])
        await self.collection.create_index("title")
