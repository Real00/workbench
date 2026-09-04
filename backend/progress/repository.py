import re
from dataclasses import asdict, fields
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

from pymongo import AsyncMongoClient

from progress.domain import (
    ENTRY_KINDS,
    EVALUATION_KINDS,
    RESOURCE_KINDS,
    MemberEvaluation,
    MemberRepository,
    ProgressEntry,
    Project,
    ProjectRepository,
    Task,
    TaskRepository,
    TaskResource,
    TeamMember,
    decode_unicode_text,
)


def task_document(task: Task) -> dict[str, Any]:
    data = asdict(task)
    for field in ("start_date", "due_date"):
        value = data[field]
        if isinstance(value, date) and not isinstance(value, datetime):
            data[field] = datetime.combine(value, datetime.min.time(), UTC)
    return data


def progress_entry_from_data(item: Any) -> ProgressEntry:
    if isinstance(item, ProgressEntry):
        return item
    created_at = item.get("created_at")
    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    if created_at is None:
        created_at = datetime.now(UTC)
    kind = item.get("kind") if item.get("kind") in ENTRY_KINDS else "update"
    return ProgressEntry(
        id=str(item.get("id") or uuid4()),
        kind=kind,
        content=str(item.get("content") or "").strip(),
        created_at=created_at,
    )


def member_evaluation_from_data(item: Any) -> MemberEvaluation:
    if isinstance(item, MemberEvaluation):
        return item
    created_at = item.get("created_at")
    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    if created_at is None:
        created_at = datetime.now(UTC)
    kind = item.get("kind") if item.get("kind") in EVALUATION_KINDS else "note"
    return MemberEvaluation(
        id=str(item.get("id") or uuid4()),
        kind=kind,
        content=str(item.get("content") or "").strip(),
        created_at=created_at,
    )


def task_resource_from_data(item: Any) -> TaskResource:
    if isinstance(item, TaskResource):
        return item
    created_at = item.get("created_at")
    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    if created_at is None:
        created_at = datetime.now(UTC)
    kind = item.get("kind") if item.get("kind") in RESOURCE_KINDS else "document"
    return TaskResource(
        id=str(item.get("id") or uuid4()),
        kind=kind,
        name=str(item.get("name") or "").strip() or "resource",
        content_type=str(item.get("content_type") or "application/octet-stream"),
        size_bytes=int(item.get("size_bytes") or 0),
        storage_key=item.get("storage_key") or None,
        url=item.get("url") or None,
        created_at=created_at,
    )


def task_from_document(data: dict[str, Any]) -> Task:
    payload = dict(data)
    for field in ("start_date", "due_date"):
        if isinstance(payload.get(field), datetime):
            payload[field] = payload[field].date()
    payload["entries"] = [
        progress_entry_from_data(item) for item in payload.get("entries") or []
    ]
    payload["resources"] = [
        task_resource_from_data(item) for item in payload.get("resources") or []
    ]
    payload["project_id"] = payload.get("project_id") or None
    allowed = {item.name for item in fields(Task)}
    return Task(**{key: payload[key] for key in allowed if key in payload})


class MongoTaskRepository(TaskRepository):
    def __init__(self, client: AsyncMongoClient, database: str):
        self.collection = client[database]["tasks"]

    async def save(self, task: Task) -> None:
        await self.collection.replace_one({"id": task.id}, task_document(task), upsert=True)

    async def by_id(self, task_id: str) -> Task | None:
        data = await self.collection.find_one({"id": task_id}, {"_id": 0})
        return task_from_document(data) if data else None

    async def list(self, filters: dict[str, Any]) -> list[Task]:
        query: dict[str, Any] = {}
        for key in ("status", "priority", "assignee_id"):
            if filters.get(key):
                query[key] = filters[key]
        if filters.get("tag"):
            query["tags"] = filters["tag"]
        if filters.get("q"):
            query["$or"] = [
                {"title": {"$regex": filters["q"], "$options": "i"}},
                {"description": {"$regex": filters["q"], "$options": "i"}},
            ]
        cursor = self.collection.find(query, {"_id": 0}).sort("updated_at", -1)
        return [task_from_document(row) async for row in cursor]

    async def delete(self, task_id: str) -> bool:
        return (await self.collection.delete_one({"id": task_id})).deleted_count > 0

    async def ensure_indexes(self) -> None:
        await self.collection.create_index("id", unique=True)
        await self.collection.create_index("status")
        await self.collection.create_index("assignee_id")
        await self.collection.create_index([("start_date", 1), ("due_date", 1)])


