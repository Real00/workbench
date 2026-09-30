"""出站 MCP 连接：仅远程 Streamable HTTP，连接失败由调用方降级跳过。"""

from __future__ import annotations

import asyncio
import logging

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.toolsets.abstract import AbstractToolset

from ai_settings.ports import McpServerConnection

logger = logging.getLogger(__name__)

MCP_INIT_TIMEOUT_SECONDS = 8.0
MCP_CALL_TIMEOUT_SECONDS = 45.0
MAX_LISTED_TOOLS = 100


def build_mcp_client(server: McpServerConnection) -> Client:
    headers = dict(server.headers)
    if server.api_key and not any(key.lower() == "authorization" for key in headers):
        headers["Authorization"] = f"Bearer {server.api_key}"
    return Client(
        StreamableHttpTransport(server.url, headers=headers or None),
        timeout=MCP_CALL_TIMEOUT_SECONDS,
        init_timeout=MCP_INIT_TIMEOUT_SECONDS,
    )


def prefixed_toolset(server: McpServerConnection) -> AbstractToolset:
    """工具名加 `<name>__` 前缀，避免与内置工具或其它服务器重名。"""
    return MCPToolset(build_mcp_client(server), id=server.name).prefixed(f"{server.name}__")


async def probe_mcp_server(server: McpServerConnection) -> list[str]:
    """连接并列出工具名；连接类错误转成 ValueError，供设置页展示。"""
    try:
        client = build_mcp_client(server)
        async with client:
            tools = await asyncio.wait_for(client.list_tools(), MCP_INIT_TIMEOUT_SECONDS)
            return [tool.name for tool in tools[:MAX_LISTED_TOOLS]]
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001 — 网络/协议错误统一转业务提示
        raise ValueError(f"无法连接 MCP 服务器：{type(exc).__name__}: {str(exc)[:160]}") from exc
