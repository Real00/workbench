import json
from collections.abc import Awaitable, Callable
from typing import Any

import jwt
from aiohttp import web
from pydantic import BaseModel, ValidationError

from shared.security import SecurityService
from shared.web_keys import ACTOR, SECURITY


def response(data: Any, status: int = 200) -> web.Response:
    return web.Response(
        text=dumps(data),
        status=status,
        content_type="application/json",
    )


def dumps(data: Any) -> str:
    return json.dumps(data, default=str, ensure_ascii=False)


async def body(request: web.Request, model: type[BaseModel]) -> dict[str, Any]:
    return model.model_validate(await request.json()).model_dump(exclude_unset=True)


@web.middleware
async def error_middleware(
    request: web.Request, handler: Callable[[web.Request], Awaitable[web.StreamResponse]]
) -> web.StreamResponse:
    try:
        return await handler(request)
    except ValidationError as exc:
        return response({"error": "validation_error", "details": exc.errors()}, 422)
    except (ValueError, json.JSONDecodeError) as exc:
        return response({"error": str(exc)}, 400)
    except LookupError as exc:
        return response({"error": str(exc)}, 404)
    except PermissionError as exc:
        return response({"error": str(exc)}, 401)
    except (jwt.InvalidTokenError, KeyError):
        return response({"error": "invalid or expired token"}, 401)
    except web.HTTPException:
        raise


@web.middleware
async def auth_middleware(
    request: web.Request, handler: Callable[[web.Request], Awaitable[web.StreamResponse]]
) -> web.StreamResponse:
    if not request.path.startswith("/api/v1") or request.path == "/api/v1/auth/login":
        return await handler(request)
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return response({"error": "authentication required"}, 401)
    security: SecurityService = request.app[SECURITY]
    request[ACTOR] = security.decode_token(header.removeprefix("Bearer "))
    admin_paths = ("/api/v1/progress/members", "/api/v1/ai-settings")
    if request.path.startswith(admin_paths) and request[ACTOR].get("role") != "admin":
        return response({"error": "admin required"}, 403)
    return await handler(request)
