from typing import Any, Literal
from urllib.parse import quote

from aiohttp import web
from aiohttp.multipart import BodyPartReader
from pydantic import BaseModel, Field

from api.http import body, response
from pulse.routes import confirm_ai_task, run_ai_task
from shared.web_keys import ACTOR, PROGRESS


class MemberCreateInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    title: str = Field(default="", max_length=100)
    active: bool = True
    color: str | None = Field(default=None, max_length=32)
    skills: list[str] = []
    background: str = Field(default="", max_length=2000)


class MemberUpdateInput(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    title: str | None = Field(default=None, max_length=100)
    active: bool | None = None
    color: str | None = Field(default=None, max_length=32)
    skills: list[str] | None = None
    background: str | None = Field(default=None, max_length=2000)


class MemberEvaluationInput(BaseModel):
    kind: Literal["highlight", "risk", "note"]
    content: str = Field(min_length=1, max_length=2000)


class ProjectInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    background: str = Field(default="", max_length=2000)
    started_at: str | None = None
    member_ids: list[str] = []
    status: Literal["planning", "active", "completed", "archived"] = "planning"
    cover_color: str | None = Field(default=None, max_length=32)


class ProjectUpdateInput(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    background: str | None = Field(default=None, max_length=2000)
    started_at: str | None = None
    member_ids: list[str] | None = None
    status: Literal["planning", "active", "completed", "archived"] | None = None
    cover_color: str | None = Field(default=None, max_length=32)


class ProgressEntryInput(BaseModel):
    kind: Literal["update", "blocker", "extra_work"]
    content: str = Field(min_length=1, max_length=2000)


class TaskInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    status: Literal["todo", "in_progress", "done", "cancelled"] = "todo"
    priority: Literal["low", "medium", "high", "urgent"] = "medium"
    assignee_id: str | None = None
    project_id: str | None = None
    start_date: str | None = None
    due_date: str | None = None
    progress: int = Field(default=0, ge=0, le=100)
    estimated_hours: float | None = Field(default=None, ge=0)
    tags: list[str] = []
    add_entry: ProgressEntryInput | None = None


class TaskUpdateInput(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    status: Literal["todo", "in_progress", "done", "cancelled"] | None = None
    priority: Literal["low", "medium", "high", "urgent"] | None = None
    assignee_id: str | None = None
    project_id: str | None = None
    start_date: str | None = None
    due_date: str | None = None
    progress: int | None = Field(default=None, ge=0, le=100)
    estimated_hours: float | None = Field(default=None, ge=0)
    tags: list[str] | None = None
    add_entry: ProgressEntryInput | None = None


class ResourceLinkInput(BaseModel):
    name: str = Field(default="", max_length=200)
    url: str = Field(min_length=1, max_length=2000)


async def list_members(request: web.Request) -> web.Response:
    return response(await request.app[PROGRESS].list_members())


async def create_member(request: web.Request) -> web.Response:
    return response(
        await request.app[PROGRESS].create_member(await body(request, MemberCreateInput)), 201
    )


async def update_member(request: web.Request) -> web.Response:
    result = await request.app[PROGRESS].update_member(
        request.match_info["member_id"], await body(request, MemberUpdateInput)
    )
    return response(result)


async def delete_member(request: web.Request) -> web.Response:
    await request.app[PROGRESS].delete_member(request.match_info["member_id"])
    return response({"ok": True})


async def add_member_evaluation(request: web.Request) -> web.Response:
    payload = await body(request, MemberEvaluationInput)
    result = await request.app[PROGRESS].add_member_evaluation(
        request.match_info["member_id"], payload["kind"], payload["content"]
    )
    return response(result, 201)


async def delete_member_evaluation(request: web.Request) -> web.Response:
    result = await request.app[PROGRESS].remove_member_evaluation(
        request.match_info["member_id"], request.match_info["evaluation_id"]
    )
    return response(result)


async def list_projects(request: web.Request) -> web.Response:
    return response(await request.app[PROGRESS].list_projects())


async def create_project(request: web.Request) -> web.Response:
    return response(
        await request.app[PROGRESS].create_project(await body(request, ProjectInput)), 201
    )


async def update_project(request: web.Request) -> web.Response:
    result = await request.app[PROGRESS].update_project(
        request.match_info["project_id"], await body(request, ProjectUpdateInput)
    )
    return response(result)


async def delete_project(request: web.Request) -> web.Response:
    await request.app[PROGRESS].delete_project(request.match_info["project_id"])
    return response({"ok": True})


async def list_tasks(request: web.Request) -> web.Response:
    filters: dict[str, Any] = dict(request.query)
    return response(await request.app[PROGRESS].list_tasks(filters))


async def get_task(request: web.Request) -> web.Response:
    return response(await request.app[PROGRESS].get_task(request.match_info["task_id"]))


async def create_task(request: web.Request) -> web.Response:
    result = await request.app[PROGRESS].create_task(
        await body(request, TaskInput), request[ACTOR]["sub"]
    )
    return response(result, 201)


async def update_task(request: web.Request) -> web.Response:
    result = await request.app[PROGRESS].update_task(
        request.match_info["task_id"], await body(request, TaskUpdateInput)
    )
    return response(result)


async def delete_task(request: web.Request) -> web.Response:
    await request.app[PROGRESS].delete_task(request.match_info["task_id"])
    return response({"ok": True})


async def _read_upload(request: web.Request) -> tuple[str, bytes]:
    reader = await request.multipart()
    field = await reader.next()
    if not isinstance(field, BodyPartReader) or field.name != "file":
        raise ValueError("file is required")
    filename = field.filename or ""
    data = await field.read(decode=False)
    return filename, data


async def upload_task_file(request: web.Request) -> web.Response:
    filename, data = await _read_upload(request)
    result = await request.app[PROGRESS].attach_file(
        request.match_info["task_id"], filename, data
    )
    return response(result, 201)


async def add_task_link(request: web.Request) -> web.Response:
    payload = await body(request, ResourceLinkInput)
    result = await request.app[PROGRESS].attach_link(
        request.match_info["task_id"], payload.get("name") or "", payload["url"]
    )
    return response(result, 201)


async def delete_task_resource(request: web.Request) -> web.Response:
    result = await request.app[PROGRESS].detach_resource(
        request.match_info["task_id"], request.match_info["resource_id"]
    )
    return response(result)


async def download_task_resource(request: web.Request) -> web.StreamResponse:
    stored = await request.app[PROGRESS].open_resource_file(
        request.match_info["task_id"], request.match_info["resource_id"]
    )
    disposition = "inline" if stored.inline else "attachment"
    headers = {
        "Content-Type": stored.content_type,
        "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(stored.filename)}",
    }
    if stored.path:
        return web.FileResponse(stored.path, headers=headers)
    return web.Response(body=stored.data or b"", headers=headers)


async def dashboard(request: web.Request) -> web.Response:
    return response(await request.app[PROGRESS].dashboard())


def register_routes(app: web.Application) -> None:
    prefix = "/api/v1/progress"
    app.router.add_get(f"{prefix}/members", list_members)
    app.router.add_post(f"{prefix}/members", create_member)
    app.router.add_patch(f"{prefix}/members/{{member_id}}", update_member)
    app.router.add_delete(f"{prefix}/members/{{member_id}}", delete_member)
    app.router.add_post(f"{prefix}/members/{{member_id}}/evaluations", add_member_evaluation)
    app.router.add_delete(
        f"{prefix}/members/{{member_id}}/evaluations/{{evaluation_id}}", delete_member_evaluation
    )
    app.router.add_get(f"{prefix}/projects", list_projects)
    app.router.add_post(f"{prefix}/projects", create_project)
    app.router.add_patch(f"{prefix}/projects/{{project_id}}", update_project)
    app.router.add_delete(f"{prefix}/projects/{{project_id}}", delete_project)
    app.router.add_get(f"{prefix}/tasks", list_tasks)
    app.router.add_post(f"{prefix}/tasks", create_task)
    app.router.add_get(f"{prefix}/tasks/{{task_id}}", get_task)
    app.router.add_patch(f"{prefix}/tasks/{{task_id}}", update_task)
    app.router.add_delete(f"{prefix}/tasks/{{task_id}}", delete_task)
    app.router.add_post(f"{prefix}/tasks/{{task_id}}/resources/file", upload_task_file)
    app.router.add_post(f"{prefix}/tasks/{{task_id}}/resources/link", add_task_link)
    app.router.add_get(
        f"{prefix}/tasks/{{task_id}}/resources/{{resource_id}}/file", download_task_resource
    )
    app.router.add_delete(
        f"{prefix}/tasks/{{task_id}}/resources/{{resource_id}}", delete_task_resource
    )
    app.router.add_get(f"{prefix}/dashboard", dashboard)
    app.router.add_post(f"{prefix}/ai/run", run_ai_task)
    app.router.add_post(f"{prefix}/ai/confirm", confirm_ai_task)
