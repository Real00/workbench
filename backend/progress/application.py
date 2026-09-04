from collections import Counter
from dataclasses import asdict
from datetime import date
from typing import Any

from progress.domain import ProgressDomainService, TaskResource, TeamMember
from progress.storage import ResourceStorage, StoredFile

DEFAULT_OPERATOR_NAMES = {"admin", "administrator"}
OPERATOR_TITLE = "工作台管理员"


def public_member(member: TeamMember) -> dict[str, Any]:
    data = asdict(member)
    data.pop("user_id", None)
    data["operator"] = bool(member.user_id)
    return data


def sorted_members(members: list[TeamMember]) -> list[TeamMember]:
    return sorted(members, key=lambda member: (not bool(member.user_id), member.name.casefold()))


def operator_member_name(display_name: str, username: str) -> str:
    label = display_name.strip() or username.strip()
    if label.casefold() in DEFAULT_OPERATOR_NAMES:
        return "管理员"
    return label


class ProgressApplicationService:
    def __init__(self, domain: ProgressDomainService, storage: ResourceStorage):
        self.domain = domain
        self.storage = storage

    async def initialize(self, operator: dict[str, Any] | None = None) -> None:
        await self.domain.ensure_indexes()
        if not operator:
            return
        await self.domain.ensure_operator(
            str(operator["id"]),
            operator_member_name(
                str(operator.get("display_name") or ""),
                str(operator.get("username") or ""),
            ),
            OPERATOR_TITLE,
        )

    async def create_task(self, data: dict[str, Any], actor_id: str) -> dict[str, Any]:
        return asdict(await self.domain.create(data, actor_id))

    async def get_task(self, task_id: str) -> dict[str, Any]:
        return asdict(await self.domain.get_task(task_id))

    async def list_tasks(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        return [asdict(task) for task in await self.domain.list_tasks(filters)]

    async def update_task(self, task_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return asdict(await self.domain.update(task_id, data))

    async def delete_task(self, task_id: str) -> None:
        task = await self.domain.delete_task(task_id)
        for resource in task.resources:
            if resource.storage_key:
                await self.storage.delete(resource.storage_key)

    async def attach_file(self, task_id: str, filename: str, data: bytes) -> dict[str, Any]:
        resource, suffix = TaskResource.create_file(filename, len(data))
        resource.storage_key = f"{task_id}/{resource.id}{suffix}"
        await self.storage.put(resource.storage_key, data)
        try:
            task = await self.domain.add_resource(task_id, resource)
        except Exception:
            await self.storage.delete(resource.storage_key)
            raise
        return asdict(task)

    async def attach_link(self, task_id: str, name: str, url: str) -> dict[str, Any]:
        resource = TaskResource.create_link(name, url)
        return asdict(await self.domain.add_resource(task_id, resource))

    async def detach_resource(self, task_id: str, resource_id: str) -> dict[str, Any]:
        task, removed = await self.domain.remove_resource(task_id, resource_id)
        if removed.storage_key:
            await self.storage.delete(removed.storage_key)
        return asdict(task)

    async def open_resource_file(self, task_id: str, resource_id: str) -> StoredFile:
        task = await self.domain.get_task(task_id)
        resource = task.resource_by_id(resource_id)
        if resource.kind == "link" or not resource.storage_key:
            raise ValueError("link resources have no file")
        path = self.storage.path_for(resource.storage_key)
        data = None if path else await self.storage.read(resource.storage_key)
        return StoredFile(
            content_type=resource.content_type,
            filename=resource.name,
            inline=resource.kind == "image",
            path=path,
            data=data,
        )

    async def create_member(self, data: dict[str, Any]) -> dict[str, Any]:
        return public_member(await self.domain.create_member(data))

    async def list_members(self) -> list[dict[str, Any]]:
        return [
            public_member(member)
            for member in sorted_members(await self.domain.list_members())
        ]

    async def update_member(self, member_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return public_member(await self.domain.update_member(member_id, data))

    async def add_member_evaluation(self, member_id: str, kind: str, content: str) -> dict[str, Any]:
        return public_member(await self.domain.add_member_evaluation(member_id, kind, content))

    async def remove_member_evaluation(self, member_id: str, evaluation_id: str) -> dict[str, Any]:
        return public_member(await self.domain.remove_member_evaluation(member_id, evaluation_id))

    async def delete_member(self, member_id: str) -> None:
        await self.domain.delete_member(member_id)

    async def create_project(self, data: dict[str, Any]) -> dict[str, Any]:
        return asdict(await self.domain.create_project(data))

    async def list_projects(self) -> list[dict[str, Any]]:
        return [asdict(project) for project in await self.domain.list_projects()]

    async def update_project(self, project_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return asdict(await self.domain.update_project(project_id, data))

    async def delete_project(self, project_id: str) -> None:
        await self.domain.delete_project(project_id)

    async def dashboard(self) -> dict[str, Any]:
        tasks = await self.domain.list_tasks({})
        members = sorted_members(await self.domain.list_members())
        statuses = Counter(task.status for task in tasks)
        priorities = Counter(task.priority for task in tasks)
        overdue = sum(
            1
            for task in tasks
            if task.due_date
            and task.due_date < date.today()
            and task.status not in {"done", "cancelled"}
        )
        workloads = []
        for member in members:
            current = [
                task
                for task in tasks
                if task.assignee_id == member.id and task.status not in {"done", "cancelled"}
            ]
            average = (
                round(sum(task.progress for task in current) / len(current), 1) if current else 0
            )
            remaining_hours = sum(
                (task.estimated_hours or 0) * (100 - task.progress) / 100 for task in current
            )
            risk = any(
                task.due_date and (task.due_date - date.today()).days <= 3 and task.progress < 100
                for task in current
            )
            workloads.append(
                {
                    "member": public_member(member),
                    "current_tasks": [asdict(task) for task in current],
                    "average_progress": average,
                    "estimated_remaining_days": round(remaining_hours / 8, 1),
                    "overdue_risk": risk,
                }
            )
        recent_pairs = [
            (
                entry.created_at,
                {
                    "task_id": task.id,
                    "task_title": task.title,
                    "kind": entry.kind,
                    "content": entry.content,
                    "created_at": entry.created_at,
                },
            )
            for task in tasks
            for entry in task.entries
        ]
        recent_pairs.sort(key=lambda item: item[0], reverse=True)
        return {
            "total": len(tasks),
            "by_status": dict(statuses),
            "by_priority": dict(priorities),
            "overdue": overdue,
            "member_workloads": workloads,
            "recent_progress": [item[1] for item in recent_pairs[:8]],
        }
