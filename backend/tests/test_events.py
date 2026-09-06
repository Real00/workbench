import asyncio
import json
from uuid import uuid4

import pytest
from aiohttp.test_utils import TestClient, TestServer

from api.events import _scope_for
from app import create_app
from shared.config import Settings
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


async def build_client(cors_origins: str = "") -> TestClient:
    app = create_app(
        Settings(admin_password="password123", cors_origins=cors_origins),
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
    return client


async def login(client: TestClient) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "password123"}
    )
    assert response.status == 200
    return {"Authorization": f"Bearer {(await response.json())['access_token']}"}


async def read_frame(resp) -> str:
    lines: list[str] = []
    while True:
        raw = await asyncio.wait_for(resp.content.readline(), timeout=5)
        line = raw.decode().rstrip("\n")
        if not line:
            return "\n".join(lines)
        lines.append(line)


async def read_event(resp) -> dict:
    frame = await read_frame(resp)
    assert frame.startswith("data: ")
    return json.loads(frame.removeprefix("data: "))


async def assert_changed(stream, scope: str, action: str) -> None:
    assert await read_event(stream) == {"type": "changed", "scope": scope, "action": action}


async def open_stream(client: TestClient, headers: dict[str, str]):
    resp = await client.get("/api/v1/events", headers=headers)
    assert resp.status == 200
    assert resp.headers["Content-Type"].startswith("text/event-stream")
    assert await read_frame(resp) == ": connected"
    return resp


def test_scope_mapping_covers_every_write_surface() -> None:
    assert _scope_for("/api/v1/progress/tasks") == "progress"
    assert _scope_for("/api/v1/progress/members/m1/evaluations") == "progress"
    assert _scope_for("/api/v1/knowledge/documents") == "knowledge"
    assert _scope_for("/api/v1/captures") == "capture"
    assert _scope_for("/api/v1/ai-settings") == "ai-settings"
    assert _scope_for("/api/v1/ai/confirm") == "all"
    assert _scope_for("/api/v1/progress/ai/confirm") == "all"
    assert _scope_for("/api/v1/auth/login") is None
    assert _scope_for("/api/v1/auth/device") is None
    assert _scope_for("/api/v1/ai/run") is None
    assert _scope_for("/mcp") is None


async def test_events_endpoint_requires_token() -> None:
    client = await build_client()
    try:
        response = await client.get("/api/v1/events")
        assert response.status == 401
    finally:
        await client.close()


async def test_events_broadcast_writes_to_subscribers() -> None:
    client = await build_client()
    try:
        headers = await login(client)
        stream = await open_stream(client, headers)

        created = await client.post(
            "/api/v1/progress/tasks", json={"title": "写周报"}, headers=headers
        )
        assert created.status == 201
        task_id = (await created.json())["id"]
        await assert_changed(stream, "progress", "created")

        updated = await client.patch(
            f"/api/v1/progress/tasks/{task_id}", json={"status": "done"}, headers=headers
        )
        assert updated.status == 200
        await assert_changed(stream, "progress", "updated")

        tag = await client.post(
            "/api/v1/knowledge/tags",
            json={"name": "架构", "explanation": "架构决策记录"},
            headers=headers,
        )
        assert tag.status == 201
        await assert_changed(stream, "knowledge", "created")

        capture = await client.post(
            "/api/v1/captures", json={"id": str(uuid4()), "content": "随手记一条"}, headers=headers
        )
        assert capture.status == 201
        await assert_changed(stream, "capture", "created")

        # 失败请求与登录白名单不广播：短时间内不应有任何事件帧
        invalid = await client.post("/api/v1/progress/tasks", json={}, headers=headers)
        assert invalid.status == 422
        again = await client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "password123"}
        )
        assert again.status == 200
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(stream.content.readline(), timeout=0.3)
        stream.close()
    finally:
        await client.close()


async def test_events_stream_sends_cors_headers_for_desktop_shell() -> None:
    client = await build_client(cors_origins="http://localhost:6274")
    try:
        headers = await login(client)
        stream = await client.get(
            "/api/v1/events", headers={**headers, "Origin": "http://localhost:6274"}
        )
        assert stream.status == 200
        assert stream.headers["Access-Control-Allow-Origin"] == "http://localhost:6274"
        assert await read_frame(stream) == ": connected"
        stream.close()
    finally:
        await client.close()


async def test_mcp_write_tool_broadcasts_event() -> None:
    client = await build_client()
    try:
        headers = await login(client)
        stream = await open_stream(client, headers)

        init = await client.post(
            "/mcp",
            data=json.dumps({
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                           "clientInfo": {"name": "test", "version": "0"}},
            }),
            headers={**headers, "Content-Type": "application/json"},
        )
        assert init.status == 200
        call = await client.post(
            "/mcp",
            data=json.dumps({
                "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": "create_task", "arguments": {"title": "来自 MCP 的任务"}},
            }),
            headers={**headers, "Content-Type": "application/json"},
        )
        assert call.status == 200
        assert (await call.json())["result"].get("isError") is not True
        await assert_changed(stream, "progress", "created")

        # 只读工具不广播
        listing = await client.post(
            "/mcp",
            data=json.dumps({
                "jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {"name": "list_tasks", "arguments": {}},
            }),
            headers={**headers, "Content-Type": "application/json"},
        )
        assert listing.status == 200
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(stream.content.readline(), timeout=0.3)
        stream.close()
    finally:
        await client.close()
