from aiohttp import web

from api.http import response
from shared.web_keys import SYSTEM


async def get_version(request: web.Request) -> web.Response:
    return response(request.app[SYSTEM].version())


async def check_update(request: web.Request) -> web.Response:
    return response(await request.app[SYSTEM].check_update())


async def apply_update(request: web.Request) -> web.Response:
    return response(request.app[SYSTEM].apply_update())


async def get_update_status(request: web.Request) -> web.Response:
    return response(request.app[SYSTEM].update_status())


def register_routes(app: web.Application) -> None:
    app.router.add_get("/api/v1/system/version", get_version)
    app.router.add_post("/api/v1/system/updates/check", check_update)
    app.router.add_post("/api/v1/system/updates/apply", apply_update)
    app.router.add_get("/api/v1/system/updates/status", get_update_status)
