from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

from app import create_app
from shared.config import Settings
from system.application import SystemApplicationService
from system.domain import (
    UpdateControlStore,
    UpdateRequest,
    desktop_update_available,
    sha_matches,
    sign_update_request,
    verify_update_request,
)
from system.ports import DesktopReleaseInfo
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


class FakeGithub:
    def __init__(
        self,
        sha: str = "abc123def456",
        error: Exception | None = None,
        *,
        desktop: DesktopReleaseInfo | None = None,
        dmg: bytes = b"dmg-bytes-placeholder-xxxx",
    ) -> None:
        self.sha = sha
        self.error = error
        self.desktop = desktop or DesktopReleaseInfo(
            tag="desktop-latest",
            version="0.1.0+bbbbbbb",
            asset_id=42,
            asset_name="Workbench-macos-aarch64.dmg",
            published_at="2026-09-28T00:00:00Z",
            target_commitish="bbbbbbb",
        )
        self.dmg = dmg
        self.calls: list[tuple[str, str, str]] = []
        self.desktop_calls: list[tuple[str, str]] = []
        self.download_calls: list[tuple[str, int, str]] = []

    async def latest_sha(self, repo: str, ref: str, token: str) -> str:
        self.calls.append((repo, ref, token))
        if self.error:
            raise self.error
        return self.sha

    async def desktop_release(self, repo: str, token: str) -> DesktopReleaseInfo:
        self.desktop_calls.append((repo, token))
        if self.error:
            raise self.error
        return self.desktop

    async def download_release_asset(
        self, repo: str, asset_id: int, token: str
    ) -> tuple[bytes, str]:
        self.download_calls.append((repo, asset_id, token))
        if self.error:
            raise self.error
        return self.dmg, "application/octet-stream"


def test_hmac_roundtrip() -> None:
    request = UpdateRequest.create("secret-token")
    assert verify_update_request("secret-token", request)
    assert not verify_update_request("wrong", request)
    expected = sign_update_request("secret-token", request.id, request.requested_at)
    assert expected == request.signature


def test_sha_matches_prefix() -> None:
    assert sha_matches("abcdef1234567890", "abcdef123456")
    assert sha_matches("abcdef123456", "abcdef1234567890")
    assert not sha_matches("unknown", "abcdef")
    assert not sha_matches("aaaa", "bbbb")


def test_desktop_update_available() -> None:
    assert desktop_update_available("0.1.0+aaaaaaa", "0.1.0+bbbbbbb") is True
    assert desktop_update_available("0.1.0+bbbbbbb", "0.1.0+bbbbbbb") is False
    assert desktop_update_available("", "0.1.0+bbbbbbb") is True
    assert desktop_update_available("0.1.0", "unknown") is False


def test_control_store_write_and_status(tmp_path: Path) -> None:
    store = UpdateControlStore(tmp_path, "tok")
    request = UpdateRequest.create("tok")
    store.write_request(request)
    assert (tmp_path / "request.json").is_file()
    status = store.read_status()
    assert status.state == "queued"
    assert status.id == request.id


def test_apply_requires_agent() -> None:
    settings = Settings(git_sha="deadbeef", update_control_dir=None, update_agent_token="")
    service = SystemApplicationService(settings, FakeGithub())
    assert service.version()["agent_configured"] is False
    with pytest.raises(ValueError, match="未配置更新通道"):
        service.apply_update()


@pytest.mark.asyncio
async def test_check_update_compares_sha() -> None:
    settings = Settings(
        git_sha="aaaaaaaaaaaaaaaa",
        update_github_repo="real00/workbench",
        update_github_ref="main",
        update_github_token="ghp_test",
    )
    github = FakeGithub(sha="bbbbbbbbbbbbbbbb")
    service = SystemApplicationService(settings, github)
    result = await service.check_update()
    assert result["update_available"] is True
    assert result["latest_sha_short"] == "bbbbbbbbbbbb"
    assert github.calls == [("real00/workbench", "main", "ghp_test")]

    settings_same = Settings(git_sha="bbbbbbbbbbbbbbbb")
    same = await SystemApplicationService(
        settings_same, FakeGithub(sha="bbbbbbbbbbbbbbbb")
    ).check_update()
    assert same["update_available"] is False


@pytest.mark.asyncio
async def test_system_routes_admin_only(tmp_path: Path) -> None:
    store = UpdateControlStore(tmp_path / "control", "shared-secret")
    settings = Settings(
        admin_password="password123",
        git_sha="1111111111111111",
        built_at="2026-03-28T00:00:00Z",
        update_control_dir=tmp_path / "control",
        update_agent_token="shared-secret",
    )
    app = create_app(
        settings,
        user_repository=MemoryUserRepository(),
        device_repository=MemoryDeviceRepository(),
        task_repository=MemoryTaskRepository(),
        member_repository=MemoryMemberRepository(),
        project_repository=MemoryProjectRepository(),
        ai_repository=MemoryAISettingsRepository(),
        resource_storage=MemoryResourceStorage(),
        github_commits=FakeGithub(sha="2222222222222222"),
        update_control_store=store,
        **knowledge_overrides(),
    )
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        denied = await client.get("/api/v1/system/version")
        assert denied.status == 401

        login = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "password123"},
        )
        assert login.status == 200
        token = (await login.json())["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        version = await client.get("/api/v1/system/version", headers=headers)
        assert version.status == 200
        body = await version.json()
        assert body["git_sha_short"] == "111111111111"
        assert body["agent_configured"] is True

        check = await client.post("/api/v1/system/updates/check", headers=headers)
        assert check.status == 200
        assert (await check.json())["update_available"] is True

        apply = await client.post("/api/v1/system/updates/apply", headers=headers)
        assert apply.status == 200
        applied = await apply.json()
        assert applied["accepted"] is True
        assert (tmp_path / "control" / "request.json").is_file()

        status = await client.get("/api/v1/system/updates/status", headers=headers)
        assert status.status == 200
        assert (await status.json())["state"] == "queued"

        desktop = await client.get(
            "/api/v1/system/desktop/update",
            params={"current": "0.1.0+aaaaaaa"},
            headers=headers,
        )
        assert desktop.status == 200
        desktop_body = await desktop.json()
        assert desktop_body["update_available"] is True
        assert desktop_body["latest_version"] == "0.1.0+bbbbbbb"
        assert desktop_body["download_path"] == "/system/desktop/dmg"

        dmg = await client.get("/api/v1/system/desktop/dmg", headers=headers)
        assert dmg.status == 200
        assert dmg.headers.get("Content-Disposition", "").endswith('filename="Workbench-macos-aarch64.dmg"')
        assert await dmg.read() == b"dmg-bytes-placeholder-xxxx"
    finally:
        await client.close()
