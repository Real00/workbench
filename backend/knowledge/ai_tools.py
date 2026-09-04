from __future__ import annotations

from typing import Any, Literal

from pydantic_ai import ModelRetry, RunContext

from knowledge.domain import KnowledgeDocument, KnowledgeEntry
from pulse.deps import AgentDeps
from shared.ai import ModuleAiContribution

INSTRUCTIONS = (
    "Knowledge module: search the compiled markdown corpus, not Mongo. "
    "Read index.md first, then search_knowledge over wiki/ only (never raw/). "
    "Use glob like wiki/entries/** or wiki/documents/** to narrow. "
    "Then read_knowledge for the matching file. "
    "Entries are key/value concepts; use the exact key from list_entries. "
    "Documents are markdown notes that can link many entries and tags. "
    "Tags have a required explanation. "
    "To extract facts from a document, read it then queue create_entry and link_entry. "
    "Never claim knowledge was saved until the user confirms."
)


def _changes(**fields: Any) -> dict[str, Any]:
    return {key: value for key, value in fields.items() if value is not None}


def _knowledge(ctx: RunContext[AgentDeps]):
    if ctx.deps.knowledge is None:
        raise ModelRetry("knowledge module is not available")
    return ctx.deps.knowledge


def _corpus(ctx: RunContext[AgentDeps]):
    if ctx.deps.corpus is None:
        raise ModelRetry("knowledge corpus is not available")
    return ctx.deps.corpus


async def _resolve_entry(
    ctx: RunContext[AgentDeps], entry_id: str | None, key: str | None
) -> KnowledgeEntry:
    domain = _knowledge(ctx)
    if entry_id:
        try:
            return await domain.get_entry(entry_id)
        except LookupError as exc:
            raise ModelRetry(f"entry not found: {entry_id}") from exc
    if not key or not key.strip():
        raise ModelRetry("provide entry key")
    entry = await domain.entry_by_key(key.strip())
    if not entry:
        raise ModelRetry(f"unknown entry key: {key.strip()}")
    return entry


async def _resolve_document(
    ctx: RunContext[AgentDeps], document_id: str | None, title: str | None
) -> KnowledgeDocument:
    domain = _knowledge(ctx)
    ident = document_id or ctx.deps.context_document_id
    if ident:
        try:
            return await domain.get_document(ident)
        except LookupError as exc:
            raise ModelRetry(f"document not found: {ident}") from exc
    if not title or not title.strip():
        raise ModelRetry("provide document_id or title")
    needle = title.strip().casefold()
    documents = await domain.list_documents()
    exact = [item for item in documents if item.title.casefold() == needle]
    if len(exact) == 1:
        return exact[0]
    contains = [item for item in documents if needle in item.title.casefold()]
    if len(contains) == 1:
        return contains[0]
    if not contains:
        raise ModelRetry(f"no document matching {title!r}")
    names = ", ".join(item.title for item in contains[:6])
    raise ModelRetry(f"multiple matching documents, be more specific: {names}")


async def search_knowledge(
    ctx: RunContext[AgentDeps],
    pattern: str,
    glob: str | None = None,
    output_mode: Literal["content", "files_with_matches", "count"] = "content",
    head_limit: int = 50,
) -> list[Any]:
    """Grep compiled knowledge markdown. Skip raw/. Prefer index.md then wiki/."""
    if glob and glob.replace("\\", "/").startswith("raw"):
        raise ModelRetry("raw/ is not searchable")
    return _corpus(ctx).search(pattern, glob, output_mode, head_limit)


async def read_knowledge(ctx: RunContext[AgentDeps], path: str) -> str:
    """Read one compiled markdown file by relative path, e.g. index.md or wiki/documents/{id}.md."""
    relative = path.lstrip("/")
    if relative.startswith("raw/"):
        raise ModelRetry("raw/ is not searchable")
    try:
        return _corpus(ctx).read(relative)
    except LookupError as exc:
        raise ModelRetry(str(exc)) from exc


async def list_tags(ctx: RunContext[AgentDeps]) -> list[dict[str, Any]]:
    """List tags with explanations."""
    return [
        {"id": tag.id, "name": tag.name, "explanation": tag.explanation}
        for tag in await _knowledge(ctx).list_tags()
    ]


async def list_entries(ctx: RunContext[AgentDeps]) -> list[dict[str, Any]]:
    """List knowledge entries as key/value concepts with tags and linked documents."""
    tags = {tag.id: tag.name for tag in await _knowledge(ctx).list_tags()}
    return [
        {
            "id": entry.id,
            "key": entry.key,
            "value": entry.value,
            "aliases": entry.aliases,
            "tags": [tags[tag_id] for tag_id in entry.tag_ids if tag_id in tags],
            "document_ids": entry.document_ids,
        }
        for entry in await _knowledge(ctx).list_entries()
    ]


async def create_tag(ctx: RunContext[AgentDeps], name: str, explanation: str) -> dict[str, Any]:
    """Queue creating a tag with an explanation."""
    changes = _changes(name=name, explanation=explanation)
    try:
        await _knowledge(ctx).validate_tag_changes(None, changes)
    except ValueError as exc:
        raise ModelRetry(str(exc)) from exc
    ctx.deps.pending.append({"op": "create_tag", "changes": changes})
    return {"queued": True, "op": "create_tag", "name": name}


