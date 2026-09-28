from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.config import Settings
from system.domain import (
    UpdateControlStore,
    UpdateRequest,
    desktop_update_available,
    sha_matches,
    short_sha,
)
from system.ports import DesktopReleaseInfo, GithubCommitLookup


class SystemApplicationService:
    def __init__(
        self,
        settings: Settings,
        github: GithubCommitLookup,
        *,
        control_store: UpdateControlStore | None = None,
    ) -> None:
        self.settings = settings
        self.github = github
        self.control_store = control_store or self._store_from_settings(settings)
        self._desktop_release: DesktopReleaseInfo | None = None

    @staticmethod
    def _store_from_settings(settings: Settings) -> UpdateControlStore | None:
        if not settings.update_control_dir or not settings.update_agent_token:
            return None
        return UpdateControlStore(Path(settings.update_control_dir), settings.update_agent_token)

    @property
    def agent_configured(self) -> bool:
        return self.control_store is not None

    def version(self) -> dict[str, Any]:
        sha = self.settings.git_sha or "unknown"
        return {
            "git_sha": sha,
            "git_sha_short": short_sha(sha),
            "built_at": self.settings.built_at or "",
            "agent_configured": self.agent_configured,
            "github_repo": self.settings.update_github_repo,
            "github_ref": self.settings.update_github_ref,
        }

    async def check_update(self) -> dict[str, Any]:
        current = self.settings.git_sha or "unknown"
        remote = await self.github.latest_sha(
            self.settings.update_github_repo,
            self.settings.update_github_ref,
            self.settings.update_github_token,
        )
        available = current == "unknown" or not sha_matches(current, remote)
        return {
            "current_sha": current,
            "current_sha_short": short_sha(current),
            "latest_sha": remote,
            "latest_sha_short": short_sha(remote),
            "update_available": available,
            "github_repo": self.settings.update_github_repo,
            "github_ref": self.settings.update_github_ref,
        }

    def apply_update(self) -> dict[str, Any]:
        if self.control_store is None:
            raise ValueError(
                "未配置更新通道：请设置 WORKBENCH_UPDATE_CONTROL_DIR 与 "
                "WORKBENCH_UPDATE_AGENT_TOKEN，并在宿主机运行 Update Agent"
            )
        request = UpdateRequest.create(self.control_store.token)
        self.control_store.write_request(request)
        return {
            "accepted": True,
            "request_id": request.id,
            "message": "更新请求已提交，服务即将短暂中断并重启",
        }

    def update_status(self) -> dict[str, Any]:
        if self.control_store is None:
            return {"id": "", "state": "idle", "message": "未配置更新通道", "finished_at": None}
        return self.control_store.read_status().to_dict()

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
