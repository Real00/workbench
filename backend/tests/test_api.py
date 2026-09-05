from aiohttp import FormData
from aiohttp.test_utils import TestClient, TestServer

from app import create_app
from shared.config import Settings
from shared.security import SecurityService
from tests.fakes import (
    MemoryAISettingsRepository,
    MemoryMemberRepository,
    MemoryProjectRepository,
    MemoryResourceStorage,
    MemoryTaskRepository,
    MemoryUserRepository,
    knowledge_overrides,
)


async def test_login_and_task_flow() -> None:
    app = create_app(
        Settings(admin_password="password123"),
        user_repository=MemoryUserRepository(),
        task_repository=MemoryTaskRepository(),
        member_repository=MemoryMemberRepository(),
        project_repository=MemoryProjectRepository(),
        ai_repository=MemoryAISettingsRepository(),
        resource_storage=MemoryResourceStorage(),
        **knowledge_overrides(),
    )
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        login = await client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "password123"}
        )
        assert login.status == 200
        token = (await login.json())["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        listed = await client.get("/api/v1/progress/members", headers=headers)
        assert listed.status == 200
        members = await listed.json()
        operator = next(item for item in members if item["operator"])
        assert operator["name"] == "管理员"
        assert operator["title"] == "工作台管理员"
        assigned = await client.post(
            "/api/v1/progress/tasks",
            json={"title": "自己处理", "assignee_id": operator["id"]},
            headers=headers,
        )
        assert assigned.status == 201
        assert (await assigned.json())["assignee_id"] == operator["id"]
        blocked = await client.delete(
            f"/api/v1/progress/members/{operator['id']}", headers=headers
        )
        assert blocked.status == 400

        member_response = await client.post(
            "/api/v1/progress/members",
            json={
                "name": "Rui",
                "title": "Engineer",
                "color": "#123456",
                "skills": ["Python", "工单对接"],
                "background": "主导过内部工单接口",
            },
            headers=headers,
        )
        assert member_response.status == 201
        member = await member_response.json()
        assert "username" not in member
        assert member["skills"] == ["Python", "工单对接"]
        assert member["background"] == "主导过内部工单接口"

        created = await client.post(
            "/api/v1/progress/tasks",
            json={
                "title": "API task",
                "assignee_id": member["id"],
                "start_date": "2026-09-01",
                "due_date": "2026-09-02",
                "progress": 25,
                "estimated_hours": 8,
            },
            headers=headers,
        )
        assert created.status == 201
        task = await created.json()

        form = FormData()
        form.add_field("file", b"png-bytes", filename="shot.png", content_type="image/png")
        uploaded = await client.post(
            f"/api/v1/progress/tasks/{task['id']}/resources/file",
            data=form,
            headers=headers,
        )
        assert uploaded.status == 201
        body = await uploaded.json()
        resource_id = body["resources"][0]["id"]
        downloaded = await client.get(
            f"/api/v1/progress/tasks/{task['id']}/resources/{resource_id}/file",
            headers=headers,
        )
        assert downloaded.status == 200
        assert await downloaded.read() == b"png-bytes"
        linked = await client.post(
            f"/api/v1/progress/tasks/{task['id']}/resources/link",
            json={"name": "规格", "url": "https://example.test/spec"},
            headers=headers,
        )
        assert linked.status == 201
        assert (await linked.json())["resources"][1]["kind"] == "link"
        dashboard = await client.get("/api/v1/progress/dashboard", headers=headers)
        assert (await dashboard.json())["total"] == 2
        assert (await client.get("/api/v1/tasks", headers=headers)).status == 404
    finally:
        await client.close()


async def test_member_evaluation_endpoints() -> None:
    app = create_app(
        Settings(admin_password="password123"),
        user_repository=MemoryUserRepository(),
        task_repository=MemoryTaskRepository(),
        member_repository=MemoryMemberRepository(),
        project_repository=MemoryProjectRepository(),
        ai_repository=MemoryAISettingsRepository(),
        resource_storage=MemoryResourceStorage(),
        **knowledge_overrides(),
    )
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        login = await client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "password123"}
        )
        token = (await login.json())["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        member = await (
            await client.post(
                "/api/v1/progress/members",
                json={"name": "Rui", "title": "Engineer"},
                headers=headers,
            )
        ).json()

        added = await client.post(
            f"/api/v1/progress/members/{member['id']}/evaluations",
            json={"kind": "highlight", "content": "联调推进很稳"},
            headers=headers,
        )
        assert added.status == 201
        updated = await added.json()
        assert updated["evaluations"][0]["kind"] == "highlight"
        assert updated["evaluations"][0]["content"] == "联调推进很稳"
        evaluation_id = updated["evaluations"][0]["id"]

        rejected = await client.post(
            f"/api/v1/progress/members/{member['id']}/evaluations",
            json={"kind": "bad", "content": "x"},
            headers=headers,
        )
        assert rejected.status == 422

        removed = await client.delete(
            f"/api/v1/progress/members/{member['id']}/evaluations/{evaluation_id}",
            headers=headers,
        )
        assert removed.status == 200
        assert (await removed.json())["evaluations"] == []

        missing = await client.delete(
            f"/api/v1/progress/members/{member['id']}/evaluations/{evaluation_id}",
            headers=headers,
        )
        assert missing.status == 404
    finally:
        await client.close()


