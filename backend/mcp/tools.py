"""MCP 工具注册表：把工作台领域服务映射为 MCP tools。

每个工具声明 annotations（readOnlyHint 等，2025-06-18+ 规范），
handler 直接调用领域服务——与站内 Pulse 相同的校验逻辑，
区别在于 MCP 调用立即生效（没有站内的排队确认环节）。
"""

from dataclasses import asdict, dataclass
from typing import Any, Awaitable, Callable

from aiohttp import web

from progress.domain import ProgressDomainService
from shared.web_keys import KNOWLEDGE, PROGRESS

READ_ANNOTATIONS = {"readOnlyHint": True, "idempotentHint": True}
WRITE_ANNOTATIONS = {"readOnlyHint": False, "destructiveHint": False}

DATE_SCHEMA = {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"}


def _progress(request: web.Request) -> ProgressDomainService:
    return request.app[PROGRESS].domain


def _knowledge(request: web.Request):
    return request.app[KNOWLEDGE].domain


def _knowledge_app(request: web.Request):
    return request.app[KNOWLEDGE]


@dataclass
class McpTool:
    name: str
    title: str
    description: str
    input_schema: dict[str, Any]
    annotations: dict[str, Any]
    handler: Callable[[web.Request, str, dict[str, Any]], Awaitable[Any]]
    # 写工具标注变更影响的数据域，成功执行后据此向 SSE 总线广播（None = 只读不广播）
    scope: str | None = None


async def _resolve_task(domain: ProgressDomainService, args: dict[str, Any]):
    task_id = args.get("task_id")
    title_query = args.get("title_query")
    if task_id:
        return await domain.get_task(str(task_id))
    if title_query:
        needle = str(title_query).strip().casefold()
        tasks = await domain.list_tasks({})
        exact = [task for task in tasks if task.title.casefold() == needle]
        if len(exact) == 1:
            return exact[0]
        contains = [task for task in tasks if needle in task.title.casefold()]
        if len(contains) == 1:
            return contains[0]
        if not contains:
            raise ValueError(f"no task matching {title_query!r}")
        raise ValueError(f"multiple tasks match {title_query!r}, be more specific")
    raise ValueError("provide task_id or title_query")


async def _resolve_member(domain: ProgressDomainService, args: dict[str, Any]):
    member_id = args.get("member_id")
    name = args.get("name")
    if member_id:
        return await domain.get_member(str(member_id))
    if name:
        member = await domain.member_by_name(str(name))
        if not member:
            raise ValueError(f"unknown member: {name}")
        return member
    raise ValueError("provide member_id or name")


async def _resolve_project(domain: ProgressDomainService, args: dict[str, Any]):
    project_id = args.get("project_id")
    name = args.get("name")
    if project_id:
        return await domain.get_project(str(project_id))
    if name:
        project = await domain.project_by_name(str(name))
        if not project:
            raise ValueError(f"unknown project: {name}")
        return project
    raise ValueError("provide project_id or name")


async def _member_ids(domain: ProgressDomainService, names: list[str]) -> list[str]:
    ids: list[str] = []
    for name in names:
        member = await domain.member_by_name(str(name))
        if not member:
            raise ValueError(f"unknown member: {name}")
        if member.id not in ids:
            ids.append(member.id)
    return ids


async def h_list_tasks(request: web.Request, actor: str, args: dict[str, Any]) -> Any:
    domain = _progress(request)
    filters = {"status": args["status"]} if args.get("status") else {}
    tasks = await domain.list_tasks(filters)
    return {"tasks": [
        {
            "id": task.id,
            "title": task.title,
            "status": task.status,
            "priority": task.priority,
            "assignee_id": task.assignee_id,
            "project_id": task.project_id,
            "progress": task.progress,
            "start_date": task.start_date.isoformat() if task.start_date else None,
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "tags": task.tags,
        }
        for task in tasks
    ]}


async def h_get_task(request: web.Request, actor: str, args: dict[str, Any]) -> Any:
    task = await _resolve_task(_progress(request), args)
    data = asdict(task)
    data["start_date"] = task.start_date.isoformat() if task.start_date else None
    data["due_date"] = task.due_date.isoformat() if task.due_date else None
    return {"task": data}


async def h_create_task(request: web.Request, actor: str, args: dict[str, Any]) -> Any:
    data: dict[str, Any] = {
        key: args[key]
        for key in (
            "title", "description", "status", "priority", "assignee_id", "project_id",
            "start_date", "due_date", "estimated_hours", "tags",
        )
        if key in args
    }
    task = await _progress(request).create(data, actor)
    return {"task": asdict(task)}


async def h_update_task(request: web.Request, actor: str, args: dict[str, Any]) -> Any:
    payload: dict[str, Any] = {
        key: args[key]
        for key in (
            "title", "description", "status", "priority", "assignee_id", "project_id",
            "start_date", "due_date", "progress", "estimated_hours", "tags",
        )
        if key in args
    }
    entry = args.get("add_entry")
    task = await _progress(request).update(str(args["task_id"]), {**payload, **({"add_entry": entry} if entry else {})})
    return {"task": asdict(task)}


async def h_add_progress_entry(request: web.Request, actor: str, args: dict[str, Any]) -> Any:
    task_id = str(args.get("task_id") or "")
    task = await _progress(request).update(
        task_id, {"add_entry": {"kind": args["kind"], "content": args["content"]}}
    )
    return {"task": asdict(task)}


async def h_list_members(request: web.Request, actor: str, args: dict[str, Any]) -> Any:
    domain = _progress(request)
    tasks = await domain.list_tasks({})
    open_counts: dict[str, int] = {}
    for task in tasks:
        if task.assignee_id and task.status in {"todo", "in_progress"}:
            open_counts[task.assignee_id] = open_counts.get(task.assignee_id, 0) + 1
    members = [
        {
            "id": member.id,
            "name": member.name,
            "title": member.title,
            "skills": member.skills,
            "background": member.background,
            "active": member.active,
            "operator": bool(member.user_id),
            "open_tasks": open_counts.get(member.id, 0),
        }
        for member in await domain.list_members()
    ]
    return {"members": members}


async def h_create_member(request: web.Request, actor: str, args: dict[str, Any]) -> Any:
    member = await _progress(request).create_member({key: args[key] for key in ("name", "title", "skills", "background") if key in args})
    from progress.application import public_member
    return {"member": public_member(member)}


async def h_update_member(request: web.Request, actor: str, args: dict[str, Any]) -> Any:
    member = await _resolve_member(_progress(request), args)
    payload: dict[str, Any] = {key: args[key] for key in ("title", "skills", "background", "active", "name", "color") if key in args}
    updated = await _progress(request).update_member(member.id, payload)
    from progress.application import public_member
    return {"member": public_member(updated)}


async def h_record_member_evaluation(request: web.Request, actor: str, args: dict[str, Any]) -> Any:
    member = await _resolve_member(_progress(request), args)
    updated = await _progress(request).add_member_evaluation(member.id, args["kind"], args["content"])
    from progress.application import public_member
    return {"member": public_member(updated)}


async def h_list_projects(request: web.Request, actor: str, args: dict[str, Any]) -> Any:
    projects = await _progress(request).list_projects()
    return {"projects": [
        {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "status": project.status,
            "started_at": project.started_at.isoformat() if project.started_at else None,
            "member_ids": project.member_ids,
        }
        for project in projects
    ]}


async def h_create_project(request: web.Request, actor: str, args: dict[str, Any]) -> Any:
    project = await _progress(request).create_project({
        key: args[key]
        for key in ("name", "description", "background", "started_at", "status", "member_ids")
        if key in args
    })
    return {"project": asdict(project)}


async def h_update_project(request: web.Request, actor: str, args: dict[str, Any]) -> Any:
    domain = _progress(request)
    project = await _resolve_project(domain, args)
    payload: dict[str, Any] = {
        key: args[key]
        for key in ("name", "description", "background", "started_at", "status", "cover_color")
        if key in args
    }
    member_ids = list(project.member_ids)
    members_changed = False
    if args.get("add_member_names"):
        for member_id in await _member_ids(domain, args["add_member_names"]):
            if member_id not in member_ids:
                member_ids.append(member_id)
                members_changed = True
    if args.get("remove_member_names"):
        for member_id in await _member_ids(domain, args["remove_member_names"]):
            if member_id in member_ids:
                member_ids.remove(member_id)
                members_changed = True
    if members_changed:
        payload["member_ids"] = member_ids
    updated = await domain.update_project(project.id, payload)
    return {"project": asdict(updated)}


async def h_list_tags(request: web.Request, actor: str, args: dict[str, Any]) -> Any:
    tags = await _knowledge(request).list_tags()
    return {"tags": [{"id": tag.id, "name": tag.name, "explanation": tag.explanation} for tag in tags]}


async def h_list_entries(request: web.Request, actor: str, args: dict[str, Any]) -> Any:
    domain = _knowledge(request)
    tags = {tag.id: tag.name for tag in await domain.list_tags()}
    entries = await domain.list_entries()
    return {"entries": [
        {
            "id": entry.id,
            "key": entry.key,
            "value": entry.value,
            "aliases": entry.aliases,
            "tags": [tags[tag_id] for tag_id in entry.tag_ids if tag_id in tags],
            "document_ids": entry.document_ids,
        }
        for entry in entries
    ]}


async def h_search_knowledge(request: web.Request, actor: str, args: dict[str, Any]) -> Any:
    corpus = _knowledge_app(request).corpus
    results = corpus.search(
        str(args["pattern"]),
        args.get("glob"),
        args.get("output_mode", "content"),
        int(args.get("head_limit", 50)),
    )
    return {"results": results}


async def h_read_knowledge(request: web.Request, actor: str, args: dict[str, Any]) -> Any:
    return {"path": args["path"], "content": _knowledge_app(request).corpus.read(str(args["path"]).lstrip("/"))}


async def h_create_tag(request: web.Request, actor: str, args: dict[str, Any]) -> Any:
    tag = await _knowledge_app(request).create_tag({"name": args["name"], "explanation": args["explanation"]})
    return {"tag": {"id": tag.id, "name": tag.name, "explanation": tag.explanation}}


async def h_create_entry(request: web.Request, actor: str, args: dict[str, Any]) -> Any:
    domain = _knowledge(request)
    tag_ids: list[str] = []
    for name in args.get("tag_names") or []:
        tag = await domain.tag_by_name(str(name))
        if not tag:
            raise ValueError(f"unknown tag: {name}. Create it with create_tag first.")
        tag_ids.append(tag.id)
    data = {"key": args["key"], "value": args["value"]}
    if args.get("aliases") is not None:
        data["aliases"] = args["aliases"]
    if tag_ids:
        data["tag_ids"] = tag_ids
    if args.get("document_ids"):
        data["document_ids"] = args["document_ids"]
    entry = await _knowledge_app(request).create_entry(data)
    return {"entry": {"id": entry.id, "key": entry.key, "value": entry.value}}


async def h_update_entry(request: web.Request, actor: str, args: dict[str, Any]) -> Any:
    domain = _knowledge(request)
    entry_id = args.get("entry_id")
    if not entry_id and args.get("key"):
        entry = await domain.by_key(str(args["key"]))
        if not entry:
            raise ValueError(f"unknown entry key: {args['key']}")
        entry_id = entry.id
    if not entry_id:
        raise ValueError("provide entry_id or key")
    data: dict[str, Any] = {}
    if args.get("value") is not None:
        data["value"] = args["value"]
    if args.get("aliases") is not None:
        data["aliases"] = args["aliases"]
    if args.get("tag_names") is not None:
        tag_ids: list[str] = []
        for name in args["tag_names"]:
            tag = await domain.tag_by_name(str(name))
            if not tag:
                raise ValueError(f"unknown tag: {name}")
            tag_ids.append(tag.id)
        data["tag_ids"] = tag_ids
    entry = await _knowledge_app(request).update_entry(str(entry_id), data)
    return {"entry": {"id": entry.id, "key": entry.key, "value": entry.value}}


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "object", "properties": properties, "additionalProperties": False}
    if required:
        schema["required"] = required
    return schema


