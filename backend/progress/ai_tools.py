from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic_ai import ModelRetry, RunContext

from progress.domain import (
    PRIORITIES,
    STATUSES,
    ProgressDomainService,
    Project,
    Task,
    TeamMember,
    normalize_skills,
)
from pulse.deps import AgentDeps
from shared.ai import ModuleAiContribution

INSTRUCTIONS = (
    "Progress module: problems, blockers, and extra work belong in add_progress_entry, "
    "not a new task. Match existing tasks with list_tasks or get_task before updating. "
    "status must be todo, in_progress, done, or cancelled. "
    "priority must be low, medium, high, or urgent. "
    "Use assignee names exactly as returned by list_members. "
    "The operator member (operator=true) is the logged-in administrator and can be assigned work. "
    "When assigning, match the task to a member's skills and background, "
    "consider open_tasks load, and say briefly why that person fits. "
    "To remember or change a person's title, skills, or project background, "
    "call update_member (or create_member if they do not exist). "
    "To record an observation or evaluation about a person, call record_member_evaluation "
    "(kind: highlight for strengths, risk for concerns, note for everything else). "
    "Projects group related work; tasks may optionally belong to a project via project_id. "
    "To create a project, call create_project; to update its description, background, "
    "started_at, status, or members, call update_project. "
    "Never claim you recorded member information unless that tool queued a change."
)


def _jsonable(value: Any) -> Any:
    if isinstance(value, date):
        return value.isoformat()
    return value


def _compact_task(task: Task, members: dict[str, str] | None = None) -> dict[str, Any]:
    return {
        "id": task.id,
        "title": task.title,
        "status": task.status,
        "priority": task.priority,
        "assignee": (members or {}).get(task.assignee_id or "") if task.assignee_id else None,
        "progress": task.progress,
        "start_date": _jsonable(task.start_date),
        "due_date": _jsonable(task.due_date),
        "tags": task.tags,
        "latest_entry": task.entries[-1].content if task.entries else None,
        "resources": [resource.name for resource in task.resources],
    }


def _changes(**fields: Any) -> dict[str, Any]:
    return {key: _jsonable(value) for key, value in fields.items() if value is not None}


async def _member_id(domain: ProgressDomainService, assignee_name: str | None) -> str | None:
    if not assignee_name:
        return None
    member = await domain.member_by_name(assignee_name)
    if not member:
        raise ModelRetry(f"unknown team member: {assignee_name}")
    return member.id


async def _resolve_task(
    ctx: RunContext[AgentDeps],
    task_id: str | None,
    title_query: str | None,
) -> Task:
    domain = ctx.deps.progress
    ident = task_id or ctx.deps.context_task_id
    if ident:
        try:
            return await domain.get_task(ident)
        except LookupError as exc:
            raise ModelRetry(f"task not found: {ident}") from exc
    if not title_query:
        raise ModelRetry("provide task_id or title_query")
    needle = title_query.strip().casefold()
    tasks = await domain.list_tasks({})
    exact = [task for task in tasks if task.title.casefold() == needle]
    if len(exact) == 1:
        return exact[0]
    contains = [task for task in tasks if needle in task.title.casefold()]
    if len(contains) == 1:
        return contains[0]
    if not contains:
        raise ModelRetry(f"no task matching {title_query!r}")
    names = ", ".join(task.title for task in contains[:6])
    raise ModelRetry(f"multiple matching tasks, be more specific: {names}")


async def list_tasks(ctx: RunContext[AgentDeps]) -> list[dict[str, Any]]:
    """List existing tasks with ids, titles, status, and latest progress."""
    members = {member.id: member.name for member in await ctx.deps.progress.list_members()}
    return [_compact_task(task, members) for task in await ctx.deps.progress.list_tasks({})]


