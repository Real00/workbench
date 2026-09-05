from pathlib import Path
from typing import Any

from aiohttp import web
from pymongo import AsyncMongoClient

from ai_settings.module import AISettingsModule
from api.cors import cors_middleware
from api.http import auth_middleware, error_middleware
from capture.module import CaptureModule
from identity.module import IdentityModule
from knowledge.module import KnowledgeModule
from progress.module import ProgressModule
from pulse.module import PulseModule
from shared.config import Settings, cors_origin_set, get_settings
from shared.module import AppModule, ModuleContext
from shared.security import SecurityService
from shared.web_keys import AI_CONTRIBUTIONS, MONGO_CLIENT, SECURITY, SETTINGS


def resolve_static_file(static_dir: Path, relative: str) -> Path | None:
    candidate = (static_dir / relative).resolve()
    if relative and candidate.is_relative_to(static_dir.resolve()) and candidate.is_file():
        return candidate
    index = static_dir / "index.html"
    return index if index.is_file() else None


async def spa_handler(request: web.Request) -> web.StreamResponse:
    if request.path.startswith("/api/"):
        raise web.HTTPNotFound()
    static_dir: Path = request.app[SETTINGS].static_dir
    relative = request.match_info.get("path", "")
    candidate = resolve_static_file(static_dir, relative)
    if candidate:
        return web.FileResponse(candidate)
    raise web.HTTPNotFound(text="frontend dist not found")


def create_app(settings: Settings | None = None, **overrides: Any) -> web.Application:
    settings = settings or get_settings()
    client: AsyncMongoClient[Any] = overrides.get("mongo_client") or AsyncMongoClient(
        settings.mongo_uri
    )
    security = overrides.get("security") or SecurityService(
        settings.jwt_secret, settings.jwt_ttl_seconds, settings.encryption_key
    )

    app = web.Application(
        middlewares=[
            cors_middleware(cors_origin_set(settings.cors_origins)),
            error_middleware,
            auth_middleware,
        ],
        client_max_size=21 * 1024 * 1024,
    )
    app[SETTINGS] = settings
    app[MONGO_CLIENT] = client
    app[SECURITY] = security
    context = ModuleContext(
        settings=settings,
        mongo=client,
        security=security,
        overrides=overrides,
    )
    modules: tuple[AppModule, ...] = (
        IdentityModule(),
        AISettingsModule(),
        ProgressModule(),
        KnowledgeModule(),
        CaptureModule(),
        PulseModule(),
    )
    for module in modules:
        module.register(app, context)
    app[AI_CONTRIBUTIONS] = context.ai_contributions

    async def cleanup(_: web.Application) -> None:
        if "mongo_client" not in overrides:
            await client.close()

    app.on_cleanup.append(cleanup)
    app.router.add_get("/{path:.*}", spa_handler)
    return app


if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=8080)