TOOLS: list[McpTool] = [
    McpTool("list_tasks", "列出任务", "List workbench tasks, optionally filtered by status.",
            _schema({"status": {"type": "string", "enum": ["todo", "in_progress", "done", "cancelled"]}}), READ_ANNOTATIONS, h_list_tasks),
    McpTool("get_task", "读取任务详情", "Get one task by task_id or unique title_query; includes description and progress entries.",
            _schema({"task_id": {"type": "string"}, "title_query": {"type": "string"}}), READ_ANNOTATIONS, h_get_task),
    McpTool("create_task", "创建任务", "Create a task. status/todo, priority/medium by default.",
            _schema({
                "title": {"type": "string"}, "description": {"type": "string"},
                "status": {"type": "string", "enum": ["todo", "in_progress", "done", "cancelled"]},
                "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
                "assignee_id": {"type": "string"}, "project_id": {"type": "string"},
                "start_date": DATE_SCHEMA, "due_date": DATE_SCHEMA,
                "estimated_hours": {"type": "number"}, "tags": {"type": "array", "items": {"type": "string"}},
            }, ["title"]), WRITE_ANNOTATIONS, h_create_task, scope="progress"),
    McpTool("update_task", "更新任务", "Update task fields by task_id (or unique title_query); add_entry appends a progress note.",
            _schema({
                "task_id": {"type": "string"}, "title_query": {"type": "string"},
                "title": {"type": "string"}, "description": {"type": "string"},
                "status": {"type": "string", "enum": ["todo", "in_progress", "done", "cancelled"]},
                "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
                "assignee_id": {"type": "string"}, "project_id": {"type": "string"},
                "start_date": DATE_SCHEMA, "due_date": DATE_SCHEMA,
                "progress": {"type": "integer", "minimum": 0, "maximum": 100},
                "estimated_hours": {"type": "number"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "add_entry": {"type": "object", "properties": {"kind": {"type": "string", "enum": ["update", "blocker", "extra_work"]}, "content": {"type": "string"}}, "required": ["kind", "content"]},
            }), WRITE_ANNOTATIONS, h_update_task, scope="progress"),
    McpTool("add_progress_entry", "追加进度记录", "Append a progress note (update/blocker/extra_work) to a task.",
            _schema({
                "task_id": {"type": "string"}, "title_query": {"type": "string"},
                "kind": {"type": "string", "enum": ["update", "blocker", "extra_work"]},
                "content": {"type": "string"},
            }, ["kind", "content"]), WRITE_ANNOTATIONS, h_add_progress_entry, scope="progress"),
    McpTool("list_members", "列出成员", "List team members with skills, background, and activity.",
            _schema({}), READ_ANNOTATIONS, h_list_members),
    McpTool("create_member", "创建成员", "Create a team member with name, title, skills, background.",
            _schema({"name": {"type": "string"}, "title": {"type": "string"}, "skills": {"type": "array", "items": {"type": "string"}}, "background": {"type": "string"}}, ["name"]),
            WRITE_ANNOTATIONS, h_create_member, scope="progress"),
    McpTool("update_member", "更新成员", "Update a member's title/skills/background/active by member_id or name.",
            _schema({
                "member_id": {"type": "string"}, "name": {"type": "string"},
                "title": {"type": "string"}, "skills": {"type": "array", "items": {"type": "string"}},
                "background": {"type": "string"}, "active": {"type": "boolean"}, "color": {"type": "string"},
            }), WRITE_ANNOTATIONS, h_update_member, scope="progress"),
    McpTool("record_member_evaluation", "记录成员评价", "Append an evaluation (highlight/risk/note) about a team member.",
            _schema({
                "member_id": {"type": "string"}, "name": {"type": "string"},
                "kind": {"type": "string", "enum": ["highlight", "risk", "note"]},
                "content": {"type": "string"},
            }, ["kind", "content"]), WRITE_ANNOTATIONS, h_record_member_evaluation, scope="progress"),
    McpTool("list_projects", "列出项目", "List projects with status and members.",
            _schema({}), READ_ANNOTATIONS, h_list_projects),
    McpTool("create_project", "创建项目", "Create a project with name, description, background, started_at, status, member_ids.",
            _schema({
                "name": {"type": "string"}, "description": {"type": "string"}, "background": {"type": "string"},
                "started_at": DATE_SCHEMA,
                "status": {"type": "string", "enum": ["planning", "active", "completed", "archived"]},
                "member_ids": {"type": "array", "items": {"type": "string"}},
            }, ["name"]), WRITE_ANNOTATIONS, h_create_project, scope="progress"),
    McpTool("update_project", "更新项目", "Update project info/status; add or remove members by name via add_member_names/remove_member_names.",
            _schema({
                "project_id": {"type": "string"}, "name": {"type": "string"},
                "description": {"type": "string"}, "background": {"type": "string"},
                "started_at": DATE_SCHEMA,
                "status": {"type": "string", "enum": ["planning", "active", "completed", "archived"]},
                "cover_color": {"type": "string"},
                "add_member_names": {"type": "array", "items": {"type": "string"}},
                "remove_member_names": {"type": "array", "items": {"type": "string"}},
            }), WRITE_ANNOTATIONS, h_update_project, scope="progress"),
    McpTool("list_tags", "列出知识标签", "List knowledge tags with explanations.",
            _schema({}), READ_ANNOTATIONS, h_list_tags),
    McpTool("list_entries", "列出知识条目", "List knowledge entries as key/value concepts with tags and linked documents.",
            _schema({}), READ_ANNOTATIONS, h_list_entries),
    McpTool("search_knowledge", "搜索知识库", "Grep compiled knowledge markdown. Prefer index.md then wiki/; raw/ is not searchable.",
            _schema({
                "pattern": {"type": "string"},
                "glob": {"type": "string"},
                "output_mode": {"type": "string", "enum": ["content", "files_with_matches", "count"]},
                "head_limit": {"type": "integer", "minimum": 1, "maximum": 200},
            }, ["pattern"]), READ_ANNOTATIONS, h_search_knowledge),
    McpTool("read_knowledge", "阅读知识文件", "Read one compiled markdown file by relative path, e.g. index.md or wiki/documents/{id}.md.",
            _schema({"path": {"type": "string"}}, ["path"]), READ_ANNOTATIONS, h_read_knowledge),
    McpTool("create_tag", "创建知识标签", "Create a knowledge tag with an explanation.",
            _schema({"name": {"type": "string"}, "explanation": {"type": "string"}}, ["name", "explanation"]),
            WRITE_ANNOTATIONS, h_create_tag, scope="knowledge"),
    McpTool("create_entry", "创建知识条目", "Create a key/value knowledge entry; optionally link tags by name and documents by id.",
            _schema({
                "key": {"type": "string"}, "value": {"type": "string"},
                "aliases": {"type": "array", "items": {"type": "string"}},
                "tag_names": {"type": "array", "items": {"type": "string"}},
                "document_ids": {"type": "array", "items": {"type": "string"}},
            }, ["key", "value"]), WRITE_ANNOTATIONS, h_create_entry, scope="knowledge"),
    McpTool("update_entry", "更新知识条目", "Update an existing entry's value/aliases/tags by entry_id or key.",
            _schema({
                "entry_id": {"type": "string"}, "key": {"type": "string"},
                "value": {"type": "string"}, "aliases": {"type": "array", "items": {"type": "string"}},
                "tag_names": {"type": "array", "items": {"type": "string"}},
            }), WRITE_ANNOTATIONS, h_update_entry, scope="knowledge"),
]

TOOL_MAP = {tool.name: tool for tool in TOOLS}