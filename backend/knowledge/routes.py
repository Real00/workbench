from aiohttp import web
from aiohttp.multipart import BodyPartReader
from pydantic import BaseModel, Field

from api.http import body, response
from shared.web_keys import KNOWLEDGE


class TagInput(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    explanation: str = Field(min_length=1, max_length=2000)


class TagUpdateInput(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    explanation: str | None = Field(default=None, min_length=1, max_length=2000)


class EntryInput(BaseModel):
    key: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=1, max_length=20_000)
    tag_ids: list[str] = []
    document_ids: list[str] = []
    aliases: list[str] = []


class EntryUpdateInput(BaseModel):
    key: str | None = Field(default=None, min_length=1, max_length=200)
    value: str | None = Field(default=None, min_length=1, max_length=20_000)
    tag_ids: list[str] | None = None
    document_ids: list[str] | None = None
    aliases: list[str] | None = None


class DocumentInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=200_000)
    tag_ids: list[str] = []
    entry_ids: list[str] = []
    canvas_x: float = 80
    canvas_y: float = 80


class DocumentUpdateInput(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, max_length=200_000)
    tag_ids: list[str] | None = None
    entry_ids: list[str] | None = None
    canvas_x: float | None = None
    canvas_y: float | None = None


class CanvasMoveInput(BaseModel):
    canvas_x: float
    canvas_y: float


async def _read_upload(request: web.Request) -> tuple[str, bytes]:
    reader = await request.multipart()
    field = await reader.next()
    if not isinstance(field, BodyPartReader) or field.name != "file":
        raise ValueError("file is required")
    return field.filename or "", await field.read(decode=False)


async def list_tags(request: web.Request) -> web.Response:
    return response(await request.app[KNOWLEDGE].list_tags(request.query.get("q") or ""))


async def create_tag(request: web.Request) -> web.Response:
    return response(await request.app[KNOWLEDGE].create_tag(await body(request, TagInput)), 201)


async def update_tag(request: web.Request) -> web.Response:
    return response(
        await request.app[KNOWLEDGE].update_tag(
            request.match_info["tag_id"], await body(request, TagUpdateInput)
        )
    )


async def delete_tag(request: web.Request) -> web.Response:
    await request.app[KNOWLEDGE].delete_tag(request.match_info["tag_id"])
    return response({"ok": True})


async def list_entries(request: web.Request) -> web.Response:
    return response(
        await request.app[KNOWLEDGE].list_entries(
            request.query.get("q") or "", request.query.get("tag_id")
        )
    )


async def create_entry(request: web.Request) -> web.Response:
    return response(await request.app[KNOWLEDGE].create_entry(await body(request, EntryInput)), 201)


async def get_entry(request: web.Request) -> web.Response:
    return response(await request.app[KNOWLEDGE].get_entry(request.match_info["entry_id"]))


async def update_entry(request: web.Request) -> web.Response:
    return response(
        await request.app[KNOWLEDGE].update_entry(
            request.match_info["entry_id"], await body(request, EntryUpdateInput)
        )
    )


async def delete_entry(request: web.Request) -> web.Response:
    await request.app[KNOWLEDGE].delete_entry(request.match_info["entry_id"])
    return response({"ok": True})


async def list_documents(request: web.Request) -> web.Response:
    return response(
        await request.app[KNOWLEDGE].list_documents(
            request.query.get("q") or "", request.query.get("tag_id")
        )
    )


async def create_document(request: web.Request) -> web.Response:
    return response(
        await request.app[KNOWLEDGE].create_document(await body(request, DocumentInput)), 201
    )


async def get_document(request: web.Request) -> web.Response:
    return response(await request.app[KNOWLEDGE].get_document(request.match_info["document_id"]))


async def update_document(request: web.Request) -> web.Response:
    return response(
        await request.app[KNOWLEDGE].update_document(
            request.match_info["document_id"], await body(request, DocumentUpdateInput)
        )
    )


async def move_document(request: web.Request) -> web.Response:
    payload = await body(request, CanvasMoveInput)
    return response(
        await request.app[KNOWLEDGE].move_document(
            request.match_info["document_id"], payload["canvas_x"], payload["canvas_y"]
        )
    )


async def delete_document(request: web.Request) -> web.Response:
    await request.app[KNOWLEDGE].delete_document(request.match_info["document_id"])
    return response({"ok": True})


async def extract_upload(request: web.Request) -> web.Response:
    filename, data = await _read_upload(request)
    return response(request.app[KNOWLEDGE].extract(filename, data))


async def import_document(request: web.Request) -> web.Response:
    filename, data = await _read_upload(request)
    apply_body = request.query.get("apply_body", "1") != "0"
    return response(
        await request.app[KNOWLEDGE].import_document(
            request.match_info["document_id"], filename, data, apply_body=apply_body
        )
    )


def register_routes(app: web.Application) -> None:
    prefix = "/api/v1/knowledge"
    app.router.add_get(f"{prefix}/tags", list_tags)
    app.router.add_post(f"{prefix}/tags", create_tag)
    app.router.add_patch(f"{prefix}/tags/{{tag_id}}", update_tag)
    app.router.add_delete(f"{prefix}/tags/{{tag_id}}", delete_tag)
    app.router.add_get(f"{prefix}/entries", list_entries)
    app.router.add_post(f"{prefix}/entries", create_entry)
    app.router.add_get(f"{prefix}/entries/{{entry_id}}", get_entry)
    app.router.add_patch(f"{prefix}/entries/{{entry_id}}", update_entry)
    app.router.add_delete(f"{prefix}/entries/{{entry_id}}", delete_entry)
    app.router.add_get(f"{prefix}/documents", list_documents)
    app.router.add_post(f"{prefix}/documents", create_document)
    app.router.add_get(f"{prefix}/documents/{{document_id}}", get_document)
    app.router.add_patch(f"{prefix}/documents/{{document_id}}", update_document)
    app.router.add_patch(f"{prefix}/documents/{{document_id}}/canvas", move_document)
    app.router.add_delete(f"{prefix}/documents/{{document_id}}", delete_document)
    app.router.add_post(f"{prefix}/extract", extract_upload)
    app.router.add_post(f"{prefix}/documents/{{document_id}}/import", import_document)
