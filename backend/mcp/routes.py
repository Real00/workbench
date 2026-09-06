"""MCP Streamable HTTP 端点（协议版本 2025-11-25，兼容 2025-06-18 / 2025-03-26）。

无状态实现：不颁发 MCP-Session-Id，工具调用即时返回 application/json；
不支持服务器主动推送（GET/DELETE 一律 405），规范允许。
鉴权：Authorization: Bearer <JWT> 或 X-Device-Id + X-Device-Token（设备绑定凭证）。
关于规范中 Origin 校验（防 DNS 重绑定）的说明：该要求针对无鉴权的本机服务器；
本端点要求显式 Bearer 凭证，重绑定页面无法获取令牌，故以鉴权为边界。
"""

import json
from typing import Any

from aiohttp import web

from mcp.tools import TOOL_MAP, TOOLS
from shared.events import ChangeEventBus
from shared.security import SecurityService
from shared.web_keys import EVENT_BUS, IDENTITY, SECURITY

SUPPORTED_PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26")
LATEST_PROTOCOL_VERSION = "2025-11-25"
ASSUMED_PROTOCOL_VERSION = "2025-03-26"
SERVER_INFO = {
    "name": "workbench-mcp",
    "title": "个人工作台 MCP",
    "version": "0.1.0",
    "description": "工作台任务、成员、项目与知识库工具",
}
INSTRUCTIONS = (
    "个人工作台工具集：任务/成员/项目/成员评价/知识库的读写。"
    "写入立即生效（与站内 Pulse 的排队确认不同）。"
    "list_* 读取后可用 get_task/条目定位；更新支持按名称解析"
    "（title_query/name/key）。"
)


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def _rpc_response(message_id: Any, payload: dict[str, Any]) -> web.Response:
    return web.json_response({"jsonrpc": "2.0", "id": message_id, "result": payload}, dumps=_dumps)


def _rpc_error(message_id: Any, code: int, message: str, data: Any = None, status: int = 200) -> web.Response:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return web.json_response({"jsonrpc": "2.0", "id": message_id, "error": error}, status=status, dumps=_dumps)


def _tool_descriptors() -> list[dict[str, Any]]:
    return [
        {
            "name": tool.name,
            "title": tool.title,
            "description": tool.description,
            "inputSchema": tool.input_schema,
            "annotations": tool.annotations,
        }
        for tool in TOOLS
    ]


async def _authenticate(request: web.Request) -> dict[str, Any] | None:
    security: SecurityService = request.app[SECURITY]
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            return security.decode_token(auth[7:])
        except Exception:
            return None
    device_id = request.headers.get("X-Device-Id")
    device_token = request.headers.get("X-Device-Token")
    if device_id and device_token:
        try:
            result = await request.app[IDENTITY].login_with_device(device_id, device_token)
            return security.decode_token(result["access_token"])
        except Exception:
            return None
    return None


def _protocol_version(request: web.Request) -> str | None:
    version = request.headers.get("MCP-Protocol-Version")
    if not version:
        return ASSUMED_PROTOCOL_VERSION
    if version not in SUPPORTED_PROTOCOL_VERSIONS:
        return None
    return version


async def _handle_tools_call(request: web.Request, actor: dict[str, Any], params: dict[str, Any]) -> web.Response:
    message_id = params.get("_message_id")
    name = params.get("name")
    tool = TOOL_MAP.get(str(name or ""))
    if not tool:
        return _rpc_error(message_id, -32602, f"unknown tool: {name}")
    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict):
        return _rpc_error(message_id, -32602, "tool arguments must be an object")
    try:
        result = await tool.handler(request, str(actor.get("sub") or ""), arguments)
    except (ValueError, LookupError, PermissionError) as exc:
        return _rpc_response(message_id, {
            "content": [{"type": "text", "text": str(exc)}],
            "isError": True,
        })
    except Exception as exc:  # noqa: BLE001 — 工具内部异常统一转为工具错误，不向客户端泄露堆栈
        return _rpc_response(message_id, {
            "content": [{"type": "text", "text": f"tool execution failed: {exc}"}],
            "isError": True,
        })
    structured = result if isinstance(result, dict | list) else {"result": result}
    # /mcp 不走 /api/v1 的变更广播中间件，写工具成功后单独向 SSE 总线发布
    if tool.scope:
        bus: ChangeEventBus | None = request.app.get(EVENT_BUS)
        if bus:
            bus.publish(tool.scope, "created" if tool.name.startswith("create_") else "updated")
    return _rpc_response(message_id, {
        "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=1, default=str)}],
        "structuredContent": structured,
    })


async def _dispatch(request: web.Request, actor: dict[str, Any], message: dict[str, Any]) -> web.Response:
    message_id = message.get("id")
    method = message.get("method")
    params = message.get("params") or {}

    if method == "initialize":
        requested = str(params.get("protocolVersion") or "")
        negotiated = requested if requested in SUPPORTED_PROTOCOL_VERSIONS else LATEST_PROTOCOL_VERSION
        return _rpc_response(message_id, {
            "protocolVersion": negotiated,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
            "instructions": INSTRUCTIONS,
        })
    if method == "ping":
        return _rpc_response(message_id, {})
    if method == "tools/list":
        return _rpc_response(message_id, {"tools": _tool_descriptors()})
    if method == "tools/call":
        return await _handle_tools_call(request, actor, {**params, "_message_id": message_id})
    return _rpc_error(message_id, -32601, f"method not found: {method}")


async def mcp_post(request: web.Request) -> web.Response:
    actor = await _authenticate(request)
    if not actor:
        return web.json_response(
            {"error": "unauthorized"},
            status=401,
            headers={"WWW-Authenticate": "Bearer"},
        )
    content_type = request.headers.get("Content-Type", "").split(";")[0].strip().lower()
    if content_type != "application/json":
        return web.json_response({"error": "unsupported media type"}, status=415)
    try:
        message = await request.json()
    except Exception:
        return _rpc_error(None, -32700, "Parse error", status=400)
    if isinstance(message, list):
        return _rpc_error(None, -32600, "batching is not supported", status=400)
    if not isinstance(message, dict):
        return _rpc_error(None, -32600, "invalid JSON-RPC message", status=400)

    method = message.get("method")
    # JSON-RPC 响应或通知：接受即 202，无响应体
    if not method or not isinstance(method, str):
        return web.Response(status=202)
    if method.startswith("notifications/"):
        return web.Response(status=202)

    if method != "initialize":
        version = _protocol_version(request)
        if version is None:
            requested = request.headers.get("MCP-Protocol-Version")
            return _rpc_error(
                message.get("id"), -32600, "unsupported MCP-Protocol-Version",
                data={"requested": requested, "supported": list(SUPPORTED_PROTOCOL_VERSIONS)},
                status=400,
            )
    return await _dispatch(request, actor, message)


async def mcp_get(request: web.Request) -> web.Response:
    """未提供服务器主动推送流：按规范返回 405。"""
    return web.Response(status=405, headers={"Allow": "POST"})


async def mcp_delete(request: web.Request) -> web.Response:
    """无状态实现没有可终止的会话：按规范返回 405。"""
    return web.Response(status=405, headers={"Allow": "POST"})


def register_mcp_routes(app: web.Application) -> None:
    app.router.add_post("/mcp", mcp_post)
    app.router.add_get("/mcp", mcp_get)
    app.router.add_delete("/mcp", mcp_delete)
