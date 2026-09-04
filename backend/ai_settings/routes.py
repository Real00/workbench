from aiohttp import web
from pydantic import BaseModel

from api.http import body, response
from shared.ai import ModuleAiContribution, describe_contributions
from shared.web_keys import AI_CONTRIBUTIONS, AI_SETTINGS


class AISettingsInput(BaseModel):
    base_url: str
    model: str
    api_key: str | None = None


async def get_settings(request: web.Request) -> web.Response:
    return response(await request.app[AI_SETTINGS].get())


async def get_secret(request: web.Request) -> web.Response:
    return response(await request.app[AI_SETTINGS].get_secret())


async def put_settings(request: web.Request) -> web.Response:
    data = await body(request, AISettingsInput)
    return response(await request.app[AI_SETTINGS].configure(data))


async def test_connection(request: web.Request) -> web.Response:
    data = await request.json() if request.can_read_body else {}
    return response(await request.app[AI_SETTINGS].test_connection(data))


async def get_tools(request: web.Request) -> web.Response:
    contributions: list[ModuleAiContribution] = request.app[AI_CONTRIBUTIONS]
    return response({"modules": describe_contributions(contributions)})


def register_routes(app: web.Application) -> None:
    app.router.add_get("/api/v1/ai-settings", get_settings)
    app.router.add_get("/api/v1/ai-settings/secret", get_secret)
    app.router.add_put("/api/v1/ai-settings", put_settings)
    app.router.add_post("/api/v1/ai-settings/test", test_connection)
    app.router.add_get("/api/v1/ai-settings/tools", get_tools)