async def test_project_crud_and_task_linkage() -> None:
    app = create_app(
        Settings(admin_password="password123"),
        user_repository=MemoryUserRepository(),
        task_repository=MemoryTaskRepository(),
        member_repository=MemoryMemberRepository(),
        project_repository=MemoryProjectRepository(),
        ai_repository=MemoryAISettingsRepository(),
        resource_storage=MemoryResourceStorage(),
        **knowledge_overrides(),
    )
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        login = await client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "password123"}
        )
        headers = {"Authorization": f"Bearer {(await login.json())['access_token']}"}
        member = await (
            await client.post(
                "/api/v1/progress/members",
                json={"name": "Rui", "title": "Engineer"},
                headers=headers,
            )
        ).json()

        created = await client.post(
            "/api/v1/progress/projects",
            json={
                "name": "MYAI 工单平台",
                "description": "工单系统二期",
                "background": "沿用现有审批流",
                "started_at": "2026-09-01",
                "member_ids": [member["id"]],
                "status": "active",
                "cover_color": "#36d9e9",
            },
            headers=headers,
        )
        assert created.status == 201
        project = await created.json()
        assert project["name"] == "MYAI 工单平台"
        assert project["started_at"] == "2026-09-01"
        assert project["member_ids"] == [member["id"]]
        assert project["status"] == "active"
        assert project["cover_color"] == "#36d9e9"

        rejected = await client.post(
            "/api/v1/progress/projects",
            json={"name": "坏颜色", "cover_color": "蓝色"},
            headers=headers,
        )
        assert rejected.status == 400

        status_update = await client.patch(
            f"/api/v1/progress/projects/{project['id']}",
            json={"status": "archived"},
            headers=headers,
        )
        assert status_update.status == 200
        assert (await status_update.json())["status"] == "archived"

        duplicate = await client.post(
            "/api/v1/progress/projects",
            json={"name": "myai 工单平台"},
            headers=headers,
        )
        assert duplicate.status == 400

        linked = await client.post(
            "/api/v1/progress/tasks",
            json={"title": "联调回调", "project_id": project["id"], "assignee_id": member["id"]},
            headers=headers,
        )
        assert linked.status == 201
        assert (await linked.json())["project_id"] == project["id"]

        bad_link = await client.post(
            "/api/v1/progress/tasks",
            json={"title": "悬空任务", "project_id": "nope"},
            headers=headers,
        )
        assert bad_link.status == 400

        free = await client.post(
            "/api/v1/progress/tasks",
            json={"title": "独立任务"},
            headers=headers,
        )
        assert (await free.json())["project_id"] is None

        updated = await client.patch(
            f"/api/v1/progress/projects/{project['id']}",
            json={"member_ids": []},
            headers=headers,
        )
        assert updated.status == 200
        assert (await updated.json())["member_ids"] == []

        deleted = await client.delete(
            f"/api/v1/progress/projects/{project['id']}", headers=headers
        )
        assert deleted.status == 200
        tasks = await (await client.get("/api/v1/progress/tasks", headers=headers)).json()
        assert all(task["project_id"] is None for task in tasks)
        remaining = await (await client.get("/api/v1/progress/projects", headers=headers)).json()
        assert remaining == []
    finally:
        await client.close()