async def list_members(ctx: RunContext[AgentDeps]) -> list[dict[str, Any]]:
    """List assignable members with skills, project background, and current open-task load."""
    open_tasks: dict[str, int] = {}
    for task in await ctx.deps.progress.list_tasks({}):
        if task.assignee_id and task.status in {"todo", "in_progress"}:
            open_tasks[task.assignee_id] = open_tasks.get(task.assignee_id, 0) + 1
    members = [
        member for member in await ctx.deps.progress.list_members() if member.active
    ]
    members.sort(key=lambda member: (not bool(member.user_id), member.name.casefold()))
    return [
        {
            "id": member.id,
            "name": member.name,
            "title": member.title,
            "skills": member.skills,
            "background": member.background,
            "operator": bool(member.user_id),
            "open_tasks": open_tasks.get(member.id, 0),
        }
        for member in members
    ]


async def get_task(
    ctx: RunContext[AgentDeps],
    task_id: str | None = None,
    title_query: str | None = None,
) -> dict[str, Any]:
    """Load one task by id or title."""
    task = await _resolve_task(ctx, task_id, title_query)
    members = {member.id: member.name for member in await ctx.deps.progress.list_members()}
    data = _compact_task(task, members)
    data["description"] = task.description
    data["entries"] = [
        {"kind": entry.kind, "content": entry.content} for entry in task.entries[-8:]
    ]
    return data


