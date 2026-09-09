"""Resolve explicit project references without treating retrieved prose as intent."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectScope:
    name: str
    project_id: str | None = None
    terms: tuple[str, ...] = ()


def mentions(text: str, term: str) -> bool:
    if not term:
        return False
    # Latin identifiers must not match substrings (myai != myai-server).
    boundary = r"[a-zA-Z0-9_-]"
    return bool(re.search(rf"(?<!{boundary}){re.escape(term)}(?!{boundary})", text, re.I))


def project_terms(name: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys((name, *re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", name))))


async def resolve_scope(progress, knowledge, instruction, references):
    projects = await progress.list_projects()
    explicit_ids = {ref.get("id") for ref in references or [] if ref.get("type") == "project"}
    candidates = []
    for project in projects:
        terms = project_terms(project.name)
        if project.id in explicit_ids or any(mentions(instruction, term) for term in terms):
            candidates.append(ProjectScope(project.name, project.id, tuple(dict.fromkeys(terms))))
    if candidates:
        return candidates
    # Existing knowledge tags also establish scope when no Project record exists.
    if knowledge:
        return [
            ProjectScope(tag.name, terms=(tag.name,))
            for tag in await knowledge.list_tags()
            if mentions(instruction, tag.name)
        ]
    return []
