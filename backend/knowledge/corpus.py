from __future__ import annotations

import fnmatch
import re
import shutil
from pathlib import Path
from typing import Any, Protocol

from knowledge.domain import KnowledgeDocument, KnowledgeEntry, KnowledgeTag

AGENTS_MD = """# Knowledge corpus

- Source of truth is the workbench API, not these files.
- Search `index.md` first, then grep `wiki/` only. Never search `raw/`.
- One concept per `wiki/entries/{id}.md`. Documents live in `wiki/documents/{id}.md`.
- Frontmatter: title, tags, aliases, updated. Body is UTF-8 Markdown, one paragraph per line.
"""


def _yaml_list(values: list[str]) -> str:
    return ", ".join(item.replace("\n", " ") for item in values)


def _frontmatter(
    title: str, tags: list[str], updated: str, aliases: list[str] | None = None
) -> str:
    lines = ["---", f"title: {title.replace(chr(10), ' ')}", f"tags: {_yaml_list(tags)}"]
    if aliases:
        lines.append(f"aliases: {_yaml_list(aliases)}")
    lines.append(f"updated: {updated}")
    lines.append("---")
    return "\n".join(lines)


class KnowledgeCorpus(Protocol):
    async def rebuild(
        self,
        tags: list[KnowledgeTag],
        entries: list[KnowledgeEntry],
        documents: list[KnowledgeDocument],
    ) -> None: ...
    async def put_raw(self, document_id: str, filename: str, data: bytes) -> str: ...
    async def delete_raw(self, document_id: str) -> None: ...
    def search(
        self,
        pattern: str,
        glob: str | None = None,
        output_mode: str = "content",
        head_limit: int = 50,
    ) -> list[Any]: ...
    def read(self, relative_path: str) -> str: ...


def compile_files(
    tags: list[KnowledgeTag],
    entries: list[KnowledgeEntry],
    documents: list[KnowledgeDocument],
) -> dict[str, str]:
    tag_names = {tag.id: tag.name for tag in tags}
    entry_keys = {entry.id: entry.key for entry in entries}
    files: dict[str, str] = {"AGENTS.md": AGENTS_MD}
    index_rows = ["path | title | tags | keywords"]
    for tag in tags:
        path = f"wiki/tags/{tag.id}.md"
        names = [tag.name]
        files[path] = (
            f"{_frontmatter(tag.name, names, tag.updated_at.isoformat())}\n\n"
            f"# {tag.name}\n\n{tag.explanation}\n"
        )
        index_rows.append(f"{path} | {tag.name} | {tag.name} | {tag.name}")
    for entry in entries:
        path = f"wiki/entries/{entry.id}.md"
        names = [tag_names[tag_id] for tag_id in entry.tag_ids if tag_id in tag_names]
        aliases = [entry.key, *entry.aliases]
        files[path] = (
            f"{_frontmatter(entry.key, names, entry.updated_at.isoformat(), entry.aliases)}\n\n"
            f"# {entry.key}\n\n{entry.value}\n\n"
            f"aliases: {', '.join(aliases)}\n"
            f"tags: {', '.join(names)}\n"
        )
        index_rows.append(
            f"{path} | {entry.key} | {', '.join(names)} | {', '.join(aliases)}"
        )
    for document in documents:
        path = f"wiki/documents/{document.id}.md"
        names = [tag_names[tag_id] for tag_id in document.tag_ids if tag_id in tag_names]
        linked = [entry_keys[entry_id] for entry_id in document.entry_ids if entry_id in entry_keys]
        files[path] = (
            f"{_frontmatter(document.title, names, document.updated_at.isoformat())}\n\n"
            f"# {document.title}\n\n{document.body}\n\n"
            f"tags: {', '.join(names)}\n"
            f"entries: {', '.join(linked)}\n"
        )
        index_rows.append(
            f"{path} | {document.title} | {', '.join(names)} | "
            f"{document.title}, {', '.join(linked)}"
        )
    files["index.md"] = "\n".join(index_rows) + "\n"
    return files


