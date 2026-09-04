import re
from dataclasses import dataclass, field, fields, replace
from datetime import UTC, date, datetime
from typing import Any, Protocol
from urllib.parse import urlparse
from uuid import uuid4

STATUSES = {"todo", "in_progress", "done", "cancelled"}
PRIORITIES = {"low", "medium", "high", "urgent"}
ENTRY_KINDS = {"update", "blocker", "extra_work"}
RESOURCE_KINDS = {"image", "document", "link"}
MAX_RESOURCES = 40
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_MEMBER_SKILLS = 20
MAX_SKILL_LENGTH = 40
MAX_BACKGROUND_LENGTH = 2000
EVALUATION_KINDS = {"highlight", "risk", "note"}
MAX_EVALUATION_LENGTH = 2000
MAX_MEMBER_EVALUATIONS = 200
MAX_PROJECT_NAME_LENGTH = 200
MAX_PROJECT_DESCRIPTION_LENGTH = 5000
MAX_PROJECT_BACKGROUND_LENGTH = 2000
MAX_PROJECT_MEMBERS = 50
PROJECT_STATUSES = {"planning", "active", "completed", "archived"}
_UNICODE_ESCAPE = re.compile(r"\\u[0-9a-fA-F]{4}", re.I)


def decode_unicode_text(value: str) -> str:
    """Decode literal \\uXXXX sequences models sometimes emit as plain text."""
    if not value or not _UNICODE_ESCAPE.search(value):
        return value
    try:
        return _UNICODE_ESCAPE.sub(lambda match: chr(int(match.group(0)[2:], 16)), value)
    except ValueError:
        return value


IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
DOCUMENT_TYPES = {
    ".pdf": "application/pdf",
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


@dataclass
class ProgressEntry:
    id: str
    kind: str
    content: str
    created_at: datetime

    @classmethod
    def create(cls, kind: str, content: str) -> "ProgressEntry":
        if kind not in ENTRY_KINDS:
            raise ValueError("invalid progress entry kind")
        text = content.strip()
        if not text:
            raise ValueError("progress entry content is required")
        return cls(str(uuid4()), kind, text, datetime.now(UTC))


@dataclass
class MemberEvaluation:
    id: str
    kind: str
    content: str
    created_at: datetime

    @classmethod
    def create(cls, kind: str, content: str) -> "MemberEvaluation":
        if kind not in EVALUATION_KINDS:
            raise ValueError("invalid member evaluation kind")
        text = decode_unicode_text(str(content or "")).strip()
        if not text:
            raise ValueError("member evaluation content is required")
        if len(text) > MAX_EVALUATION_LENGTH:
            raise ValueError("member evaluation is too long")
        return cls(str(uuid4()), kind, text, datetime.now(UTC))


def classify_upload(filename: str) -> tuple[str, str, str]:
    name = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not name:
        raise ValueError("filename is required")
    suffix = f".{name.rsplit('.', 1)[-1].lower()}" if "." in name else ""
    if suffix in IMAGE_TYPES:
        return "image", IMAGE_TYPES[suffix], suffix
    if suffix in DOCUMENT_TYPES:
        return "document", DOCUMENT_TYPES[suffix], suffix
    raise ValueError("unsupported resource type")


def display_filename(filename: str) -> str:
    name = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not name:
        raise ValueError("filename is required")
    return name[:200]


@dataclass
class TaskResource:
    id: str
    kind: str
    name: str
    content_type: str
    size_bytes: int
    storage_key: str | None
    url: str | None
    created_at: datetime

    @classmethod
    def create_file(cls, filename: str, size_bytes: int) -> tuple["TaskResource", str]:
        if size_bytes <= 0:
            raise ValueError("file is empty")
        if size_bytes > MAX_FILE_BYTES:
            raise ValueError("file exceeds 20MB limit")
        kind, content_type, suffix = classify_upload(filename)
        resource_id = str(uuid4())
        return (
            cls(
                resource_id,
                kind,
                display_filename(filename),
                content_type,
                size_bytes,
                None,
                None,
                datetime.now(UTC),
            ),
            suffix,
        )

    @classmethod
    def create_link(cls, name: str, url: str) -> "TaskResource":
        parsed = urlparse(url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("resource url must be http or https")
        title = name.strip() or parsed.netloc
        if not title:
            raise ValueError("resource name is required")
        return cls(
            str(uuid4()),
            "link",
            title[:200],
            "text/uri-list",
            0,
            None,
            parsed.geturl(),
            datetime.now(UTC),
        )


@dataclass
class Task:
    id: str
    title: str
    description: str
    status: str
    priority: str
    assignee_id: str | None
    project_id: str | None
    start_date: date | None
    due_date: date | None
    progress: int
    estimated_hours: float | None
    tags: list[str]
    entries: list[ProgressEntry]
    resources: list[TaskResource]
    created_by: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(cls, data: dict[str, Any], created_by: str) -> "Task":
        now = datetime.now(UTC)
        task = cls(
            id=str(uuid4()),
            title="",
            description="",
            status="todo",
            priority="medium",
            assignee_id=None,
            project_id=None,
            start_date=None,
            due_date=None,
            progress=0,
            estimated_hours=None,
            tags=[],
            entries=[],
            resources=[],
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        task.update(data)
        if not task.title:
            raise ValueError("title is required")
        return task

    def update(self, data: dict[str, Any]) -> None:
        if "title" in data:
            title = str(data["title"]).strip()
            if not title:
                raise ValueError("title is required")
            self.title = title
        if "description" in data:
            self.description = str(data["description"]).strip()
        if "status" in data:
            self.change_status(data["status"])
        if "priority" in data:
            if data["priority"] not in PRIORITIES:
                raise ValueError("invalid priority")
            self.priority = data["priority"]
        if "assignee_id" in data:
            self.assignee_id = data["assignee_id"] or None
        if "project_id" in data:
            self.project_id = data["project_id"] or None
        for field in ("start_date", "due_date"):
            if field in data:
                value = data[field]
                setattr(
                    self,
                    field,
                    date.fromisoformat(value) if isinstance(value, str) and value else value,
                )
        if "progress" in data:
            progress = int(data["progress"])
            if not 0 <= progress <= 100:
                raise ValueError("progress must be between 0 and 100")
            self.progress = progress
        if "estimated_hours" in data:
            hours = data["estimated_hours"]
            if hours is not None and float(hours) < 0:
                raise ValueError("estimated_hours must be non-negative")
            self.estimated_hours = float(hours) if hours is not None else None
        if "tags" in data:
            self.tags = sorted({str(tag).strip() for tag in data["tags"] if str(tag).strip()})
        if self.start_date and self.due_date and self.start_date > self.due_date:
            raise ValueError("start_date cannot be after due_date")
        if self.status == "done":
            self.progress = 100
        self.updated_at = datetime.now(UTC)

    def add_entry(self, kind: str, content: str) -> ProgressEntry:
        entry = ProgressEntry.create(kind, content)
        self.entries.append(entry)
        self.updated_at = datetime.now(UTC)
        return entry

    def add_resource(self, resource: TaskResource) -> TaskResource:
        if len(self.resources) >= MAX_RESOURCES:
            raise ValueError("a task can have at most 40 resources")
        self.resources.append(resource)
        self.updated_at = datetime.now(UTC)
        return resource

    def remove_resource(self, resource_id: str) -> TaskResource:
        for index, resource in enumerate(self.resources):
            if resource.id == resource_id:
                self.resources.pop(index)
                self.updated_at = datetime.now(UTC)
                return resource
        raise LookupError("resource not found")

    def resource_by_id(self, resource_id: str) -> TaskResource:
        for resource in self.resources:
            if resource.id == resource_id:
                return resource
        raise LookupError("resource not found")

    def snapshot(self) -> "Task":
        values = {item.name: getattr(self, item.name) for item in fields(self)}
        values["entries"] = list(self.entries)
        values["resources"] = list(self.resources)
        return Task(**values)

    def change_status(self, status: str) -> None:
        if status not in STATUSES:
            raise ValueError("invalid status")
        if self.status == "cancelled" and status != "cancelled":
            raise ValueError("cancelled task cannot be reopened")
        self.status = status
        if status == "done":
            self.progress = 100


def normalize_skills(values: Any) -> list[str]:
    skills: list[str] = []
    seen: set[str] = set()
    for item in values or []:
        skill = decode_unicode_text(str(item)).strip()
        if not skill:
            continue
        if len(skill) > MAX_SKILL_LENGTH:
            raise ValueError("skill is too long")
        key = skill.casefold()
        if key in seen:
            continue
        seen.add(key)
        skills.append(skill)
        if len(skills) > MAX_MEMBER_SKILLS:
            raise ValueError("too many skills")
    return skills


def normalize_background(value: Any) -> str:
    text = decode_unicode_text(str(value or "")).strip()
    if len(text) > MAX_BACKGROUND_LENGTH:
        raise ValueError("background is too long")
    return text


@dataclass
class Project:
    id: str
    name: str
    description: str
    background: str
    started_at: date | None
    member_ids: list[str]
    status: str
    cover_color: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(cls, data: dict[str, Any]) -> "Project":
        now = datetime.now(UTC)
        project = cls(str(uuid4()), "", "", "", None, [], "planning", None, now, now)
        project.update(data)
        if not project.name:
            raise ValueError("project name is required")
        return project

    def update(self, data: dict[str, Any]) -> None:
        if "name" in data:
            name = decode_unicode_text(str(data["name"])).strip()
            if not name:
                raise ValueError("project name is required")
            if len(name) > MAX_PROJECT_NAME_LENGTH:
                raise ValueError("project name is too long")
            self.name = name
        if "description" in data:
            text = decode_unicode_text(str(data["description"] or "")).strip()
            if len(text) > MAX_PROJECT_DESCRIPTION_LENGTH:
                raise ValueError("project description is too long")
            self.description = text
        if "background" in data:
            text = decode_unicode_text(str(data["background"] or "")).strip()
            if len(text) > MAX_PROJECT_BACKGROUND_LENGTH:
                raise ValueError("project background is too long")
            self.background = text
        if "started_at" in data:
            value = data["started_at"]
            if isinstance(value, str) and value.strip():
                try:
                    self.started_at = date.fromisoformat(value.strip())
                except ValueError as exc:
                    raise ValueError("invalid started_at") from exc
            elif isinstance(value, date):
                self.started_at = value
            else:
                self.started_at = None
        if "member_ids" in data:
            ids: list[str] = []
            for item in data["member_ids"] or []:
                member_id = str(item).strip()
                if member_id and member_id not in ids:
                    ids.append(member_id)
            if len(ids) > MAX_PROJECT_MEMBERS:
                raise ValueError("too many project members")
            self.member_ids = ids
        if "status" in data:
            if data["status"] not in PROJECT_STATUSES:
                raise ValueError("invalid project status")
            self.status = data["status"]
        if "cover_color" in data:
            value = data["cover_color"]
            text = str(value).strip() if value else ""
            if text and not re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})", text):
                raise ValueError("cover_color must be a hex color like #36d9e9")
            self.cover_color = text or None
        self.updated_at = datetime.now(UTC)


@dataclass
class TeamMember:
    id: str
    name: str
    title: str
    active: bool
    color: str | None
    skills: list[str]
    background: str
    created_at: datetime
    updated_at: datetime
    user_id: str | None = None
    evaluations: list["MemberEvaluation"] = field(default_factory=list)

    @classmethod
    def create(cls, data: dict[str, Any]) -> "TeamMember":
        now = datetime.now(UTC)
        member = cls(str(uuid4()), "", "", True, None, [], "", now, now, None)
        member.update(data)
        if data.get("user_id"):
            member.user_id = str(data["user_id"])
        if not member.name:
            raise ValueError("name is required")
        return member

    def update(self, data: dict[str, Any]) -> None:
        if "name" in data:
            name = decode_unicode_text(str(data["name"]).strip())
            if not name:
                raise ValueError("name is required")
            self.name = name
        if "title" in data:
            self.title = decode_unicode_text(str(data["title"])).strip()
        if "active" in data:
            self.active = bool(data["active"])
        if "color" in data:
            value = data["color"]
            self.color = str(value).strip() if value else None
        if "skills" in data:
            self.skills = normalize_skills(data["skills"])
        if "background" in data:
            self.background = normalize_background(data["background"])
        self.updated_at = datetime.now(UTC)

    def add_evaluation(self, kind: str, content: str) -> MemberEvaluation:
        if len(self.evaluations) >= MAX_MEMBER_EVALUATIONS:
            raise ValueError("a member can have at most 200 evaluations")
        evaluation = MemberEvaluation.create(kind, content)
        self.evaluations.append(evaluation)
        self.updated_at = datetime.now(UTC)
        return evaluation

    def remove_evaluation(self, evaluation_id: str) -> MemberEvaluation:
        for index, evaluation in enumerate(self.evaluations):
            if evaluation.id == evaluation_id:
                self.evaluations.pop(index)
                self.updated_at = datetime.now(UTC)
                return evaluation
        raise LookupError("evaluation not found")


class TaskRepository(Protocol):
    async def save(self, task: Task) -> None: ...
    async def by_id(self, task_id: str) -> Task | None: ...
    async def list(self, filters: dict[str, Any]) -> list[Task]: ...
    async def delete(self, task_id: str) -> bool: ...
    async def ensure_indexes(self) -> None: ...


class MemberRepository(Protocol):
    async def save(self, member: TeamMember) -> None: ...
    async def by_id(self, member_id: str) -> TeamMember | None: ...
    async def by_name(self, name: str) -> TeamMember | None: ...
    async def by_user_id(self, user_id: str) -> TeamMember | None: ...
    async def list(self) -> list[TeamMember]: ...
    async def delete(self, member_id: str) -> bool: ...
    async def ensure_indexes(self) -> None: ...


class ProjectRepository(Protocol):
    async def save(self, project: Project) -> None: ...
    async def by_id(self, project_id: str) -> Project | None: ...
    async def by_name(self, name: str) -> Project | None: ...
    async def list(self) -> list[Project]: ...
    async def delete(self, project_id: str) -> bool: ...
    async def ensure_indexes(self) -> None: ...


class ProgressDomainService:
    def __init__(
        self,
        tasks: TaskRepository,
        members: MemberRepository,
        projects: ProjectRepository,
    ):
        self.tasks = tasks
        self.members = members
        self.projects = projects

    async def ensure_indexes(self) -> None:
        await self.tasks.ensure_indexes()
        await self.members.ensure_indexes()
        await self.projects.ensure_indexes()

    async def ensure_operator(self, user_id: str, name: str, title: str) -> TeamMember:
        existing = await self.members.by_user_id(user_id)
        if existing:
            if not existing.active:
                existing.active = True
                existing.updated_at = datetime.now(UTC)
                await self.members.save(existing)
            return existing
        named = await self.members.by_name(name)
        if named and not named.user_id:
            named.user_id = user_id
            named.active = True
            named.updated_at = datetime.now(UTC)
            await self.members.save(named)
            return named
        member = TeamMember.create({"name": name, "title": title, "user_id": user_id})
        await self.members.save(member)
        return member

    async def _validate_assignee(self, assignee_id: str | None) -> None:
        if not assignee_id:
            return
        member = await self.members.by_id(assignee_id)
        if not member or not member.active:
            raise ValueError("assignee must be an active team member")

    async def _validate_project(self, project_id: str | None) -> None:
        if not project_id:
            return
        if not await self.projects.by_id(project_id):
            raise ValueError("project not found")

    async def _validate_project_members(self, member_ids: list[str]) -> None:
        for member_id in member_ids:
            if not await self.members.by_id(member_id):
                raise ValueError(f"project member not found: {member_id}")

    def _apply_entry(self, task: Task, entry: dict[str, Any] | None) -> None:
        if not entry:
            return
        task.add_entry(entry["kind"], entry["content"])

    async def create(self, data: dict[str, Any], actor_id: str) -> Task:
        payload = dict(data)
        entry = payload.pop("add_entry", None)
        await self._validate_assignee(payload.get("assignee_id"))
        await self._validate_project(payload.get("project_id"))
        task = Task.create(payload, actor_id)
        self._apply_entry(task, entry)
        await self.tasks.save(task)
        return task

    async def update(self, task_id: str, data: dict[str, Any]) -> Task:
        payload = dict(data)
        entry = payload.pop("add_entry", None)
        task = await self.get_task(task_id)
        await self._validate_assignee(payload.get("assignee_id"))
        await self._validate_project(payload.get("project_id"))
        if payload:
            task.update(payload)
        self._apply_entry(task, entry)
        await self.tasks.save(task)
        return task

    async def validate_changes(
        self,
        operation: str,
        task_id: str | None,
        data: dict[str, Any],
        entry: dict[str, Any] | None = None,
    ) -> Task:
        payload = dict(data)
        payload.pop("add_entry", None)
        await self._validate_assignee(payload.get("assignee_id"))
        await self._validate_project(payload.get("project_id"))
        if operation == "create_task":
            task = Task.create(payload, "preview")
        else:
            task = (await self.get_task(task_id or "")).snapshot()
            if payload:
                task.update(payload)
        self._apply_entry(task, entry)
        return task

    async def get_task(self, task_id: str) -> Task:
        task = await self.tasks.by_id(task_id)
        if not task:
            raise LookupError("task not found")
        return task

    async def list_tasks(self, filters: dict[str, Any]) -> list[Task]:
        return await self.tasks.list(filters)

    async def add_resource(self, task_id: str, resource: TaskResource) -> Task:
        task = await self.get_task(task_id)
        task.add_resource(resource)
        await self.tasks.save(task)
        return task

    async def remove_resource(self, task_id: str, resource_id: str) -> tuple[Task, TaskResource]:
        task = await self.get_task(task_id)
        removed = task.remove_resource(resource_id)
        await self.tasks.save(task)
        return task, removed

    async def delete_task(self, task_id: str) -> Task:
        task = await self.get_task(task_id)
        if not await self.tasks.delete(task_id):
            raise LookupError("task not found")
        return task

    async def create_member(self, data: dict[str, Any]) -> TeamMember:
        if await self.members.by_name(data["name"]):
            raise ValueError("member name already exists")
        member = TeamMember.create(data)
        await self.members.save(member)
        return member

    async def list_members(self) -> list[TeamMember]:
        return await self.members.list()

    async def get_member(self, member_id: str) -> TeamMember:
        member = await self.members.by_id(member_id)
        if not member:
            raise LookupError("member not found")
        return member

    async def update_member(self, member_id: str, data: dict[str, Any]) -> TeamMember:
        member = await self.get_member(member_id)
        if member.user_id and data.get("active") is False:
            raise ValueError("operator cannot be deactivated")
        if "name" in data:
            existing = await self.members.by_name(data["name"])
            if existing and existing.id != member_id:
                raise ValueError("member name already exists")
        member.update(data)
        await self.members.save(member)
        return member

    async def add_member_evaluation(self, member_id: str, kind: str, content: str) -> TeamMember:
        member = await self.get_member(member_id)
        member.add_evaluation(kind, content)
        await self.members.save(member)
        return member

    async def remove_member_evaluation(self, member_id: str, evaluation_id: str) -> TeamMember:
        member = await self.get_member(member_id)
        member.remove_evaluation(evaluation_id)
        await self.members.save(member)
        return member

    async def validate_member_changes(
        self, member_id: str | None, data: dict[str, Any]
    ) -> TeamMember:
        payload = dict(data)
        if not member_id:
            name = str(payload.get("name") or "").strip()
            if name and await self.members.by_name(name):
                raise ValueError("member name already exists")
            return TeamMember.create(payload)
        member = await self.get_member(member_id)
        if member.user_id and payload.get("active") is False:
            raise ValueError("operator cannot be deactivated")
        if "name" in payload:
            existing = await self.members.by_name(str(payload["name"]))
            if existing and existing.id != member_id:
                raise ValueError("member name already exists")
        preview = replace(
            member,
            skills=list(member.skills),
            evaluations=list(member.evaluations),
        )
        preview.update(payload)
        return preview

    async def delete_member(self, member_id: str) -> None:
        member = await self.get_member(member_id)
        if member.user_id:
            raise ValueError("cannot delete the operator member")
        if not await self.members.delete(member_id):
            raise LookupError("member not found")

    async def create_project(self, data: dict[str, Any]) -> Project:
        name = str(data.get("name") or "").strip()
        if name and await self.projects.by_name(name):
            raise ValueError("project name already exists")
        project = Project.create(data)
        await self._validate_project_members(project.member_ids)
        await self.projects.save(project)
        return project

    async def list_projects(self) -> list[Project]:
        return await self.projects.list()

    async def get_project(self, project_id: str) -> Project:
        project = await self.projects.by_id(project_id)
        if not project:
            raise LookupError("project not found")
        return project

    async def update_project(self, project_id: str, data: dict[str, Any]) -> Project:
        project = await self.get_project(project_id)
        if "name" in data:
            existing = await self.projects.by_name(str(data["name"]).strip())
            if existing and existing.id != project_id:
                raise ValueError("project name already exists")
        project.update(data)
        await self._validate_project_members(project.member_ids)
        await self.projects.save(project)
        return project

    async def delete_project(self, project_id: str) -> None:
        await self.get_project(project_id)
        for task in await self.tasks.list({}):
            if task.project_id == project_id:
                task.project_id = None
                await self.tasks.save(task)
        if not await self.projects.delete(project_id):
            raise LookupError("project not found")

    async def project_by_name(self, name: str) -> Project | None:
        return await self.projects.by_name(name)

    async def validate_project_changes(
        self, project_id: str | None, data: dict[str, Any]
    ) -> Project:
        payload = dict(data)
        if not project_id:
            name = str(payload.get("name") or "").strip()
            if name and await self.projects.by_name(name):
                raise ValueError("project name already exists")
            return Project.create(payload)
        project = await self.get_project(project_id)
        if "name" in payload:
            existing = await self.projects.by_name(str(payload["name"]).strip())
            if existing and existing.id != project_id:
                raise ValueError("project name already exists")
        preview = replace(project, member_ids=list(project.member_ids))
        preview.update(payload)
        return preview

    async def member_by_name(self, name: str) -> TeamMember | None:
        return await self.members.by_name(name)
