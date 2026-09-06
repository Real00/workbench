import json

import pytest
from aiohttp.test_utils import TestClient, TestServer

from app import create_app
from shared.config import Settings
from shared.security import SecurityService
from tests.fakes import (
    MemoryAISettingsRepository,
    MemoryDeviceRepository,
    MemoryMemberRepository,
    MemoryProjectRepository,
    MemoryResourceStorage,
    MemoryTaskRepository,
    MemoryUserRepository,
    knowledge_overrides,
)


async def build_mcp_client(cors_origins: str = "") -> tuple[TestClient, dict[str, str]]:
    security = SecurityService("test-secret-with-at-least-32-characters", 60)
    app = create_app(
        Settings(admin_password="password123", cors_origins=cors_origins),
        security=security,
        user_repository=MemoryUserRepository(),
        task_repository=MemoryTaskRepository(),
        member_repository=MemoryMemberRepository(),
        project_repository=MemoryProjectRepository(),
        device_repository=MemoryDeviceRepository(),
        ai_repository=MemoryAISettingsRepository(),
        resource_storage=MemoryResourceStorage(),
        **knowledge_overrides(),
    )
    client = TestClient(TestServer(app))
    await client.start_server()
    login = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "password123"}
    )
    headers = {"Authorization": f"Bearer {(await login.json())['access_token']}"}
    return client, headers


async def post_rpc(client: TestClient, headers: dict[str, str], payload: dict):
    return await client.post(
        "/mcp", data=json.dumps(payload), headers={**headers, "Content-Type": "application/json"}
    )


async def test_mcp_initialize_negotiates_protocol_version() -> None:
    client, headers = await build_mcp_client()
    try:
        for requested, expected in (
            ("2025-11-25", "2025-11-25"),
            ("2025-06-18", "2025-06-18"),
            ("1.0", "2025-11-25"),
        ):
            response = await post_rpc(client, headers, {
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": requested, "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}},
            })
            assert response.status == 200
            result = (await response.json())["result"]
            assert result["protocolVersion"] == expected
            assert result["capabilities"]["tools"] == {"listChanged": False}
            assert result["serverInfo"]["name"] == "workbench-mcp"
    finally:
        await client.close()


async def test_mcp_notifications_accepted_and_unknown_method_error() -> None:
    client, headers = await build_mcp_client()
    try:
        notification = await post_rpc(client, headers, {
            "jsonrpc": "2.0", "method": "notifications/initialized",
        })
        assert notification.status == 202
        unknown = await post_rpc(client, headers, {"jsonrpc": "2.0", "id": 2, "method": "resources/list"})
        body = await unknown.json()
        assert body["error"]["code"] == -32601
        ping = await post_rpc(client, headers, {"jsonrpc": "2.0", "id": 3, "method": "ping"})
        assert (await ping.json())["result"] == {}
    finally:
        await client.close()


async def test_mcp_tools_list_and_call_read() -> None:
    client, headers = await build_mcp_client()
    try:
        listing = await post_rpc(client, headers, {"jsonrpc": "2.0", "id": 4, "method": "tools/list"})
        tools = (await listing.json())["result"]["tools"]
        names = {tool["name"] for tool in tools}
        assert {"list_tasks", "create_task", "record_member_evaluation", "search_knowledge"} <= names
        read_only = {tool["name"]: tool["annotations"]["readOnlyHint"] for tool in tools}
        assert read_only["list_tasks"] is True
        assert read_only["create_task"] is False

        call = await post_rpc(client, headers, {
            "jsonrpc": "2.0", "id": 5, "method": "tools/call",
            "params": {"name": "list_tasks", "arguments": {}},
        })
        result = (await call.json())["result"]
        assert result.get("isError") is not True
        assert result["structuredContent"]["tasks"] == []
        assert "tasks" in result["content"][0]["text"]
    finally:
        await client.close()


async def test_mcp_tools_call_write_and_error_mapping() -> None:
    client, headers = await build_mcp_client()
    try:
        created = await post_rpc(client, headers, {
            "jsonrpc": "2.0", "id": 6, "method": "tools/call",
            "params": {"name": "create_task", "arguments": {"title": "MCP 建的任务", "priority": "high"}},
        })
        result = (await created.json())["result"]
        assert result.get("isError") is not True
        task_id = result["structuredContent"]["task"]["id"]
        assert result["structuredContent"]["task"]["priority"] == "high"

        evaluated = await post_rpc(client, headers, {
            "jsonrpc": "2.0", "id": 7, "method": "tools/call",
            "params": {"name": "add_progress_entry", "arguments": {"task_id": task_id, "kind": "blocker", "content": "接口超时"}},
        })
        entry_result = (await evaluated.json())["result"]
        assert entry_result["structuredContent"]["task"]["entries"][0]["kind"] == "blocker"

        failed = await post_rpc(client, headers, {
            "jsonrpc": "2.0", "id": 8, "method": "tools/call",
            "params": {"name": "get_task", "arguments": {"task_id": "missing"}},
        })
        failed_result = (await failed.json())["result"]
        assert failed_result["isError"] is True
        assert "not found" in failed_result["content"][0]["text"]

        unknown_tool = await post_rpc(client, headers, {
            "jsonrpc": "2.0", "id": 9, "method": "tools/call",
            "params": {"name": "nope", "arguments": {}},
        })
        assert (await unknown_tool.json())["error"]["code"] == -32602
    finally:
        await client.close()


async def test_mcp_transport_rules_and_auth() -> None:
    client, headers = await build_mcp_client()
    try:
        assert (await client.get("/mcp", headers=headers)).status == 405
        assert (await client.delete("/mcp", headers=headers)).status == 405
        assert (await client.post("/mcp", data="{}", headers={"Content-Type": "application/json"})).status == 401

        batch = await client.post(
            "/mcp", data="[]",
            headers={**headers, "Content-Type": "application/json"},
        )
        assert batch.status == 400

        bad_version = await client.post(
            "/mcp", data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}),
            headers={**headers, "Content-Type": "application/json", "MCP-Protocol-Version": "1.0"},
        )
        assert bad_version.status == 400
        error_body = await bad_version.json()
        assert error_body["error"]["data"]["supported"] == ["2025-11-25", "2025-06-18", "2025-03-26"]
    finally:
        await client.close()


async def test_mcp_accepts_device_credentials_header() -> None:
    client, headers = await build_mcp_client()
    try:
        login = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "password123", "device_id": "desk-mcp", "device_name": "桌面端"},
        )
        device_token = (await login.json())["device_token"]
        device_headers = {"X-Device-Id": "desk-mcp", "X-Device-Token": device_token}
        response = await post_rpc(client, device_headers, {
            "jsonrpc": "2.0", "id": 1, "method": "tools/list",
        })
        assert response.status == 200
        tools = (await response.json())["result"]["tools"]
        assert tools
    finally:
        await client.close()


async def test_mcp_browser_preflight_allows_mcp_headers() -> None:
    """浏览器端客户端（Inspector 等）预检必须放行 MCP 专有头，否则连不上。"""
    client, _ = await build_mcp_client(cors_origins="http://localhost:6274")
    try:
        preflight = await client.options(
            "/mcp",
            headers={
                "Origin": "http://localhost:6274",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": (
                    "authorization, content-type, mcp-protocol-version, mcp-session-id, x-device-id"
                ),
            },
        )
        assert preflight.status == 204
        allow = preflight.headers["Access-Control-Allow-Headers"]
        assert "MCP-Protocol-Version" in allow
        assert "MCP-Session-Id" in allow
        assert "X-Device-Id" in allow
    finally:
        await client.close()