class MemoryKnowledgeCorpus:
    def __init__(self) -> None:
        self.files: dict[str, str] = {}
        self.raw: dict[str, bytes] = {}

    async def rebuild(
        self,
        tags: list[KnowledgeTag],
        entries: list[KnowledgeEntry],
        documents: list[KnowledgeDocument],
    ) -> None:
        compiled = compile_files(tags, entries, documents)
        self.files = {path: text for path, text in self.files.items() if path.startswith("raw/")}
        self.files.update(compiled)

    async def put_raw(self, document_id: str, filename: str, data: bytes) -> str:
        name = filename.replace("\\", "/").rsplit("/", 1)[-1]
        key = f"raw/documents/{document_id}/{name}"
        prefix = f"raw/documents/{document_id}/"
        self.files = {
            path: text for path, text in self.files.items() if not path.startswith(prefix)
        }
        self.raw = {path: blob for path, blob in self.raw.items() if not path.startswith(prefix)}
        self.raw[key] = data
        return key

    async def delete_raw(self, document_id: str) -> None:
        prefix = f"raw/documents/{document_id}/"
        self.raw = {path: blob for path, blob in self.raw.items() if not path.startswith(prefix)}
        self.files = {
            path: text for path, text in self.files.items() if not path.startswith(prefix)
        }

    def _searchable(self) -> dict[str, str]:
        return {
            path: text
            for path, text in self.files.items()
            if not path.startswith("raw/") and path.endswith(".md")
        }

    def search(
        self,
        pattern: str,
        glob: str | None = None,
        output_mode: str = "content",
        head_limit: int = 50,
    ) -> list[Any]:
        return search_markdown(self._searchable(), pattern, glob, output_mode, head_limit)

    def read(self, relative_path: str) -> str:
        path = relative_path.lstrip("/")
        if path.startswith("raw/"):
            raise LookupError("raw files are not searchable")
        if path not in self.files:
            raise LookupError("knowledge file not found")
        return self.files[path]


class FilesystemKnowledgeCorpus:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def _resolve(self, relative: str) -> Path:
        candidate = (self.root / relative).resolve()
        if not candidate.is_relative_to(self.root):
            raise ValueError("invalid knowledge path")
        return candidate

    async def rebuild(
        self,
        tags: list[KnowledgeTag],
        entries: list[KnowledgeEntry],
        documents: list[KnowledgeDocument],
    ) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        wiki = self.root / "wiki"
        if wiki.exists():
            shutil.rmtree(wiki)
        for relative, text in compile_files(tags, entries, documents).items():
            path = self._resolve(relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    async def put_raw(self, document_id: str, filename: str, data: bytes) -> str:
        name = filename.replace("\\", "/").rsplit("/", 1)[-1]
        folder = self._resolve(f"raw/documents/{document_id}")
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)
        return f"raw/documents/{document_id}/{name}"

    async def delete_raw(self, document_id: str) -> None:
        folder = self._resolve(f"raw/documents/{document_id}")
        if folder.exists():
            shutil.rmtree(folder)

    def _searchable(self) -> dict[str, str]:
        files: dict[str, str] = {}
        if not self.root.exists():
            return files
        for path in self.root.rglob("*.md"):
            relative = path.relative_to(self.root).as_posix()
            if relative.startswith("raw/"):
                continue
            files[relative] = path.read_text(encoding="utf-8")
        return files

    def search(
        self,
        pattern: str,
        glob: str | None = None,
        output_mode: str = "content",
        head_limit: int = 50,
    ) -> list[Any]:
        return search_markdown(self._searchable(), pattern, glob, output_mode, head_limit)

    def read(self, relative_path: str) -> str:
        path = relative_path.lstrip("/")
        if path.startswith("raw/"):
            raise LookupError("raw files are not searchable")
        target = self._resolve(path)
        if not target.is_file():
            raise LookupError("knowledge file not found")
        return target.read_text(encoding="utf-8")


def search_markdown(
    files: dict[str, str],
    pattern: str,
    glob: str | None,
    output_mode: str,
    head_limit: int,
) -> list[Any]:
    try:
        regex = re.compile(pattern, re.I)
    except re.error:
        regex = re.compile(re.escape(pattern), re.I)
    limit = max(1, min(int(head_limit or 50), 200))
    selected = sorted(files)
    if glob:
        selected = [path for path in selected if fnmatch.fnmatch(path, glob)]
    files_with: list[str] = []
    counts: list[dict[str, Any]] = []
    hits: list[dict[str, Any]] = []
    for path in selected:
        matched = [
            {"path": path, "line": index, "text": line}
            for index, line in enumerate(files[path].splitlines(), 1)
            if regex.search(line)
        ]
        if not matched:
            continue
        files_with.append(path)
        counts.append({"path": path, "count": len(matched)})
        hits.extend(matched)
        if output_mode == "content" and len(hits) >= limit:
            return hits[:limit]
        if output_mode != "content" and len(files_with) >= limit:
            break
    if output_mode == "files_with_matches":
        return files_with[:limit]
    if output_mode == "count":
        return counts[:limit]
    return hits[:limit]
