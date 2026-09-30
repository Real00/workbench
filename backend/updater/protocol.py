from __future__ import annotations

import platform
import re
from dataclasses import asdict, dataclass
from typing import Any

# Bump when Python, OS libraries, or the supervisor protocol become incompatible.
RUNTIME = "cpython312-bookworm-v1"
MAX_ARCHIVE = 1024 * 1024 * 1024
ACTIVE_STATES = {"queued", "downloading", "preparing", "restarting", "verifying"}


def architecture() -> str:
    machine = platform.machine().lower()
    return {"x86_64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(machine, machine)


@dataclass(frozen=True)
class Release:
    git_sha: str
    built_at: str
    runtime: str
    arch: str
    sha256: str
    size: int

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Release:
        try:
            release = cls(**{key: data[key] for key in cls.__dataclass_fields__})
        except (KeyError, TypeError) as exc:
            raise ValueError("更新清单字段不完整") from exc
        if not isinstance(release.git_sha, str) or not re.fullmatch(
            r"[0-9a-f]{40}", release.git_sha
        ):
            raise ValueError("更新包版本标识无效")
        if not isinstance(release.sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", release.sha256):
            raise ValueError("更新包校验信息无效")
        if release.arch not in {"amd64", "arm64"}:
            raise ValueError("更新包架构无效")
        if not isinstance(release.size, int) or not 0 < release.size <= MAX_ARCHIVE:
            raise ValueError("更新包大小无效")
        if not isinstance(release.built_at, str) or not isinstance(release.runtime, str):
            raise ValueError("更新包元信息无效")
        return release

    def require_compatible(self) -> None:
        if self.runtime != RUNTIME:
            raise ValueError("新版需要更新基础镜像，请先通过 Docker 部署新版镜像")
        if self.arch != architecture():
            raise ValueError("更新包与服务器架构不兼容")

    @property
    def tag(self) -> str:
        return f"server-{self.git_sha}"

    @property
    def asset(self) -> str:
        return f"workbench-linux-{self.arch}.tar.gz"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
