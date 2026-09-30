from __future__ import annotations

import re
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

from system.ports import DesktopReleaseInfo

DESKTOP_ASSET_NAME = "Workbench-macos-aarch64.dmg"
DESKTOP_LATEST_TAG = "desktop-latest"
_VERSION_IN_NAME = re.compile(r"(\d+\.\d+\.\d+(?:\+[0-9a-fA-F]+)?)")


class GithubCommitClient:
    def __init__(self, *, base_url: str = "https://api.github.com") -> None:
        self.base_url = base_url.rstrip("/")

    def _headers(
        self, token: str, *, accept: str = "application/vnd.github+json"
    ) -> dict[str, str]:
        headers = {
            "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "workbench-update-check",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def _get_json(self, url: str, token: str) -> Any:
        # sock_connect 单独设短超时，避免 DNS/建连挂死被前端收成 Network Error
        timeout = ClientTimeout(total=25, sock_connect=8)
        try:
            async with ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=self._headers(token)) as resp:
                    if resp.status == 404:
                        raise LookupError(
                            f"未找到资源 {url}；私有仓需配置 WORKBENCH_UPDATE_GITHUB_TOKEN"
                        )
                    if resp.status in {401, 403}:
                        text = await resp.text()
                        if "rate limit" in text.lower():
                            raise ValueError(
                                "GitHub API 速率受限；请配置 WORKBENCH_UPDATE_GITHUB_TOKEN"
                            )
                        raise ValueError(
                            "GitHub API 拒绝访问；请检查 WORKBENCH_UPDATE_GITHUB_TOKEN 权限"
                        )
                    if resp.status >= 400:
                        text = await resp.text()
                        raise ValueError(f"GitHub API 错误 {resp.status}: {text[:200]}")
                    return await resp.json()
        except TimeoutError as exc:
            raise ValueError("检查更新超时（无法在时限内访问 GitHub），请稍后重试") from exc
        except ClientError as exc:
            raise ValueError(f"无法连接 GitHub：{exc}") from exc

    def _parse_release(self, data: dict[str, Any]) -> DesktopReleaseInfo:
        raw_assets = data.get("assets")
        assets: list[Any] = raw_assets if isinstance(raw_assets, list) else []
        asset: dict[str, Any] | None = None
        for item in assets:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "")
            if name == DESKTOP_ASSET_NAME or name.endswith(".dmg"):
                asset = item
                if name == DESKTOP_ASSET_NAME:
                    break
        if asset is None:
            raise LookupError("Release 中未找到 macOS DMG 资产")
        asset_id = asset.get("id")
        if not isinstance(asset_id, int):
            raise ValueError("Release 资产信息不完整")
        tag = str(data.get("tag_name") or "")
        name = str(data.get("name") or "")
        body = str(data.get("body") or "")
        version = ""
        for source in (name, body, tag):
            matched = _VERSION_IN_NAME.search(source)
            if matched:
                version = matched.group(1)
                break
        if not version:
            version = tag or "unknown"
        return DesktopReleaseInfo(
            tag=tag,
            version=version,
            asset_id=asset_id,
            asset_name=str(asset.get("name") or DESKTOP_ASSET_NAME),
            published_at=str(data.get("published_at") or data.get("created_at") or ""),
            target_commitish=str(data.get("target_commitish") or ""),
        )

    async def desktop_release(self, repo: str, token: str) -> DesktopReleaseInfo:
        try:
            data = await self._get_json(
                f"{self.base_url}/repos/{repo}/releases/tags/{DESKTOP_LATEST_TAG}",
                token,
            )
            if isinstance(data, dict):
                return self._parse_release(data)
        except LookupError:
            pass
        releases = await self._get_json(f"{self.base_url}/repos/{repo}/releases?per_page=20", token)
        if not isinstance(releases, list):
            raise LookupError("未找到可用的桌面端 Release")
        for item in releases:
            if not isinstance(item, dict) or item.get("draft"):
                continue
            try:
                return self._parse_release(item)
            except LookupError:
                continue
        raise LookupError(
            f"未找到桌面端 Release（优先 tag `{DESKTOP_LATEST_TAG}`）；"
            "请确认 CI 已发布 DMG，私有仓需配置 WORKBENCH_UPDATE_GITHUB_TOKEN"
        )

    async def download_release_asset(
        self, repo: str, asset_id: int, token: str
    ) -> tuple[bytes, str]:
        url = f"{self.base_url}/repos/{repo}/releases/assets/{asset_id}"
        timeout = ClientTimeout(total=600, sock_connect=15)
        try:
            async with ClientSession(timeout=timeout) as session:
                async with session.get(
                    url,
                    headers=self._headers(token, accept="application/octet-stream"),
                    allow_redirects=True,
                ) as resp:
                    if resp.status == 404:
                        raise LookupError("未找到 DMG 资产")
                    if resp.status in {401, 403}:
                        text = await resp.text()
                        if "rate limit" in text.lower():
                            raise ValueError(
                                "下载 DMG 触发 GitHub 速率限制；"
                                "请配置 WORKBENCH_UPDATE_GITHUB_TOKEN"
                            )
                        raise ValueError(
                            "下载 DMG 被拒绝；请检查 WORKBENCH_UPDATE_GITHUB_TOKEN 权限"
                        )
                    if resp.status >= 400:
                        text = await resp.text()
                        raise ValueError(f"下载 DMG 失败 {resp.status}: {text[:200]}")
                    data = await resp.read()
                    content_type = resp.headers.get("Content-Type", "application/octet-stream")
                    return data, content_type
        except TimeoutError as exc:
            raise ValueError("下载 DMG 超时") from exc
        except ClientError as exc:
            raise ValueError(f"无法下载 DMG：{exc}") from exc
