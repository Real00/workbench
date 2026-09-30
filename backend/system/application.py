from __future__ import annotations

import asyncio
from typing import Any

from shared.config import Settings
from system.domain import desktop_update_available, sha_matches, short_sha
from system.ports import DesktopReleaseInfo, GithubCommitLookup
from updater.github import ReleaseClient
from updater.store import UpdateStore


class SystemApplicationService:
    def __init__(
        self,
        settings: Settings,
        github: GithubCommitLookup,
        *,
        release_client: ReleaseClient | None = None,
    ) -> None:
        self.settings = settings
        self.github = github
        self.store = UpdateStore(settings.release_root) if settings.release_root else None
        self.releases = release_client or ReleaseClient(
            settings.update_github_repo,
            settings.update_github_token,
            settings.update_release_tag,
        )
        self._desktop_release: DesktopReleaseInfo | None = None

    def version(self) -> dict[str, Any]:
        sha = self.settings.git_sha or "unknown"
        return {
            "git_sha": sha,
            "git_sha_short": short_sha(sha),
            "built_at": self.settings.built_at,
            "update_enabled": bool(self.store and self.store.available()),
            "github_repo": self.settings.update_github_repo,
            "release_tag": self.settings.update_release_tag,
        }

    async def check_update(self) -> dict[str, Any]:
        release = await asyncio.to_thread(self.releases.latest)
        release.require_compatible()
        current = self.settings.git_sha or "unknown"
        return {
            "current_sha": current,
            "current_sha_short": short_sha(current),
            "latest_sha": release.git_sha,
            "latest_sha_short": short_sha(release.git_sha),
            "update_available": not sha_matches(current, release.git_sha),
            "github_repo": self.settings.update_github_repo,
            "release_tag": self.settings.update_release_tag,
        }

    def apply_update(self) -> dict[str, Any]:
        if self.store is None or not self.store.available():
            raise ValueError("内置更新器未运行，请使用支持自更新的 Docker 镜像部署")
        return self.store.enqueue()

    def update_status(self) -> dict[str, Any]:
        if self.store is None:
            return {
                "id": "",
                "state": "idle",
                "message": "当前环境不支持在线更新",
                "finished_at": None,
            }
        status: dict[str, Any] = self.store.read()["status"]
        return status

    async def check_desktop_update(self, current_version: str) -> dict[str, Any]:
        release = await self.github.desktop_release(
            self.settings.update_github_repo,
            self.settings.update_github_token,
        )
        self._desktop_release = release
        available = desktop_update_available(current_version, release.version)
        return {
            "current_version": current_version or "unknown",
            "latest_version": release.version,
            "update_available": available,
            "download_path": "/system/desktop/dmg",
            "asset_name": release.asset_name,
            "tag": release.tag,
            "published_at": release.published_at,
            "target_commitish": release.target_commitish,
            "github_repo": self.settings.update_github_repo,
        }

    async def desktop_dmg(self) -> tuple[bytes, str, str]:
        release = self._desktop_release
        if release is None:
            release = await self.github.desktop_release(
                self.settings.update_github_repo,
                self.settings.update_github_token,
            )
            self._desktop_release = release
        data, content_type = await self.github.download_release_asset(
            self.settings.update_github_repo,
            release.asset_id,
            self.settings.update_github_token,
        )
        return data, content_type, release.asset_name
