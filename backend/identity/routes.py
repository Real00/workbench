from aiohttp import web
from pydantic import BaseModel, Field

from api.http import body, response
from shared.web_keys import ACTOR, IDENTITY


class LoginInput(BaseModel):
    username: str
    password: str
    device_id: str | None = Field(default=None, max_length=100)
    device_name: str | None = Field(default=None, max_length=100)


class DeviceLoginInput(BaseModel):
    device_id: str = Field(min_length=1, max_length=100)
    device_token: str = Field(min_length=1, max_length=200)


class DeviceBindInput(BaseModel):
    device_id: str = Field(min_length=1, max_length=100)
    device_name: str = Field(min_length=1, max_length=100)


async def login(request: web.Request) -> web.Response:
    data = await body(request, LoginInput)
    identity = request.app[IDENTITY]
    result = await identity.login(data["username"], data["password"])
    device_token = await identity.bind_device(
        result["user"]["id"], data.get("device_id") or "", data.get("device_name") or ""
    )
    if device_token:
        result["device_token"] = device_token
    return response(result)


async def bind_device(request: web.Request) -> web.Response:
    """已登录会话为当前设备补发绑定凭证（应用升级后自动获得静默登录能力）。"""
    data = await body(request, DeviceBindInput)
    token = await request.app[IDENTITY].bind_device(
        request[ACTOR]["sub"], data["device_id"], data["device_name"]
    )
    if not token:
        raise PermissionError("device binding is not available")
    return response({"device_token": token})


async def login_device(request: web.Request) -> web.Response:
    data = await body(request, DeviceLoginInput)
    return response(
        await request.app[IDENTITY].login_with_device(data["device_id"], data["device_token"])
    )


async def list_devices(request: web.Request) -> web.Response:
    return response(await request.app[IDENTITY].list_devices(request[ACTOR]["sub"]))


async def unbind_device(request: web.Request) -> web.Response:
    await request.app[IDENTITY].unbind_device(request[ACTOR]["sub"], request.match_info["binding_id"])
    return response({"ok": True})


def register_routes(app: web.Application) -> None:
    app.router.add_post("/api/v1/auth/login", login)
    app.router.add_post("/api/v1/auth/device", login_device)
    app.router.add_post("/api/v1/auth/devices/bind", bind_device)
    app.router.add_get("/api/v1/auth/devices", list_devices)
    app.router.add_delete("/api/v1/auth/devices/{binding_id}", unbind_device)
