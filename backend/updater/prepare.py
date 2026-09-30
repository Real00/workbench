from __future__ import annotations

import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path, PurePosixPath

from updater.github import ReleaseClient
from updater.protocol import MAX_ARCHIVE
from updater.store import UpdateStore


def extract_bundle(archive: Path, destination: Path) -> None:
    total = 0
    seen: set[str] = set()
    with tarfile.open(archive, "r:gz") as bundle:
        for member in bundle:
            path = PurePosixPath(member.name)
            if (
                path.is_absolute()
                or ".." in path.parts
                or not path.parts
                or path.parts[0] not in {"backend", "wheels", "requirements.txt"}
                or not (member.isdir() or member.isfile())
                or member.name in seen
            ):
                raise ValueError("更新包包含不安全的文件路径或链接")
            seen.add(member.name)
            total += member.size
            if total > 3 * MAX_ARCHIVE or len(seen) > 50000:
                raise ValueError("更新包解压大小超限")
            target = destination / path
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                source = bundle.extractfile(member)
                if source is None:
                    raise ValueError("更新包文件无效")
                with source, target.open("xb") as output:
                    shutil.copyfileobj(source, output)


def run_checked(args: list[str], *, cwd: Path) -> None:
    # Do not expose subprocess output (it may contain private URLs or credentials).
    result = subprocess.run(args, cwd=cwd, capture_output=True, timeout=300)
    if result.returncode:
        raise ValueError(f"更新准备失败：{args[0]}（exit {result.returncode}）")


def prepare(store: UpdateStore, request_id: str, client: ReleaseClient) -> None:
    directory = store.root / "releases" / request_id
    archive = store.root / f"{request_id}.tar.gz"
    try:
        store.report(request_id, "downloading", "正在下载已发布的版本包…")
        release = client.latest()
        release.require_compatible()
        if store.read().get("current_sha") == release.git_sha:
            store.report(request_id, "succeeded", "当前已是最新发布版本")
            return
        directory.mkdir(parents=True)
        client.download(release, archive)
        store.report(request_id, "preparing", "正在校验并离线安装依赖…")
        extract_bundle(archive, directory)
        backend = directory / "backend"
        metadata = json.loads((backend / "release.json").read_text())
        if any(
            metadata.get(key) != value
            for key, value in release.to_dict().items()
            if key not in {"sha256", "size"}
        ):
            raise ValueError("更新包内容与发布清单不匹配")
        for required in ["static/index.html", "workbench/__main__.py", "app.py"]:
            if not (backend / required).is_file():
                raise ValueError(f"更新包缺少 {required}")
        # Create the venv at its permanent path; never move an installed venv.
        python = str(backend / ".venv/bin/python")
        run_checked(
            [
                "uv",
                "venv",
                "--python",
                "/usr/local/bin/python3",
                "--no-python-downloads",
                str(backend / ".venv"),
            ],
            cwd=directory,
        )
        run_checked(
            [
                "uv",
                "pip",
                "install",
                "--python",
                python,
                "--offline",
                "--no-index",
                "--require-hashes",
                "--find-links",
                str(directory / "wheels"),
                "-r",
                str(directory / "requirements.txt"),
            ],
            cwd=directory,
        )
        run_checked([python, "-c", "from app import create_app; create_app()"], cwd=backend)
        with store.edit() as state:
            state["pending"] = {"release": request_id, "id": request_id}
            state["status"] = store.status(request_id, "restarting", "新版已就绪，正在重启…")
    except Exception as exc:
        shutil.rmtree(directory, ignore_errors=True)
        store.report(request_id, "failed", f"更新失败，继续使用原版本：{exc}")
    finally:
        archive.unlink(missing_ok=True)


def main(request_id: str) -> None:
    store = UpdateStore(Path(os.environ["WORKBENCH_RELEASE_ROOT"]))
    client = ReleaseClient(
        os.environ.get("WORKBENCH_UPDATE_GITHUB_REPO", "real00/workbench"),
        os.environ.get("WORKBENCH_UPDATE_GITHUB_TOKEN", ""),
        os.environ.get("WORKBENCH_UPDATE_RELEASE_TAG", "server-latest"),
    )
    prepare(store, request_id, client)