async def create_task(
    ctx: RunContext[AgentDeps],
    title: str,
    description: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    assignee_name: str | None = None,
    start_date: date | None = None,
    due_date: date | None = None,
    progress: int | None = None,
    estimated_hours: float | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Queue creating a new task. Nothing is saved until the user confirms."""
    if status and status not in STATUSES:
        raise ModelRetry("status must be todo, in_progress, done, or cancelled")
    if priority and priority not in PRIORITIES:
        raise ModelRetry("priority must be low, medium, high, or urgent")
    changes = _changes(
        title=title,
        description=description,
        status=status,
        priority=priority,
        start_date=start_date,
        due_date=due_date,
        progress=progress,
        estimated_hours=estimated_hours,
        tags=tags,
    )
    assignee_id = await _member_id(ctx.deps.progress, assignee_name)
    if assignee_id:
        changes["assignee_id"] = assignee_id
    try:
        await ctx.deps.progress.validate_changes("create_task", None, changes)
    except ValueError as exc:
        raise ModelRetry(str(exc)) from exc
    ctx.deps.pending.append({"op": "create_task", "changes": changes})
    return {"queued": True, "op": "create_task", "title": title}


async def update_task(
    ctx: RunContext[AgentDeps],
    task_id: str | None = None,
    title_query: str | None = None,
    title: str | None = None,
    description: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    assignee_name: str | None = None,
    start_date: date | None = None,
    due_date: date | None = None,
    progress: int | None = None,
    estimated_hours: float | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Queue field updates on an existing task. Nothing is saved until the user confirms."""
    if status and status not in STATUSES:
        raise ModelRetry("status must be todo, in_progress, done, or cancelled")
    if priority and priority not in PRIORITIES:
        raise ModelRetry("priority must be low, medium, high, or urgent")
    task = await _resolve_task(ctx, task_id, title_query)
    changes = _changes(
        title=title,
        description=description,
        status=status,
        priority=priority,
        start_date=start_date,
        due_date=due_date,
        progress=progress,
        estimated_hours=estimated_hours,
        tags=tags,
    )
    assignee_id = await _member_id(ctx.deps.progress, assignee_name)
    if assignee_id:
        changes["assignee_id"] = assignee_id
    if not changes:
        raise ModelRetry("no fields to update")
    try:
        await ctx.deps.progress.validate_changes("update_task", task.id, changes)
    except ValueError as exc:
        raise ModelRetry(str(exc)) from exc
    ctx.deps.pending.append({"op": "update_task", "task_id": task.id, "changes": changes})
    return {"queued": True, "op": "update_task", "task_id": task.id, "title": task.title}


async def add_progress_entry(
    ctx: RunContext[AgentDeps],
    kind: Literal["update", "blocker", "extra_work"],
    content: str,
    task_id: str | None = None,
    title_query: str | None = None,
) -> dict[str, Any]:
    """Queue a progress note, blocker, or extra-work record on an existing task."""
    task = await _resolve_task(ctx, task_id, title_query)
    entry = {"kind": kind, "content": content.strip()}
    if not entry["content"]:
        raise ModelRetry("progress entry content is required")
    try:
        await ctx.deps.progress.validate_changes("update_task", task.id, {}, entry)
    except ValueError as exc:
        raise ModelRetry(str(exc)) from exc
    ctx.deps.pending.append({"op": "add_entry", "task_id": task.id, "entry": entry})
    return {
        "queued": True,
        "op": "add_entry",
        "task_id": task.id,
        "title": task.title,
        "kind": kind,
    }


async def _resolve_member(
    ctx: RunContext[AgentDeps],
    member_id: str | None,
    name: str | None,
) -> TeamMember:
    if member_id:
        try:
            return await ctx.deps.progress.get_member(member_id)
        except LookupError as exc:
            raise ModelRetry(f"member not found: {member_id}") from exc
    if not name or not name.strip():
        raise ModelRetry("provide member name")
    member = await ctx.deps.progress.member_by_name(name.strip())
    if not member:
        raise ModelRetry(
            f"unknown team member: {name.strip()}. Use create_member if this is a new person."
        )
    return member


async def create_member(
    ctx: RunContext[AgentDeps],
    name: str,
    title: str | None = None,
    skills: list[str] | None = None,
    background: str | None = None,
) -> dict[str, Any]:
    """Queue creating a team member. Nothing is saved until the user confirms."""
    changes = _changes(name=name, title=title, skills=skills, background=background)
    if "name" not in changes:
        raise ModelRetry("member name is required")
    try:
        await ctx.deps.progress.validate_member_changes(None, changes)
    except ValueError as exc:
        raise ModelRetry(str(exc)) from exc
    ctx.deps.pending.append({"op": "create_member", "changes": changes})
    return {"queued": True, "op": "create_member", "name": changes["name"]}


async def update_member(
    ctx: RunContext[AgentDeps],
    name: str | None = None,
    member_id: str | None = None,
    title: str | None = None,
    skills: list[str] | None = None,
    add_skills: list[str] | None = None,
    background: str | None = None,
) -> dict[str, Any]:
    """Queue updates to a member's title, skills, or project background."""
    member = await _resolve_member(ctx, member_id, name)
    changes = _changes(title=title, background=background)
    if skills is not None:
        changes["skills"] = skills
    elif add_skills:
        try:
            changes["skills"] = normalize_skills([*member.skills, *add_skills])
        except ValueError as exc:
            raise ModelRetry(str(exc)) from exc
    if not changes:
        raise ModelRetry("no member fields to update")
    try:
        await ctx.deps.progress.validate_member_changes(member.id, changes)
    except ValueError as exc:
        raise ModelRetry(str(exc)) from exc
    ctx.deps.pending.append(
        {"op": "update_member", "member_id": member.id, "changes": changes}
    )
    return {
        "queued": True,
        "op": "update_member",
        "member_id": member.id,
        "name": member.name,
    }


async def record_member_evaluation(
    ctx: RunContext[AgentDeps],
    kind: Literal["highlight", "risk", "note"],
    content: str,
    name: str | None = None,
    member_id: str | None = None,
) -> dict[str, Any]:
    """Queue an evaluation (highlight, risk, or note) about a team member."""
    member = await _resolve_member(ctx, member_id, name)
    evaluation = {"kind": kind, "content": content.strip()}
    if not evaluation["content"]:
        raise ModelRetry("member evaluation content is required")
    ctx.deps.pending.append(
        {"op": "add_member_evaluation", "member_id": member.id, "evaluation": evaluation}
    )
    return {
        "queued": True,
        "op": "add_member_evaluation",
        "member_id": member.id,
        "name": member.name,
        "kind": kind,
    }


async def _resolve_project(
    ctx: RunContext[AgentDeps],
    project_id: str | None,
    name: str | None,
) -> Project:
    if project_id:
        try:
            return await ctx.deps.progress.get_project(project_id)
        except LookupError as exc:
            raise ModelRetry(f"project not found: {project_id}") from exc
    if not name or not name.strip():
        raise ModelRetry("provide project name")
    project = await ctx.deps.progress.project_by_name(name.strip())
    if not project:
        raise ModelRetry(
            f"unknown project: {name.strip()}. Use create_project if this is a new project."
        )
    return project


async def _resolve_member_ids(
    ctx: RunContext[AgentDeps],
    member_names: list[str],
) -> list[str]:
    ids: list[str] = []
    for member_name in member_names:
        member = await ctx.deps.progress.member_by_name(member_name.strip())
        if not member:
            raise ModelRetry(f"unknown team member: {member_name}")
        if member.id not in ids:
            ids.append(member.id)
    return ids


async def create_project(
    ctx: RunContext[AgentDeps],
    name: str,
    description: str | None = None,
    background: str | None = None,
    started_at: date | None = None,
    status: Literal["planning", "active", "completed", "archived"] | None = None,
    member_names: list[str] | None = None,
) -> dict[str, Any]:
    """Queue creating a project. Nothing is saved until the user confirms."""
    changes = _changes(
        name=name,
        description=description,
        background=background,
        started_at=started_at,
        status=status,
    )
    if "name" not in changes:
        raise ModelRetry("project name is required")
    if member_names:
        changes["member_ids"] = await _resolve_member_ids(ctx, member_names)
    try:
        await ctx.deps.progress.validate_project_changes(None, changes)
    except ValueError as exc:
        raise ModelRetry(str(exc)) from exc
    ctx.deps.pending.append({"op": "create_project", "changes": changes})
    return {"queued": True, "op": "create_project", "name": changes["name"]}


async def update_project(
    ctx: RunContext[AgentDeps],
    name: str | None = None,
    project_id: str | None = None,
    description: str | None = None,
    background: str | None = None,
    started_at: date | None = None,
    status: Literal["planning", "active", "completed", "archived"] | None = None,
    add_members: list[str] | None = None,
    remove_members: list[str] | None = None,
) -> dict[str, Any]:
    """Queue updates to a project's info, status, or members. Nothing is saved until the user confirms."""
    project = await _resolve_project(ctx, project_id, name)
    changes = _changes(
        description=description,
        background=background,
        started_at=started_at,
        status=status,
    )
    member_ids = list(project.member_ids)
    members_changed = False
    if add_members:
        for member_id in await _resolve_member_ids(ctx, add_members):
            if member_id not in member_ids:
                member_ids.append(member_id)
                members_changed = True
    if remove_members:
        for member_id in await _resolve_member_ids(ctx, remove_members):
            if member_id in member_ids:
                member_ids.remove(member_id)
                members_changed = True
    if members_changed:
        changes["member_ids"] = member_ids
    if not changes:
        raise ModelRetry("no project fields to update")
    try:
        await ctx.deps.progress.validate_project_changes(project.id, changes)
    except ValueError as exc:
        raise ModelRetry(str(exc)) from exc
    ctx.deps.pending.append(
        {"op": "update_project", "project_id": project.id, "changes": changes}
    )
    return {
        "queued": True,
        "op": "update_project",
        "project_id": project.id,
        "name": project.name,
    }


def progress_ai_contribution() -> ModuleAiContribution:
    return ModuleAiContribution(
        id="progress",
        instructions=INSTRUCTIONS,
        tools=(
            list_tasks,
            list_members,
            get_task,
            create_task,
            update_task,
            add_progress_entry,
            create_member,
            update_member,
            record_member_evaluation,
            create_project,
            update_project,
        ),
    )