async def test_api_requires_authentication() -> None:
    app = create_app(
        Settings(),
        user_repository=MemoryUserRepository(),
        task_repository=MemoryTaskRepository(),
        member_repository=MemoryMemberRepository(),
        project_repository=MemoryProjectRepository(),
        ai_repository=MemoryAISettingsRepository(),
        resource_storage=MemoryResourceStorage(),
        **knowledge_overrides(),
    )
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        result = await client.get("/api/v1/progress/tasks")
        assert result.status == 401
    finally:
        await client.close()


async def test_ai_settings_secret_requires_admin_and_returns_plaintext_on_demand() -> None:
    security = SecurityService("test-secret-with-at-least-32-characters", 60)
    app = create_app(
        Settings(admin_password="password123"),
        security=security,
        user_repository=MemoryUserRepository(),
        task_repository=MemoryTaskRepository(),
        member_repository=MemoryMemberRepository(),
        project_repository=MemoryProjectRepository(),
        ai_repository=MemoryAISettingsRepository(),
        resource_storage=MemoryResourceStorage(),
        **knowledge_overrides(),
    )
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        secret_path = "/api/v1/ai-settings/secret"
        assert (await client.get(secret_path)).status == 401

        member_token = security.issue_access_token("member", "member")
        member_headers = {"Authorization": f"Bearer {member_token}"}
        assert (await client.get(secret_path, headers=member_headers)).status == 403
        assert (
            await client.get("/api/v1/progress/members", headers=member_headers)
        ).status == 403
        assert (
            await client.get("/api/v1/progress/tasks", headers=member_headers)
        ).status == 200

        login = await client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "password123"}
        )
        admin_headers = {
            "Authorization": f"Bearer {(await login.json())['access_token']}"
        }
        assert (await client.get(secret_path, headers=admin_headers)).status == 404

        plain_key = "sk-private-api-key"
        saved = await client.put(
            "/api/v1/ai-settings",
            json={
                "base_url": "https://example.test/v1",
                "model": "test-model",
                "api_key": plain_key,
            },
            headers=admin_headers,
        )
        saved_body = await saved.json()
        assert saved.status == 200
        assert saved_body["api_key_masked"] != plain_key
        assert "api_key" not in saved_body

        public_body = await (
            await client.get("/api/v1/ai-settings", headers=admin_headers)
        ).json()
        assert public_body["api_key_masked"] == saved_body["api_key_masked"]
        assert "api_key" not in public_body

        secret = await client.get(secret_path, headers=admin_headers)
        assert secret.status == 200
        assert await secret.json() == {"api_key": plain_key}
    finally:
        await client.close()


async def test_ai_tools_registry_requires_admin_and_lists_modules() -> None:
    security = SecurityService("test-secret-with-at-least-32-characters", 60)
    app = create_app(
        Settings(admin_password="password123"),
        security=security,
        user_repository=MemoryUserRepository(),
        task_repository=MemoryTaskRepository(),
        member_repository=MemoryMemberRepository(),
        project_repository=MemoryProjectRepository(),
        ai_repository=MemoryAISettingsRepository(),
        resource_storage=MemoryResourceStorage(),
        **knowledge_overrides(),
    )
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        tools_path = "/api/v1/ai-settings/tools"
        assert (await client.get(tools_path)).status == 401
        member_token = security.issue_access_token("member", "member")
        assert (
            await client.get(tools_path, headers={"Authorization": f"Bearer {member_token}"})
        ).status == 403

        login = await client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "password123"}
        )
        headers = {"Authorization": f"Bearer {(await login.json())['access_token']}"}
        result = await client.get(tools_path, headers=headers)
        assert result.status == 200
        modules = (await result.json())["modules"]
        by_id = {item["id"]: item for item in modules}
        assert set(by_id) == {"progress", "knowledge"}
        tool_names = {tool["name"] for tool in by_id["progress"]["tools"]}
        assert "record_member_evaluation" in tool_names
        evaluation_tool = next(
            tool for tool in by_id["progress"]["tools"]
            if tool["name"] == "record_member_evaluation"
        )
        assert evaluation_tool["description"]
        kind = next(param for param in evaluation_tool["parameters"] if param["name"] == "kind")
        assert kind["required"] is True
        assert kind["values"] == ["highlight", "risk", "note"]
        content = next(
            param for param in evaluation_tool["parameters"] if param["name"] == "content"
        )
        assert content["required"] is True
        name = next(param for param in evaluation_tool["parameters"] if param["name"] == "name")
        assert name["required"] is False
        assert name["type"] == "string | null"
    finally:
        await client.close()


