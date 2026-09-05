from collections.abc import Awaitable, Callable

from aiohttp import web

from shared.web_keys import CORS_ORIGIN

ALLOWED_METHODS = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
ALLOWED_HEADERS = "Authorization, Content-Type"
MAX_AGE = "86400"


def cors_middleware(allowed_origins: frozenset[str]) -> Callable[
    [web.Request, Callable[[web.Request], Awaitable[web.StreamResponse]]],
    Awaitable[web.StreamResponse],
]:
    """跨源支持：桌面端（tauri://）或独立网页域访问云端 API 时启用。

    通过 WORKBENCH_CORS_ORIGINS 配置放行来源（逗号分隔）；留空时全部请求
    按同源处理，不加任何 CORS 头。中间件必须放在最外层：预检请求无
    Authorization，需先于鉴权短路；错误响应也要带放行头浏览器才能读到。
    """

    @web.middleware
    async def middleware(
        request: web.Request,
        handler: Callable[[web.Request], Awaitable[web.StreamResponse]],
    ) -> web.StreamResponse:
        origin = request.headers.get("Origin")
        allowed = origin is not None and origin in allowed_origins
        if request.method == "OPTIONS":
            if not origin:
                return await handler(request)
            if not allowed:
                raise web.HTTPForbidden(text="origin not allowed")
            return web.Response(
                status=204,
                headers={
                    "Access-Control-Allow-Origin": origin,
                    "Access-Control-Allow-Methods": ALLOWED_METHODS,
                    "Access-Control-Allow-Headers": ALLOWED_HEADERS,
                    "Access-Control-Max-Age": MAX_AGE,
                    "Vary": "Origin",
                },
            )
        # 流式响应在路由内部 prepare 并写出，中间件事后补头无效——
        # 把放行来源挂到请求上，由路由在 prepare 前自行应用（见 pulse/routes）。
        request[CORS_ORIGIN] = origin if allowed else None
        response = await handler(request)
        if allowed and origin:
            response.headers.setdefault("Access-Control-Allow-Origin", origin)
            response.headers.setdefault("Vary", "Origin")
        return response

    return middleware
