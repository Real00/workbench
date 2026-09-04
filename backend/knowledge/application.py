from dataclasses import asdict
from typing import Any

from knowledge.corpus import KnowledgeCorpus
from knowledge.domain import (
    KnowledgeDocument,
    KnowledgeDomainService,
    KnowledgeEntry,
    KnowledgeTag,
)
from knowledge.extract import extract_markdown


def public_tag(tag: KnowledgeTag) -> dict[str, Any]:
    return asdict(tag)


def public_entry(entry: KnowledgeEntry) -> dict[str, Any]:
    return asdict(entry)


def public_document(document: KnowledgeDocument) -> dict[str, Any]:
    data = asdict(document)
    data["has_raw"] = bool(document.raw_storage_key)
    return data


def _matches(text: str, needle: str) -> bool:
    return needle.casefold() in text.casefold()


class KnowledgeApplicationService:
    def __init__(self, domain: KnowledgeDomainService, corpus: KnowledgeCorpus):
        self.domain = domain
        self.corpus = corpus

    async def initialize(self) -> None:
        await self.domain.ensure_indexes()
        await self.compile()

    async def compile(self) -> None:
        await self.corpus.rebuild(
            await self.domain.list_tags(),
            await self.domain.list_entries(),
            await self.domain.list_documents(),
        )

    def extract(self, filename: str, data: bytes) -> dict[str, str]:
        return {"filename": filename, "body": extract_markdown(filename, data)}

    async def create_tag(self, data: dict[str, Any]) -> dict[str, Any]:
        tag = await self.domain.create_tag(data)
        await self.compile()
        return public_tag(tag)

    async def list_tags(self, query: str = "") -> list[dict[str, Any]]:
        tags = [public_tag(tag) for tag in await self.domain.list_tags()]
        if query:
            tags = [
                tag
                for tag in tags
                if _matches(tag["name"], query) or _matches(tag["explanation"], query)
            ]
        return tags

    async def update_tag(self, tag_id: str, data: dict[str, Any]) -> dict[str, Any]:
        tag = await self.domain.update_tag(tag_id, data)
        await self.compile()
        return public_tag(tag)

    async def delete_tag(self, tag_id: str) -> None:
        await self.domain.delete_tag(tag_id)
        await self.compile()

    async def create_entry(self, data: dict[str, Any]) -> dict[str, Any]:
        entry = await self.domain.create_entry(data)
        await self.compile()
        return public_entry(entry)

    async def list_entries(
        self, query: str = "", tag_id: str | None = None
    ) -> list[dict[str, Any]]:
        entries = await self.domain.list_entries()
        if tag_id:
            entries = [entry for entry in entries if tag_id in entry.tag_ids]
        result = [public_entry(entry) for entry in entries]
        if query:
            result = [
                entry
                for entry in result
                if _matches(entry["key"], query)
                or _matches(entry["value"], query)
                or any(_matches(alias, query) for alias in entry["aliases"])
            ]
        return result

    async def get_entry(self, entry_id: str) -> dict[str, Any]:
        return public_entry(await self.domain.get_entry(entry_id))

    async def update_entry(self, entry_id: str, data: dict[str, Any]) -> dict[str, Any]:
        entry = await self.domain.update_entry(entry_id, data)
        await self.compile()
        return public_entry(entry)

    async def delete_entry(self, entry_id: str) -> None:
        await self.domain.delete_entry(entry_id)
        await self.compile()

    async def create_document(self, data: dict[str, Any]) -> dict[str, Any]:
        document = await self.domain.create_document(data)
        await self.compile()
        return public_document(document)

    async def list_documents(
        self, query: str = "", tag_id: str | None = None
    ) -> list[dict[str, Any]]:
        documents = await self.domain.list_documents()
        if tag_id:
            documents = [document for document in documents if tag_id in document.tag_ids]
        result = [public_document(document) for document in documents]
        if query:
            result = [
                document
                for document in result
                if _matches(document["title"], query) or _matches(document["body"], query)
            ]
        return result

    async def get_document(self, document_id: str) -> dict[str, Any]:
        return public_document(await self.domain.get_document(document_id))

    async def update_document(self, document_id: str, data: dict[str, Any]) -> dict[str, Any]:
        document = await self.domain.update_document(document_id, data)
        await self.compile()
        return public_document(document)

    async def import_document(
        self, document_id: str, filename: str, data: bytes, apply_body: bool = True
    ) -> dict[str, Any]:
        key = await self.corpus.put_raw(document_id, filename, data)
        payload: dict[str, Any] = {"raw_filename": filename, "raw_storage_key": key}
        if apply_body:
            payload["body"] = extract_markdown(filename, data)
        document = await self.domain.update_document(document_id, payload)
        await self.compile()
        return public_document(document)

    async def move_document(
        self, document_id: str, canvas_x: float, canvas_y: float
    ) -> dict[str, Any]:
        document = await self.domain.update_document(
            document_id, {"canvas_x": canvas_x, "canvas_y": canvas_y}
        )
        return public_document(document)

    async def delete_document(self, document_id: str) -> None:
        document = await self.domain.delete_document(document_id)
        await self.corpus.delete_raw(document.id)
        await self.compile()

    async def apply_operation(self, operation: dict[str, Any]) -> dict[str, Any]:
        op = operation.get("op")
        if op == "create_tag":
            return await self.create_tag(operation.get("changes") or {})
        if op == "update_tag":
            return await self.update_tag(operation["tag_id"], operation.get("changes") or {})
        if op == "create_entry":
            return await self.create_entry(operation.get("changes") or {})
        if op == "update_entry":
            return await self.update_entry(operation["entry_id"], operation.get("changes") or {})
        if op == "create_document":
            return await self.create_document(operation.get("changes") or {})
        if op == "update_document":
            return await self.update_document(
                operation["document_id"], operation.get("changes") or {}
            )
        if op == "link_entry":
            document = await self.domain.link_entry(operation["document_id"], operation["entry_id"])
            await self.compile()
            return public_document(document)
        raise ValueError(f"unknown AI operation: {op}")