async def test_cors_preflight_and_origin_allowlist() -> None:
    security = SecurityService("test-secret-with-at-least-32-characters", 60)
    app = create_app(
        Settings(
            admin_password="password123",
            cors_origins="https://desktop.example, https://web.example/",
        ),
        security=security,
        user_repository=MemoryUserRepository(),
        task_repository=MemoryTaskRepository(),
        member_repository=MemoryMemberRepository(),
        project_repository=MemoryProjectRepository(),
        ai_repository=MemoryAISettingsRepository(),
        resource_storage=MemoryResourceStorage(),
        **knowledge_overrides(),
    )
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        preflight = await client.options(
            "/api/v1/progress/tasks",
            headers={
                "Origin": "https://desktop.example",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization, content-type",
            },
        )
        assert preflight.status == 204
        assert preflight.headers["Access-Control-Allow-Origin"] == "https://desktop.example"
        assert "Authorization" in preflight.headers["Access-Control-Allow-Headers"]

        tauri_preflight = await client.options(
            "/api/v1/progress/tasks",
            headers={"Origin": "tauri://localhost", "Access-Control-Request-Method": "POST"},
        )
        assert tauri_preflight.status == 204
        assert tauri_preflight.headers["Access-Control-Allow-Origin"] == "tauri://localhost"

        blocked_preflight = await client.options(
            "/api/v1/progress/tasks",
            headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
        )
        assert blocked_preflight.status == 403

        login = await client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "password123"}
        )
        headers = {"Authorization": f"Bearer {(await login.json())['access_token']}"}
        allowed = await client.get(
            "/api/v1/progress/tasks", headers={**headers, "Origin": "https://web.example"}
        )
        assert allowed.status == 200
        assert allowed.headers["Access-Control-Allow-Origin"] == "https://web.example"

        denied = await client.get(
            "/api/v1/progress/tasks", headers={**headers, "Origin": "https://evil.example"}
        )
        assert denied.status == 200
        assert "Access-Control-Allow-Origin" not in denied.headers
    finally:
        await client.close()


async def test_ai_stream_endpoint_sends_cors_headers_for_desktop_shell() -> None:
    app = create_app(
        Settings(admin_password="password123"),
        user_repository=MemoryUserRepository(),
        task_repository=MemoryTaskRepository(),
        member_repository=MemoryMemberRepository(),
        project_repository=MemoryProjectRepository(),
        ai_repository=MemoryAISettingsRepository(),
        resource_storage=MemoryResourceStorage(),
        **knowledge_overrides(),
    )
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        login = await client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "password123"}
        )
        headers = {
            "Authorization": f"Bearer {(await login.json())['access_token']}",
            "Origin": "tauri://localhost",
        }
        # 流式响应在路由内部 prepare，CORS 头必须在写出前就位
        response = await client.post(
            "/api/v1/ai/run", json={"instruction": "hi"}, headers=headers
        )
        assert response.status == 200
        assert response.headers["Access-Control-Allow-Origin"] == "tauri://localhost"
        assert "text/event-stream" in response.headers["Content-Type"]
    finally:
        await client.close()
