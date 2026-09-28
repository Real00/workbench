from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class DesktopReleaseInfo:
    tag: str
    version: str
    asset_id: int
    asset_name: str
    published_at: str
    target_commitish: str


class GithubCommitLookup(Protocol):
    async def latest_sha(self, repo: str, ref: str, token: str) -> str: ...

    async def desktop_release(self, repo: str, token: str) -> DesktopReleaseInfo: ...

    async def download_release_asset(
        self, repo: str, asset_id: int, token: str
    ) -> tuple[bytes, str]: ...
