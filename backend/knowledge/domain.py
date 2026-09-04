from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

from progress.domain import decode_unicode_text

MAX_TAG_NAME = 40
MAX_EXPLANATION = 2000
MAX_KEY_LENGTH = 200
MAX_VALUE_LENGTH = 20_000
MAX_BODY_CHARS = 200_000
MAX_ALIASES = 10
MAX_ALIAS_LENGTH = 80
MAX_TITLE_LENGTH = 200


def _clean(value: Any, *, required: bool, max_length: int, field: str) -> str:
    text = decode_unicode_text(str(value or "")).strip()
    if required and not text:
        raise ValueError(f"{field} is required")
    if len(text) > max_length:
        raise ValueError(f"{field} is too long")
    return text


def normalize_aliases(value: Any) -> list[str]:
    items = value if isinstance(value, list) else []
    aliases: list[str] = []
    seen: set[str] = set()
    for item in items:
        alias = decode_unicode_text(str(item)).strip()
        if not alias:
            continue
        if len(alias) > MAX_ALIAS_LENGTH:
            raise ValueError("alias is too long")
        key = alias.casefold()
        if key in seen:
            continue
        seen.add(key)
        aliases.append(alias)
        if len(aliases) > MAX_ALIASES:
            raise ValueError("too many aliases")
    return aliases


def normalize_ids(value: Any) -> list[str]:
    items = value if isinstance(value, list) else []
    ids: list[str] = []
    seen: set[str] = set()
    for item in items:
        ident = str(item or "").strip()
        if not ident or ident in seen:
            continue
        seen.add(ident)
        ids.append(ident)
    return ids


def normalize_body(value: Any) -> str:
    text = decode_unicode_text(str(value or "")).replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    body = "\n".join(lines).strip()
    if len(body) > MAX_BODY_CHARS:
        raise ValueError("document body is too long")
    return body


@dataclass
class KnowledgeTag:
    id: str
    name: str
    explanation: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(cls, data: dict[str, Any]) -> "KnowledgeTag":
        now = datetime.now(UTC)
        tag = cls(str(uuid4()), "", "", now, now)
        tag.update(data, require_name=True)
        return tag

    def update(self, data: dict[str, Any], require_name: bool = False) -> None:
        if "name" in data or require_name:
            self.name = _clean(
                data.get("name"), required=True, max_length=MAX_TAG_NAME, field="name"
            )
        if "explanation" in data or require_name:
            self.explanation = _clean(
                data.get("explanation"),
                required=True,
                max_length=MAX_EXPLANATION,
                field="explanation",
            )
        self.updated_at = datetime.now(UTC)


@dataclass
class KnowledgeEntry:
    id: str
    key: str
    value: str
    tag_ids: list[str]
    document_ids: list[str]
    aliases: list[str]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(cls, data: dict[str, Any]) -> "KnowledgeEntry":
        now = datetime.now(UTC)
        entry = cls(str(uuid4()), "", "", [], [], [], now, now)
        entry.update(data, require_key=True)
        return entry

    def update(self, data: dict[str, Any], require_key: bool = False) -> None:
        if "key" in data or require_key:
            self.key = _clean(
                data.get("key"), required=True, max_length=MAX_KEY_LENGTH, field="key"
            )
        if "value" in data or require_key:
            self.value = _clean(
                data.get("value"), required=True, max_length=MAX_VALUE_LENGTH, field="value"
            )
        if "tag_ids" in data:
            self.tag_ids = normalize_ids(data["tag_ids"])
        if "document_ids" in data:
            self.document_ids = normalize_ids(data["document_ids"])
        if "aliases" in data:
            self.aliases = normalize_aliases(data["aliases"])
        self.updated_at = datetime.now(UTC)


@dataclass
class KnowledgeDocument:
    id: str
    title: str
    body: str
    tag_ids: list[str]
    entry_ids: list[str]
    raw_filename: str | None
    raw_storage_key: str | None
    canvas_x: float
    canvas_y: float
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(cls, data: dict[str, Any]) -> "KnowledgeDocument":
        now = datetime.now(UTC)
        document = cls(str(uuid4()), "", "", [], [], None, None, 80.0, 80.0, now, now)
        document.update(data, require_title=True)
        return document

    def update(self, data: dict[str, Any], require_title: bool = False) -> None:
        if "title" in data or require_title:
            self.title = _clean(
                data.get("title"), required=True, max_length=MAX_TITLE_LENGTH, field="title"
            )
        if "body" in data:
            self.body = normalize_body(data["body"])
        if "tag_ids" in data:
            self.tag_ids = normalize_ids(data["tag_ids"])
        if "entry_ids" in data:
            self.entry_ids = normalize_ids(data["entry_ids"])
        if "raw_filename" in data:
            value = data["raw_filename"]
            self.raw_filename = str(value).strip() if value else None
        if "raw_storage_key" in data:
            value = data["raw_storage_key"]
            self.raw_storage_key = str(value).strip() if value else None
        if "canvas_x" in data:
            self.canvas_x = float(data["canvas_x"])
        if "canvas_y" in data:
            self.canvas_y = float(data["canvas_y"])
        self.updated_at = datetime.now(UTC)


