"""全局数据变更总线：/api/v1 写操作统一广播 + GET /api/v1/events 订阅端点。

网页端与桌面壳各持一条 SSE 长连接，任何 /api/v1 写操作成功（含 AI 确认
落库）都广播 scope 级 changed 事件，前端收到后静默重拉对应模块——桌面端
因此不需要刷新按钮。事件经中间件在响应出口发布，业务代码零侵入；/mcp
不走 /api/v1 中间件，由 mcp/routes 在写工具成功后单独发布。

SSE 写出与 CORS 处理同 pulse/routes：流式响应在路由内 prepare，CORS 头
必须在 prepare 前从 cors 中间件挂好的 CORS_ORIGIN 取。客户端断连由 25s
ping 的写失败兜底清理，最长残留一个 ping 周期。
"""

import asyncio
from collections.abc import Awaitable, Callable

from aiohttp import web

from api.http import dumps
from shared.events import ChangeEventBus
from shared.web_keys import CORS_ORIGIN, EVENT_BUS

PING_INTERVAL = 25.0
_MUTATING_METHODS = frozenset({"POST", "PATCH", "PUT", "DELETE"})
_ACTION_BY_METHOD = {"POST": "created", "PATCH": "updated", "PUT": "updated", "DELETE": "deleted"}


def _scope_for(path: str) -> str | None:
    # ai/confirm 落库范围横跨任务与知识库，直接让全模块失效
    if path in {"/api/v1/ai/confirm", "/api/v1/progress/ai/confirm"}:
        return "all"
    if path.startswith("/api/v1/progress"):
        return "progress"
    if path.startswith("/api/v1/knowledge"):
        return "knowledge"
    if path.startswith("/api/v1/captures"):
        return "capture"
    if path.startswith("/api/v1/ai-settings"):
        return "ai-settings"
    return None


@web.middleware
async def mutation_events_middleware(
    request: web.Request, handler: Callable[[web.Request], Awaitable[web.StreamResponse]]
) -> web.StreamResponse:
    response = await handler(request)
    bus: ChangeEventBus | None = request.app.get(EVENT_BUS)
    if (
        bus is not None
        and request.method in _MUTATING_METHODS
        and response.status < 400
        and "application/json" in response.headers.get("Content-Type", "")
    ):
        scope = _scope_for(request.path)
        if scope:
            bus.publish(scope, _ACTION_BY_METHOD[request.method])
    return response


async def stream_events(request: web.Request) -> web.StreamResponse:
    stream = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "text/event-stream; charset=utf-8",
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
    if origin := request.get(CORS_ORIGIN):
        stream.headers["Access-Control-Allow-Origin"] = origin
        stream.headers["Vary"] = "Origin"
    await stream.prepare(request)
    bus: ChangeEventBus = request.app[EVENT_BUS]

    async def write(chunk: bytes) -> bool:
        try:
            await stream.write(chunk)
            return True
        except (ConnectionResetError, ConnectionAbortedError, OSError):
            return False

    if not await write(b": connected\n\n"):
        return stream

    queue = bus.subscribe()
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=PING_INTERVAL)
            except TimeoutError:
                if not await write(b": ping\n\n"):
                    break
                continue
            if not await write(f"data: {dumps(event)}\n\n".encode()):
                break
    finally:
        bus.unsubscribe(queue)
        try:
            await stream.write_eof()
        except (ConnectionResetError, ConnectionAbortedError, OSError):
            pass
    return stream


def register_events_routes(app: web.Application) -> None:
    app.router.add_get("/api/v1/events", stream_events)
