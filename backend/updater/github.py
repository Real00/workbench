from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from updater.protocol import Release, architecture


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: Request, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> Request | None:
        host = urlparse(newurl).hostname or ""
        if urlparse(newurl).scheme != "https" or not (
            host == "github.com"
            or host == "api.github.com"
            or host.endswith(".githubusercontent.com")
        ):
            raise ValueError("更新下载重定向到不受信任的地址")
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected and host != urlparse(req.full_url).hostname:
            redirected.remove_header("Authorization")
        return redirected


class ReleaseClient:
    def __init__(self, repo: str, token: str = "", tag: str = "server-latest") -> None:
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
            raise ValueError("更新仓库格式无效")
        if not re.fullmatch(r"[\w.-]+", tag):
            raise ValueError("更新频道格式无效")
        self.base = f"https://api.github.com/repos/{repo}"
        self.token = token
        self.tag = tag
        self.opener = build_opener(SafeRedirect())

    def _open(self, url: str, *, binary: bool = False) -> Any:
        headers = {
            "User-Agent": "workbench-updater",
            "Accept": "application/octet-stream" if binary else "application/vnd.github+json",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            return self.opener.open(Request(url, headers=headers), timeout=30)
        except HTTPError as exc:
            if exc.code == 404:
                raise ValueError("未找到已发布的服务端更新包；私有仓需配置 GitHub token") from exc
            raise ValueError(f"GitHub 下载失败（HTTP {exc.code}），请检查网络或 token") from exc
        except (URLError, TimeoutError) as exc:
            raise ValueError("无法连接 GitHub，请稍后重试") from exc

    def _json(self, url: str, *, binary: bool = False) -> Any:
        with self._open(url, binary=binary) as response:
            data = response.read(2 * 1024 * 1024 + 1)
        if len(data) > 2 * 1024 * 1024:
            raise ValueError("更新清单过大")
        return json.loads(data)

    def asset_url(self, tag: str, name: str) -> str:
        data = self._json(f"{self.base}/releases/tags/{tag}")
        for asset in data.get("assets", []):
            if asset.get("name") == name and isinstance(asset.get("id"), int):
                return f"{self.base}/releases/assets/{asset['id']}"
        raise ValueError(f"发布版本中缺少 {name}")

    def latest(self) -> Release:
        url = self.asset_url(self.tag, f"workbench-linux-{architecture()}.json")
        return Release.parse(self._json(url, binary=True))

    def download(self, release: Release, destination: Path) -> None:
        url = self.asset_url(release.tag, release.asset)
        digest = hashlib.sha256()
        size = 0
        started = time.monotonic()
        with self._open(url, binary=True) as response, destination.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > release.size or time.monotonic() - started > 600:
                    raise ValueError("更新包超出大小或下载时间限制")
                digest.update(chunk)
                output.write(chunk)
        if size != release.size or digest.hexdigest() != release.sha256:
            raise ValueError("更新包校验失败，当前版本未改变")
