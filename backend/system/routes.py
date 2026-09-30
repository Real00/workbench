from aiohttp import web

from api.http import response
from shared.web_keys import SETTINGS, SYSTEM


async def get_version(request: web.Request) -> web.Response:
    return response(request.app[SYSTEM].version())


async def check_update(request: web.Request) -> web.Response:
    return response(await request.app[SYSTEM].check_update())


async def apply_update(request: web.Request) -> web.Response:
    return response(request.app[SYSTEM].apply_update())


async def get_update_status(request: web.Request) -> web.Response:
    return response(request.app[SYSTEM].update_status())


async def check_desktop_update(request: web.Request) -> web.Response:
    current = str(request.rel_url.query.get("current") or "")
    return response(await request.app[SYSTEM].check_desktop_update(current))


async def download_desktop_dmg(request: web.Request) -> web.Response:
    data, content_type, filename = await request.app[SYSTEM].desktop_dmg()
    return web.Response(
        body=data,
        headers={
            "Content-Type": content_type or "application/octet-stream",
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(data)),
        },
    )


async def health(request: web.Request) -> web.Response:
    # aiohttp only serves requests after all module startup hooks have completed.
    settings = request.app[SETTINGS]
    return response({"git_sha": settings.git_sha, "instance": settings.instance_id})


def register_routes(app: web.Application) -> None:
    app.router.add_get("/health", health)
    app.router.add_get("/api/v1/system/version", get_version)
    app.router.add_post("/api/v1/system/updates/check", check_update)
    app.router.add_post("/api/v1/system/updates/apply", apply_update)
    app.router.add_get("/api/v1/system/updates/status", get_update_status)
    app.router.add_get("/api/v1/system/desktop/update", check_desktop_update)
    app.router.add_get("/api/v1/system/desktop/dmg", download_desktop_dmg)
