from typing import Any

from ai_settings.domain import AISettings
from identity.domain import DeviceBinding, User
from knowledge.domain import KnowledgeDocument, KnowledgeEntry, KnowledgeTag
from progress.domain import Project, Task, TeamMember


class MemoryUserRepository:
    def __init__(self):
        self.items: dict[str, User] = {}

    async def count(self) -> int:
        return len(self.items)

    async def save(self, user: User) -> None:
        self.items[user.id] = user

    async def by_id(self, user_id: str) -> User | None:
        return self.items.get(user_id)

    async def by_username(self, username: str) -> User | None:
        return next((item for item in self.items.values() if item.username == username), None)

    async def list(self) -> list[User]:
        return list(self.items.values())

    async def delete(self, user_id: str) -> bool:
        user = self.items.get(user_id)
        if not user or user.role == "admin":
            return False
        del self.items[user_id]
        return True

    async def ensure_indexes(self) -> None:
        return None


class MemoryTaskRepository:
    def __init__(self):
        self.items: dict[str, Task] = {}

    async def save(self, task: Task) -> None:
        self.items[task.id] = task

    async def by_id(self, task_id: str) -> Task | None:
        return self.items.get(task_id)

    async def list(self, filters: dict[str, Any]) -> list[Task]:
        result = list(self.items.values())
        for key in ("status", "priority", "assignee_id"):
            if filters.get(key):
                result = [task for task in result if getattr(task, key) == filters[key]]
        if filters.get("tag"):
            result = [task for task in result if filters["tag"] in task.tags]
        return result

    async def delete(self, task_id: str) -> bool:
        return self.items.pop(task_id, None) is not None

    async def ensure_indexes(self) -> None:
        return None


class MemoryMemberRepository:
    def __init__(self):
        self.items: dict[str, TeamMember] = {}
    async def save(self, member: TeamMember) -> None:
        self.items[member.id] = member

    async def by_id(self, member_id: str) -> TeamMember | None:
        return self.items.get(member_id)

    async def by_name(self, name: str) -> TeamMember | None:
        return next(
            (item for item in self.items.values() if item.name.casefold() == name.casefold()),
            None,
        )

    async def by_user_id(self, user_id: str) -> TeamMember | None:
        return next((item for item in self.items.values() if item.user_id == user_id), None)

    async def list(self) -> list[TeamMember]:
        return list(self.items.values())

    async def delete(self, member_id: str) -> bool:
        return self.items.pop(member_id, None) is not None

    async def ensure_indexes(self) -> None:
        return None


class MemoryProjectRepository:
    def __init__(self):
        self.items: dict[str, Project] = {}

    async def save(self, project: Project) -> None:
        self.items[project.id] = project

    async def by_id(self, project_id: str) -> Project | None:
        return self.items.get(project_id)

    async def by_name(self, name: str) -> Project | None:
        return next(
            (item for item in self.items.values() if item.name.casefold() == name.casefold()),
            None,
        )

    async def list(self) -> list[Project]:
        return list(self.items.values())

    async def delete(self, project_id: str) -> bool:
        return self.items.pop(project_id, None) is not None

    async def ensure_indexes(self) -> None:
        return None


class MemoryDeviceRepository:
    def __init__(self):
        self.items: dict[tuple[str, str], DeviceBinding] = {}

    async def save(self, binding: DeviceBinding) -> None:
        self.items[(binding.user_id, binding.device_id)] = binding

    async def by_device(self, device_id: str) -> DeviceBinding | None:
        return next((item for item in self.items.values() if item.device_id == device_id), None)

    async def list_for_user(self, user_id: str) -> list[DeviceBinding]:
        return [item for item in self.items.values() if item.user_id == user_id]

    async def delete(self, user_id: str, binding_id: str) -> bool:
        found = next(
            (key for key, item in self.items.items() if key[0] == user_id and item.id == binding_id),
            None,
        )
        return self.items.pop(found, None) is not None if found else False

    async def ensure_indexes(self) -> None:
        return None


class MemoryResourceStorage:
    def __init__(self):
        self.files: dict[str, bytes] = {}

    async def put(self, key: str, data: bytes) -> None:
        self.files[key] = data

    async def delete(self, key: str) -> None:
        self.files.pop(key, None)

    async def read(self, key: str) -> bytes:
        if key not in self.files:
            raise LookupError("resource file not found")
        return self.files[key]

    def path_for(self, key: str) -> None:
        return None


class MemoryTagRepository:
    def __init__(self):
        self.items: dict[str, KnowledgeTag] = {}

    async def save(self, tag: KnowledgeTag) -> None:
        self.items[tag.id] = tag

    async def by_id(self, tag_id: str) -> KnowledgeTag | None:
        return self.items.get(tag_id)

    async def by_name(self, name: str) -> KnowledgeTag | None:
        return next(
            (item for item in self.items.values() if item.name.casefold() == name.casefold()),
            None,
        )

    async def list(self) -> list[KnowledgeTag]:
        return list(self.items.values())

    async def delete(self, tag_id: str) -> bool:
        return self.items.pop(tag_id, None) is not None

    async def ensure_indexes(self) -> None:
        return None


class MemoryEntryRepository:
    def __init__(self):
        self.items: dict[str, KnowledgeEntry] = {}

    async def save(self, entry: KnowledgeEntry) -> None:
        self.items[entry.id] = entry

    async def by_id(self, entry_id: str) -> KnowledgeEntry | None:
        return self.items.get(entry_id)

    async def by_key(self, key: str) -> KnowledgeEntry | None:
        return next(
            (item for item in self.items.values() if item.key.casefold() == key.casefold()),
            None,
        )

    async def list(self) -> list[KnowledgeEntry]:
        return list(self.items.values())

    async def delete(self, entry_id: str) -> bool:
        return self.items.pop(entry_id, None) is not None

    async def ensure_indexes(self) -> None:
        return None


class MemoryDocumentRepository:
    def __init__(self):
        self.items: dict[str, KnowledgeDocument] = {}

    async def save(self, document: KnowledgeDocument) -> None:
        self.items[document.id] = document

    async def by_id(self, document_id: str) -> KnowledgeDocument | None:
        return self.items.get(document_id)

    async def list(self) -> list[KnowledgeDocument]:
        return list(self.items.values())

    async def delete(self, document_id: str) -> bool:
        return self.items.pop(document_id, None) is not None

    async def ensure_indexes(self) -> None:
        return None


class MemoryAISettingsRepository:
    def __init__(self):
        self.settings: AISettings | None = None

    async def get(self) -> AISettings | None:
        return self.settings

    async def save(self, settings: AISettings) -> None:
        self.settings = settings

    async def ensure_indexes(self) -> None:
        return None


def knowledge_overrides() -> dict[str, Any]:
    from knowledge.corpus import MemoryKnowledgeCorpus

    return {
        "knowledge_tag_repository": MemoryTagRepository(),
        "knowledge_entry_repository": MemoryEntryRepository(),
        "knowledge_document_repository": MemoryDocumentRepository(),
        "knowledge_corpus": MemoryKnowledgeCorpus(),
    }
