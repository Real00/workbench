from __future__ import annotations

from typing import Any, Literal

from pydantic_ai import ModelRetry, RunContext

from knowledge.corpus import compile_files, search_markdown
from knowledge.domain import KnowledgeDocument, KnowledgeEntry
from pulse.deps import AgentDeps
from pulse.scope import mentions
from shared.ai import ModuleAiContribution

INSTRUCTIONS = (
    "Knowledge module: search the compiled markdown corpus, not Mongo. "
    "Search specific terms over wiki/ first (never raw/); read only relevant matching files. "
    "Use glob like wiki/entries/** or wiki/documents/** to narrow. "
    "Then read_knowledge for the matching file. "
    "Entries are key/value concepts; list_entries returns brief metadata, read files for facts. "
    "Never copy source tags to tasks. Empty scoped results mean evidence is unavailable. "
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


async def _scoped_data(ctx: RunContext[AgentDeps]):
    domain = _knowledge(ctx)
    tags = await domain.list_tags()
    entries = await domain.list_entries()
    documents = await domain.list_documents()
    if not ctx.deps.scopes:
        return tags, entries, documents
    terms = [term for scope in ctx.deps.scopes for term in scope.terms]
    scoped_tag_ids = {
        tag.id for tag in tags if any(tag.name.casefold() == term.casefold() for term in terms)
    }

    def relevant(item, labels):
        return bool(scoped_tag_ids.intersection(item.tag_ids)) or any(
            mentions(label, term) for label in labels for term in terms
        )

    entries = [entry for entry in entries if relevant(entry, [entry.key, *entry.aliases])]
    documents = [doc for doc in documents if relevant(doc, [doc.title])]
    # Linked foreign entries must not leak through the compiled document index.
    from dataclasses import replace

    entry_ids = {entry.id for entry in entries}
    document_ids = {doc.id for doc in documents}
    entries = [
        replace(
            entry, document_ids=[ident for ident in entry.document_ids if ident in document_ids]
        )
        for entry in entries
    ]
    documents = [
        replace(doc, entry_ids=[ident for ident in doc.entry_ids if ident in entry_ids])
        for doc in documents
    ]
    used_tags = scoped_tag_ids | {
        ident for item in [*entries, *documents] for ident in item.tag_ids
    }
    return [tag for tag in tags if tag.id in used_tags], entries, documents


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
    if ctx.deps.scopes:
        files = compile_files(*await _scoped_data(ctx))
        return search_markdown(files, pattern, glob or "wiki/**", output_mode, head_limit)
    return _corpus(ctx).search(pattern, glob or "wiki/**", output_mode, head_limit)


async def read_knowledge(ctx: RunContext[AgentDeps], path: str) -> str:
    """Read one compiled markdown file by relative path, e.g. index.md or wiki/documents/{id}.md."""
    relative = path.lstrip("/")
    if relative.startswith("raw/"):
        raise ModelRetry("raw/ is not searchable")
    if ctx.deps.scopes:
        files = compile_files(*await _scoped_data(ctx))
        if relative not in files:
            raise ModelRetry("file is outside the current scope or does not exist")
        return files[relative]
    try:
        return _corpus(ctx).read(relative)
    except LookupError as exc:
        raise ModelRetry(str(exc)) from exc


async def list_tags(ctx: RunContext[AgentDeps]) -> list[dict[str, Any]]:
    """List tags with explanations."""
    return [
        {"id": tag.id, "name": tag.name, "explanation": tag.explanation}
        for tag in (await _scoped_data(ctx))[0]
    ]


async def list_entries(
    ctx: RunContext[AgentDeps], query: str = "", limit: int = 30
) -> list[dict[str, Any]]:
    """List brief entry metadata. Filter by key/alias; read path for the actual value."""
    tags = {tag.id: tag.name for tag in (await _scoped_data(ctx))[0]}
    return [
        {
            "id": entry.id,
            "key": entry.key,
            "path": f"wiki/entries/{entry.id}.md",
            "aliases": entry.aliases,
            "tags": [tags[tag_id] for tag_id in entry.tag_ids if tag_id in tags],
            "document_ids": entry.document_ids,
        }
        for entry in (await _scoped_data(ctx))[1]
        if not query or query.casefold() in " ".join([entry.key, *entry.aliases]).casefold()
    ][: max(1, min(limit, 100))]


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
    ctx.deps.pending.append({"op": "link_entry", "document_id": document.id, "entry_id": entry.id})
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