async def create_entry(
    ctx: RunContext[AgentDeps],
    key: str,
    value: str,
    aliases: list[str] | None = None,
    tag_names: list[str] | None = None,
    document_id: str | None = None,
) -> dict[str, Any]:
    """Queue creating a key/value knowledge entry. Optionally link a document and tags."""
    domain = _knowledge(ctx)
    tag_ids: list[str] = []
    for name in tag_names or []:
        tag = await domain.tag_by_name(name)
        if not tag:
            raise ModelRetry(f"unknown tag: {name}. Create it with create_tag first.")
        tag_ids.append(tag.id)
    changes = _changes(key=key, value=value, aliases=aliases, tag_ids=tag_ids or None)
    if document_id or ctx.deps.context_document_id:
        changes["document_ids"] = [document_id or ctx.deps.context_document_id]
    try:
        await domain.validate_entry_changes(None, changes)
    except ValueError as exc:
        raise ModelRetry(str(exc)) from exc
    ctx.deps.pending.append({"op": "create_entry", "changes": changes})
    return {"queued": True, "op": "create_entry", "key": key}


async def update_entry(
    ctx: RunContext[AgentDeps],
    key: str | None = None,
    entry_id: str | None = None,
    value: str | None = None,
    aliases: list[str] | None = None,
    tag_names: list[str] | None = None,
) -> dict[str, Any]:
    """Queue updates to an existing knowledge entry."""
    domain = _knowledge(ctx)
    entry = await _resolve_entry(ctx, entry_id, key)
    changes = _changes(value=value, aliases=aliases)
    if tag_names is not None:
        tag_ids: list[str] = []
        for name in tag_names:
            tag = await domain.tag_by_name(name)
            if not tag:
                raise ModelRetry(f"unknown tag: {name}")
            tag_ids.append(tag.id)
        changes["tag_ids"] = tag_ids
    if not changes:
        raise ModelRetry("no entry fields to update")
    try:
        await domain.validate_entry_changes(entry.id, changes)
    except ValueError as exc:
        raise ModelRetry(str(exc)) from exc
    ctx.deps.pending.append({"op": "update_entry", "entry_id": entry.id, "changes": changes})
    return {"queued": True, "op": "update_entry", "entry_id": entry.id, "key": entry.key}


async def create_document(
    ctx: RunContext[AgentDeps],
    title: str,
    body: str | None = None,
    tag_names: list[str] | None = None,
) -> dict[str, Any]:
    """Queue creating a markdown document."""
    domain = _knowledge(ctx)
    tag_ids: list[str] = []
    for name in tag_names or []:
        tag = await domain.tag_by_name(name)
        if not tag:
            raise ModelRetry(f"unknown tag: {name}")
        tag_ids.append(tag.id)
    changes = _changes(title=title, body=body, tag_ids=tag_ids or None)
    try:
        await domain.validate_document_changes(None, changes)
    except ValueError as exc:
        raise ModelRetry(str(exc)) from exc
    ctx.deps.pending.append({"op": "create_document", "changes": changes})
    return {"queued": True, "op": "create_document", "title": title}


async def update_document(
    ctx: RunContext[AgentDeps],
    document_id: str | None = None,
    title: str | None = None,
    new_title: str | None = None,
    body: str | None = None,
    tag_names: list[str] | None = None,
) -> dict[str, Any]:
    """Queue updates to a document body, title, or tags. Does not rewrite linked entries."""
    domain = _knowledge(ctx)
    document = await _resolve_document(ctx, document_id, title)
    changes = _changes(title=new_title, body=body)
    if tag_names is not None:
        tag_ids: list[str] = []
        for name in tag_names:
            tag = await domain.tag_by_name(name)
            if not tag:
                raise ModelRetry(f"unknown tag: {name}")
            tag_ids.append(tag.id)
        changes["tag_ids"] = tag_ids
    if not changes:
        raise ModelRetry("no document fields to update")
    try:
        await domain.validate_document_changes(document.id, changes)
    except ValueError as extra:
        raise ModelRetry(str(extra)) from extra
    ctx.deps.pending.append(
        {"op": "update_document", "document_id": document.id, "changes": changes}
    )
    return {
        "queued": True,
        "op": "update_document",
        "document_id": document.id,
        "title": document.title,
    }


async def link_entry(
    ctx: RunContext[AgentDeps],
    entry_key: str | None = None,
    entry_id: str | None = None,
    document_id: str | None = None,
    document_title: str | None = None,
) -> dict[str, Any]:
    """Queue linking an existing entry onto a document node."""
    entry = await _resolve_entry(ctx, entry_id, entry_key)
    document = await _resolve_document(ctx, document_id, document_title)
    ctx.deps.pending.append(
        {"op": "link_entry", "document_id": document.id, "entry_id": entry.id}
    )
    return {
        "queued": True,
        "op": "link_entry",
        "document_id": document.id,
        "entry_id": entry.id,
        "key": entry.key,
    }


def knowledge_ai_contribution() -> ModuleAiContribution:
    return ModuleAiContribution(
        id="knowledge",
        instructions=INSTRUCTIONS,
        tools=(
            search_knowledge,
            read_knowledge,
            list_tags,
            list_entries,
            create_tag,
            create_entry,
            update_entry,
            create_document,
            update_document,
            link_entry,
        ),
    )