def member_from_document(data: dict[str, Any]) -> TeamMember:
    payload = dict(data)
    payload["name"] = decode_unicode_text(str(payload.get("name") or ""))
    payload["title"] = decode_unicode_text(str(payload.get("title") or ""))
    payload["skills"] = [
        decode_unicode_text(str(item)) for item in (payload.get("skills") or [])
    ]
    payload["background"] = decode_unicode_text(str(payload.get("background") or ""))
    payload["evaluations"] = [
        member_evaluation_from_data(item) for item in (payload.get("evaluations") or [])
    ]
    payload["user_id"] = payload.get("user_id") or None
    allowed = {item.name for item in fields(TeamMember)}
    return TeamMember(**{key: payload[key] for key in allowed if key in payload})


class MongoMemberRepository(MemberRepository):
    def __init__(self, client: AsyncMongoClient, database: str):
        self.collection = client[database]["members"]
    async def save(self, member: TeamMember) -> None:
        data = asdict(member)
        if not data.get("user_id"):
            data.pop("user_id", None)
        await self.collection.replace_one({"id": member.id}, data, upsert=True)

    async def by_id(self, member_id: str) -> TeamMember | None:
        data = await self.collection.find_one({"id": member_id}, {"_id": 0})
        return member_from_document(data) if data else None

    async def by_name(self, name: str) -> TeamMember | None:
        data = await self.collection.find_one(
            {"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}, {"_id": 0}
        )
        return member_from_document(data) if data else None

    async def by_user_id(self, user_id: str) -> TeamMember | None:
        data = await self.collection.find_one({"user_id": user_id}, {"_id": 0})
        return member_from_document(data) if data else None

    async def list(self) -> list[TeamMember]:
        cursor = self.collection.find({}, {"_id": 0}).sort("name")
        return [member_from_document(row) async for row in cursor]

    async def delete(self, member_id: str) -> bool:
        return (await self.collection.delete_one({"id": member_id})).deleted_count > 0

    async def ensure_indexes(self) -> None:
        await self.collection.create_index("id", unique=True)
        await self.collection.create_index("name", unique=True)
        await self.collection.create_index("user_id", unique=True, sparse=True)


def project_from_document(data: dict[str, Any]) -> Project:
    payload = dict(data)
    if isinstance(payload.get("started_at"), datetime):
        payload["started_at"] = payload["started_at"].date()
    allowed = {item.name for item in fields(Project)}
    return Project(**{key: payload[key] for key in allowed if key in payload})


class MongoProjectRepository(ProjectRepository):
    def __init__(self, client: AsyncMongoClient, database: str):
        self.collection = client[database]["projects"]

    async def save(self, project: Project) -> None:
        await self.collection.replace_one({"id": project.id}, asdict(project), upsert=True)

    async def by_id(self, project_id: str) -> Project | None:
        data = await self.collection.find_one({"id": project_id}, {"_id": 0})
        return project_from_document(data) if data else None

    async def by_name(self, name: str) -> Project | None:
        data = await self.collection.find_one(
            {"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}, {"_id": 0}
        )
        return project_from_document(data) if data else None

    async def list(self) -> list[Project]:
        cursor = self.collection.find({}, {"_id": 0}).sort("created_at", -1)
        return [project_from_document(row) async for row in cursor]

    async def delete(self, project_id: str) -> bool:
        return (await self.collection.delete_one({"id": project_id})).deleted_count > 0

    async def ensure_indexes(self) -> None:
        await self.collection.create_index("id", unique=True)
        await self.collection.create_index("name", unique=True)
