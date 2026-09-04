from aiohttp import web
from pydantic import BaseModel

from api.http import body, response
from shared.web_keys import IDENTITY


class LoginInput(BaseModel):
    username: str
    password: str


async def login(request: web.Request) -> web.Response:
    data = await body(request, LoginInput)
    return response(await request.app[IDENTITY].login(**data))


def register_routes(app: web.Application) -> None:
    app.router.add_post("/api/v1/auth/login", login)
