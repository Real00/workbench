from typing import Any

from aiohttp import web
from pydantic import BaseModel, Field

from api.http import body, response
from shared.web_keys import SUBSCRIPTION


class PluginCreateInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    script: str = Field(min_length=1, max_length=200_000)


class PluginUpdateInput(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    script: str | None = Field(default=None, min_length=1, max_length=200_000)


class PluginTrialInput(BaseModel):
    body: str = Field(min_length=1, max_length=2_000_000)
    url: str = Field(default="https://example.com/feed", max_length=2000)
    config: dict[str, Any] = Field(default_factory=dict)


class SourceCreateInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=1, max_length=2000)
    plugin_id: str = Field(min_length=1, max_length=100)
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    interval_minutes: int = Field(default=60, ge=5, le=10080)


class SourceUpdateInput(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    url: str | None = Field(default=None, min_length=1, max_length=2000)
    plugin_id: str | None = Field(default=None, min_length=1, max_length=100)
    config: dict[str, Any] | None = None
    enabled: bool | None = None
    interval_minutes: int | None = Field(default=None, ge=5, le=10080)


async def list_plugins(request: web.Request) -> web.Response:
    return response(await request.app[SUBSCRIPTION].list_plugins())


async def get_plugin(request: web.Request) -> web.Response:
    return response(await request.app[SUBSCRIPTION].get_plugin(request.match_info["id"]))


async def create_plugin(request: web.Request) -> web.Response:
    payload = await body(request, PluginCreateInput)
    return response(await request.app[SUBSCRIPTION].create_plugin(payload))


async def update_plugin(request: web.Request) -> web.Response:
    return response(
        await request.app[SUBSCRIPTION].update_plugin(
            request.match_info["id"], await body(request, PluginUpdateInput)
        )
    )


async def delete_plugin(request: web.Request) -> web.Response:
    await request.app[SUBSCRIPTION].delete_plugin(request.match_info["id"])
    return response({"ok": True})


async def trial_plugin(request: web.Request) -> web.Response:
    payload = await body(request, PluginTrialInput)
    return response(
        await request.app[SUBSCRIPTION].trial_plugin(
            request.match_info["id"],
            body=str(payload.get("body") or ""),
            url=str(payload.get("url") or "https://example.com/feed"),
            config=dict(payload.get("config") or {}),
        )
    )


async def list_sources(request: web.Request) -> web.Response:
    return response(await request.app[SUBSCRIPTION].list_sources())


async def get_source(request: web.Request) -> web.Response:
    return response(await request.app[SUBSCRIPTION].get_source(request.match_info["id"]))


async def create_source(request: web.Request) -> web.Response:
    payload = await body(request, SourceCreateInput)
    return response(await request.app[SUBSCRIPTION].create_source(payload))


async def update_source(request: web.Request) -> web.Response:
    return response(
        await request.app[SUBSCRIPTION].update_source(
            request.match_info["id"], await body(request, SourceUpdateInput)
        )
    )


async def delete_source(request: web.Request) -> web.Response:
    await request.app[SUBSCRIPTION].delete_source(request.match_info["id"])
    return response({"ok": True})


async def refresh_source(request: web.Request) -> web.Response:
    return response(await request.app[SUBSCRIPTION].refresh_source(request.match_info["id"]))


async def list_articles(request: web.Request) -> web.Response:
    source_id = request.rel_url.query.get("source_id") or None
    query = request.rel_url.query.get("q") or ""
    offset = int(request.rel_url.query.get("offset") or 0)
    limit = int(request.rel_url.query.get("limit") or 50)
    return response(
        await request.app[SUBSCRIPTION].list_articles(
            source_id=source_id, query=query, offset=offset, limit=limit
        )
    )


async def get_article(request: web.Request) -> web.Response:
    return response(await request.app[SUBSCRIPTION].get_article(request.match_info["id"]))


def register_routes(app: web.Application) -> None:
    app.router.add_get("/api/v1/subscription/plugins", list_plugins)
    app.router.add_post("/api/v1/subscription/plugins", create_plugin)
    app.router.add_get("/api/v1/subscription/plugins/{id}", get_plugin)
    app.router.add_patch("/api/v1/subscription/plugins/{id}", update_plugin)
    app.router.add_delete("/api/v1/subscription/plugins/{id}", delete_plugin)
    app.router.add_post("/api/v1/subscription/plugins/{id}/trial", trial_plugin)

    app.router.add_get("/api/v1/subscription/sources", list_sources)
    app.router.add_post("/api/v1/subscription/sources", create_source)
    app.router.add_get("/api/v1/subscription/sources/{id}", get_source)
    app.router.add_patch("/api/v1/subscription/sources/{id}", update_source)
    app.router.add_delete("/api/v1/subscription/sources/{id}", delete_source)
    app.router.add_post("/api/v1/subscription/sources/{id}/refresh", refresh_source)

    app.router.add_get("/api/v1/subscription/articles", list_articles)
    app.router.add_get("/api/v1/subscription/articles/{id}", get_article)
