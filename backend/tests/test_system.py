from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

from app import create_app
from shared.config import Settings
from shared.web_keys import SECURITY
from system.application import SystemApplicationService
from system.domain import desktop_update_available, sha_matches
from system.ports import DesktopReleaseInfo
from tests.fakes import (
    MemoryAISettingsRepository,
    MemoryDeviceRepository,
    MemoryMemberRepository,
    MemoryProjectRepository,
    MemoryResourceStorage,
    MemorySkillsRepository,
    MemoryTaskRepository,
    MemoryUserRepository,
    knowledge_overrides,
)
from updater.protocol import RUNTIME, Release, architecture
from updater.store import UpdateStore


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


class FakeReleases:
    def latest(self) -> Release:
        return Release("b" * 40, "2026-09-30", RUNTIME, architecture(), "f" * 64, 100)


def test_apply_requires_supervisor() -> None:
    service = SystemApplicationService(Settings(), FakeGithub())
    assert service.version()["update_enabled"] is False
    with pytest.raises(ValueError, match="内置更新器未运行"):
        service.apply_update()


@pytest.mark.asyncio
async def test_check_update_uses_published_bundle() -> None:
    service = SystemApplicationService(
        Settings(git_sha="a" * 40),
        FakeGithub(),
        release_client=FakeReleases(),
    )
    result = await service.check_update()
    assert result["update_available"] is True
    assert result["latest_sha"] == "b" * 40
    service.settings.git_sha = "b" * 40
    assert (await service.check_update())["update_available"] is False


@pytest.mark.asyncio
async def test_system_routes_admin_only(tmp_path: Path) -> None:
    store = UpdateStore(tmp_path / "releases")
    settings = Settings(
        admin_password="password123",
        git_sha="1111111111111111",
        built_at="2026-03-28T00:00:00Z",
        release_root=tmp_path / "releases",
    )
    store.root.mkdir()
    (store.root / "heartbeat").touch()
    app = create_app(
        settings,
        user_repository=MemoryUserRepository(),
        device_repository=MemoryDeviceRepository(),
        task_repository=MemoryTaskRepository(),
        member_repository=MemoryMemberRepository(),
        project_repository=MemoryProjectRepository(),
        ai_repository=MemoryAISettingsRepository(),
        ai_skills_repository=MemorySkillsRepository(),
        resource_storage=MemoryResourceStorage(),
        github_commits=FakeGithub(sha="2222222222222222"),
        release_client=FakeReleases(),
        **knowledge_overrides(),
    )
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        denied = await client.get("/api/v1/system/version")
        assert denied.status == 401

        user_token = app[SECURITY].issue_access_token("reader", "user")
        forbidden = await client.post(
            "/api/v1/system/updates/apply",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert forbidden.status == 403
        assert not (store.root / "state.json").exists()

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
        assert body["update_enabled"] is True

        check = await client.post("/api/v1/system/updates/check", headers=headers)
        assert check.status == 200
        assert (await check.json())["update_available"] is True

        apply = await client.post("/api/v1/system/updates/apply", headers=headers)
        assert apply.status == 200
        applied = await apply.json()
        assert applied["accepted"] is True
        assert (tmp_path / "releases" / "state.json").is_file()

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
        assert dmg.headers.get("Content-Disposition", "").endswith(
            'filename="Workbench-macos-aarch64.dmg"'
        )
        assert await dmg.read() == b"dmg-bytes-placeholder-xxxx"
    finally:
        await client.close()