class TagRepository(Protocol):
    async def save(self, tag: KnowledgeTag) -> None: ...
    async def by_id(self, tag_id: str) -> KnowledgeTag | None: ...
    async def by_name(self, name: str) -> KnowledgeTag | None: ...
    async def list(self) -> list[KnowledgeTag]: ...
    async def delete(self, tag_id: str) -> bool: ...
    async def ensure_indexes(self) -> None: ...


class EntryRepository(Protocol):
    async def save(self, entry: KnowledgeEntry) -> None: ...
    async def by_id(self, entry_id: str) -> KnowledgeEntry | None: ...
    async def by_key(self, key: str) -> KnowledgeEntry | None: ...
    async def list(self) -> list[KnowledgeEntry]: ...
    async def delete(self, entry_id: str) -> bool: ...
    async def ensure_indexes(self) -> None: ...


class DocumentRepository(Protocol):
    async def save(self, document: KnowledgeDocument) -> None: ...
    async def by_id(self, document_id: str) -> KnowledgeDocument | None: ...
    async def list(self) -> list[KnowledgeDocument]: ...
    async def delete(self, document_id: str) -> bool: ...
    async def ensure_indexes(self) -> None: ...


class KnowledgeDomainService:
    def __init__(
        self,
        tags: TagRepository,
        entries: EntryRepository,
        documents: DocumentRepository,
    ):
        self.tags = tags
        self.entries = entries
        self.documents = documents

    async def ensure_indexes(self) -> None:
        await self.tags.ensure_indexes()
        await self.entries.ensure_indexes()
        await self.documents.ensure_indexes()

    async def _require_tags(self, tag_ids: list[str]) -> None:
        for tag_id in tag_ids:
            if not await self.tags.by_id(tag_id):
                raise ValueError(f"unknown tag: {tag_id}")

    async def _sync_entry_documents(self, entry: KnowledgeEntry, document_ids: list[str]) -> None:
        previous = set(entry.document_ids)
        wanted = set(document_ids)
        for document_id in previous - wanted:
            document = await self.get_document(document_id)
            document.entry_ids = [item for item in document.entry_ids if item != entry.id]
            await self.documents.save(document)
        for document_id in wanted - previous:
            document = await self.get_document(document_id)
            if entry.id not in document.entry_ids:
                document.entry_ids.append(entry.id)
                await self.documents.save(document)
        entry.document_ids = list(document_ids)

    async def _sync_document_entries(
        self, document: KnowledgeDocument, entry_ids: list[str]
    ) -> None:
        previous = set(document.entry_ids)
        wanted = set(entry_ids)
        for entry_id in previous - wanted:
            entry = await self.get_entry(entry_id)
            entry.document_ids = [item for item in entry.document_ids if item != document.id]
            await self.entries.save(entry)
        for entry_id in wanted - previous:
            entry = await self.get_entry(entry_id)
            if document.id not in entry.document_ids:
                entry.document_ids.append(document.id)
                await self.entries.save(entry)
        document.entry_ids = list(entry_ids)

    async def create_tag(self, data: dict[str, Any]) -> KnowledgeTag:
        name = _clean(data.get("name"), required=True, max_length=MAX_TAG_NAME, field="name")
        if await self.tags.by_name(name):
            raise ValueError("tag name already exists")
        tag = KnowledgeTag.create(data)
        await self.tags.save(tag)
        return tag

    async def list_tags(self) -> list[KnowledgeTag]:
        return await self.tags.list()

    async def get_tag(self, tag_id: str) -> KnowledgeTag:
        tag = await self.tags.by_id(tag_id)
        if not tag:
            raise LookupError("tag not found")
        return tag

    async def tag_by_name(self, name: str) -> KnowledgeTag | None:
        return await self.tags.by_name(name)

    async def update_tag(self, tag_id: str, data: dict[str, Any]) -> KnowledgeTag:
        tag = await self.get_tag(tag_id)
        if "name" in data:
            existing = await self.tags.by_name(str(data["name"]))
            if existing and existing.id != tag_id:
                raise ValueError("tag name already exists")
        tag.update(data)
        await self.tags.save(tag)
        return tag

    async def validate_tag_changes(
        self, tag_id: str | None, data: dict[str, Any]
    ) -> KnowledgeTag:
        if not tag_id:
            return KnowledgeTag.create(data)
        tag = await self.get_tag(tag_id)
        if "name" in data:
            existing = await self.tags.by_name(str(data["name"]))
            if existing and existing.id != tag_id:
                raise ValueError("tag name already exists")
        preview = replace(tag)
        preview.update(data)
        return preview

    async def delete_tag(self, tag_id: str) -> None:
        await self.get_tag(tag_id)
        for entry in await self.entries.list():
            if tag_id in entry.tag_ids:
                entry.tag_ids = [item for item in entry.tag_ids if item != tag_id]
                await self.entries.save(entry)
        for document in await self.documents.list():
            if tag_id in document.tag_ids:
                document.tag_ids = [item for item in document.tag_ids if item != tag_id]
                await self.documents.save(document)
        if not await self.tags.delete(tag_id):
            raise LookupError("tag not found")

    async def create_entry(self, data: dict[str, Any]) -> KnowledgeEntry:
        key = _clean(data.get("key"), required=True, max_length=MAX_KEY_LENGTH, field="key")
        if await self.entries.by_key(key):
            raise ValueError("entry key already exists")
        payload = dict(data)
        document_ids = normalize_ids(payload.pop("document_ids", []))
        await self._require_tags(normalize_ids(payload.get("tag_ids") or []))
        for document_id in document_ids:
            await self.get_document(document_id)
        entry = KnowledgeEntry.create(payload)
        await self._sync_entry_documents(entry, document_ids)
        await self.entries.save(entry)
        return entry

    async def list_entries(self) -> list[KnowledgeEntry]:
        return await self.entries.list()

    async def get_entry(self, entry_id: str) -> KnowledgeEntry:
        entry = await self.entries.by_id(entry_id)
        if not entry:
            raise LookupError("entry not found")
        return entry

    async def entry_by_key(self, key: str) -> KnowledgeEntry | None:
        return await self.entries.by_key(key)

    async def update_entry(self, entry_id: str, data: dict[str, Any]) -> KnowledgeEntry:
        entry = await self.get_entry(entry_id)
        payload = dict(data)
        if "key" in payload:
            existing = await self.entries.by_key(str(payload["key"]))
            if existing and existing.id != entry_id:
                raise ValueError("entry key already exists")
        if "tag_ids" in payload:
            await self._require_tags(normalize_ids(payload["tag_ids"]))
        document_ids = payload.pop("document_ids", None)
        entry.update(payload)
        if document_ids is not None:
            await self._sync_entry_documents(entry, normalize_ids(document_ids))
        await self.entries.save(entry)
        return entry

    async def validate_entry_changes(
        self, entry_id: str | None, data: dict[str, Any]
    ) -> KnowledgeEntry:
        payload = dict(data)
        if not entry_id:
            if payload.get("key") and await self.entries.by_key(str(payload["key"])):
                raise ValueError("entry key already exists")
            if "tag_ids" in payload:
                await self._require_tags(normalize_ids(payload["tag_ids"]))
            return KnowledgeEntry.create(payload)
        entry = await self.get_entry(entry_id)
        if "key" in payload:
            existing = await self.entries.by_key(str(payload["key"]))
            if existing and existing.id != entry_id:
                raise ValueError("entry key already exists")
        if "tag_ids" in payload:
            await self._require_tags(normalize_ids(payload["tag_ids"]))
        preview = replace(entry, tag_ids=list(entry.tag_ids), document_ids=list(entry.document_ids))
        preview.update(payload)
        return preview

    async def delete_entry(self, entry_id: str) -> None:
        entry = await self.get_entry(entry_id)
        await self._sync_entry_documents(entry, [])
        if not await self.entries.delete(entry_id):
            raise LookupError("entry not found")

    async def create_document(self, data: dict[str, Any]) -> KnowledgeDocument:
        payload = dict(data)
        entry_ids = normalize_ids(payload.pop("entry_ids", []))
        await self._require_tags(normalize_ids(payload.get("tag_ids") or []))
        document = KnowledgeDocument.create(payload)
        await self._sync_document_entries(document, entry_ids)
        await self.documents.save(document)
        return document

    async def list_documents(self) -> list[KnowledgeDocument]:
        return await self.documents.list()

    async def get_document(self, document_id: str) -> KnowledgeDocument:
        document = await self.documents.by_id(document_id)
        if not document:
            raise LookupError("document not found")
        return document

    async def update_document(self, document_id: str, data: dict[str, Any]) -> KnowledgeDocument:
        document = await self.get_document(document_id)
        payload = dict(data)
        if "tag_ids" in payload:
            await self._require_tags(normalize_ids(payload["tag_ids"]))
        entry_ids = payload.pop("entry_ids", None)
        document.update(payload)
        if entry_ids is not None:
            await self._sync_document_entries(document, normalize_ids(entry_ids))
        await self.documents.save(document)
        return document

    async def validate_document_changes(
        self, document_id: str | None, data: dict[str, Any]
    ) -> KnowledgeDocument:
        payload = dict(data)
        if "tag_ids" in payload:
            await self._require_tags(normalize_ids(payload["tag_ids"]))
        if not document_id:
            return KnowledgeDocument.create(payload)
        document = await self.get_document(document_id)
        preview = replace(
            document, tag_ids=list(document.tag_ids), entry_ids=list(document.entry_ids)
        )
        preview.update(payload)
        return preview

    async def link_entry(self, document_id: str, entry_id: str) -> KnowledgeDocument:
        document = await self.get_document(document_id)
        await self.get_entry(entry_id)
        if entry_id not in document.entry_ids:
            await self._sync_document_entries(document, [*document.entry_ids, entry_id])
            await self.documents.save(document)
        return document

    async def delete_document(self, document_id: str) -> KnowledgeDocument:
        document = await self.get_document(document_id)
        await self._sync_document_entries(document, [])
        if not await self.documents.delete(document_id):
            raise LookupError("document not found")
        return document
