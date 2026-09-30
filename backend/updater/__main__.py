from __future__ import annotations

import fcntl
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from updater.protocol import ACTIVE_STATES, RUNTIME, architecture
from updater.store import UpdateStore


class Supervisor:
    def __init__(self, root: Path, base: Path, *, timeout: float = 90) -> None:
        self.store = UpdateStore(root)
        self.base = base
        self.timeout = timeout
        self.stopping = False
        self.child: subprocess.Popen[bytes] | None = None
        self.worker: subprocess.Popen[bytes] | None = None
        self.worker_started = 0.0

    def directory(self, release: str) -> Path:
        if release == "base":
            return self.base
        if not re.fullmatch(r"[0-9a-f]{32}", release):
            raise ValueError("保存的版本目录无效")
        return self.store.root / "releases" / release / "backend"

    def metadata(self, release: str) -> dict[str, Any]:
        result: dict[str, Any] = json.loads((self.directory(release) / "release.json").read_text())
        if result["runtime"] != RUNTIME or result["arch"] != architecture():
            raise ValueError("已安装版本与基础镜像不兼容")
        return result

    def heartbeat(self) -> None:
        (self.store.root / "heartbeat").touch()

    def recover(self) -> str:
        base_sha = self.metadata("base")["git_sha"]
        with self.store.edit() as state:
            status = state["status"]
            if state.get("pending") or status["state"] in ACTIVE_STATES - {"queued"}:
                state["status"] = self.store.status(
                    status["id"], "failed", "上次更新被中断，已恢复原版本"
                )
                state["pending"] = None
            if state.get("image_sha", base_sha) != base_sha:
                state["previous"] = "base"
                state["current"] = "base"
                state["status"] = self.store.status(status["id"], "idle", "已启动新基础镜像")
            state["image_sha"] = base_sha
            try:
                self.metadata(state["current"])
            except (ValueError, OSError, KeyError):
                state["current"] = "base"
                state["status"] = self.store.status(
                    status["id"], "failed", "版本不兼容，已恢复镜像版本"
                )
            state["current_sha"] = self.metadata(state["current"])["git_sha"]
            return str(state["current"])

    @staticmethod
    def stop(process: subprocess.Popen[bytes] | None) -> None:
        if process is None or process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            process.wait()
            return
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()

    def start(self, release: str) -> tuple[str, str]:
        directory = self.directory(release)
        metadata = self.metadata(release)
        instance = uuid.uuid4().hex
        env = os.environ.copy()
        env.update(
            {
                "WORKBENCH_GIT_SHA": metadata["git_sha"],
                "WORKBENCH_BUILT_AT": metadata["built_at"],
                "WORKBENCH_STATIC_DIR": str(directory / "static"),
                "WORKBENCH_RELEASE_ROOT": str(self.store.root),
                "WORKBENCH_INSTANCE_ID": instance,
                "PYTHONPATH": str(directory),
            }
        )
        self.child = subprocess.Popen(
            [str(directory / ".venv/bin/python"), "-m", "workbench"],
            cwd=directory,
            env=env,
            start_new_session=True,
        )
        return instance, str(metadata["git_sha"])

    def healthy(self, instance: str, sha: str) -> bool:
        port = int(os.environ.get("WORKBENCH_DEV_API_PORT", "8080"))
        try:
            with urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as response:
                data = json.load(response)
            return data.get("instance") == instance and data.get("git_sha") == sha
        except (OSError, URLError, ValueError):
            return False

    def wait_ready(self, identity: tuple[str, str]) -> bool:
        deadline = time.monotonic() + self.timeout
        consecutive = 0
        while not self.stopping and time.monotonic() < deadline:
            self.heartbeat()
            if self.child is None or self.child.poll() is not None:
                return False
            consecutive = consecutive + 1 if self.healthy(*identity) else 0
            if consecutive >= 3:
                return True
            time.sleep(1)
        return False

    def activate(self, pending: dict[str, Any]) -> bool:
        self.stop(self.child)
        request_id = pending["id"]
        self.store.report(request_id, "verifying", "正在验证新版服务…")
        ready = False
        try:
            ready = self.wait_ready(self.start(pending["release"]))
        except (OSError, ValueError, KeyError):
            pass
        if self.stopping:
            return False  # Leave pending on disk; next boot recovers the last committed version.
        if ready:
            with self.store.edit() as state:
                state["previous"] = state["current"]
                state["current"] = pending["release"]
                state["current_sha"] = self.metadata(pending["release"])["git_sha"]
                state["pending"] = None
                state["status"] = self.store.status(request_id, "succeeded", "新版已启动并通过检查")
            self.prune()
            return True
        self.stop(self.child)
        current = self.store.read()["current"]
        with self.store.edit() as state:
            state["pending"] = None
            state["status"] = self.store.status(
                request_id, "failed", "新版启动失败，已回退到原版本"
            )
        recovered = self.wait_ready(self.start(current))
        if recovered:
            self.prune()
        return recovered

    def prune(self) -> None:
        state = self.store.read()
        keep = {state["current"], state["previous"]}
        for archive in self.store.root.glob("*.tar.gz"):
            if re.fullmatch(r"[0-9a-f]{32}\.tar\.gz", archive.name):
                archive.unlink()
        releases = self.store.root / "releases"
        if releases.exists():
            for directory in releases.iterdir():
                if directory.name not in keep and re.fullmatch(r"[0-9a-f]{32}", directory.name):
                    shutil.rmtree(directory)

    def run(self) -> int:
        self.store.root.mkdir(parents=True, exist_ok=True)
        with (self.store.root / "supervisor.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            signal.signal(signal.SIGTERM, self.shutdown)
            signal.signal(signal.SIGINT, self.shutdown)
            try:
                current = self.recover()
                self.prune()
                if not self.wait_ready(self.start(current)):
                    return 1
                while not self.stopping:
                    self.heartbeat()
                    state = self.store.read()
                    if self.worker is not None and time.monotonic() - self.worker_started > 1200:
                        self.stop(self.worker)
                        self.worker = None
                        with self.store.edit() as interrupted:
                            interrupted["pending"] = None
                            interrupted["status"] = self.store.status(
                                state["status"]["id"],
                                "failed",
                                "更新准备超时，保留原版本",
                            )
                        self.prune()
                        state = self.store.read()
                    if self.worker is not None and self.worker.poll() is not None:
                        self.worker = None
                        if not state.get("pending") and state["status"]["state"] in ACTIVE_STATES:
                            self.store.report(state["status"]["id"], "failed", "更新准备进程中断")
                        state = self.store.read()
                    if state.get("pending") and self.worker is None:
                        if not self.activate(state["pending"]):
                            return 1
                    elif state["status"]["state"] == "queued" and self.worker is None:
                        self.worker_started = time.monotonic()
                        self.worker = subprocess.Popen(
                            [sys.executable, "-m", "updater", "--prepare", state["status"]["id"]],
                            start_new_session=True,
                        )
                    if self.child is None or self.child.poll() is not None:
                        return 1
                    time.sleep(1)
                return 0
            finally:
                self.stop(self.worker)
                self.stop(self.child)
                (self.store.root / "heartbeat").unlink(missing_ok=True)

    def shutdown(self, *_: Any) -> None:
        self.stopping = True


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--prepare":
        from updater.prepare import main as prepare_main

        prepare_main(sys.argv[2])
        return 0
    return Supervisor(Path(os.environ["WORKBENCH_RELEASE_ROOT"]), Path("/app/backend")).run()


if __name__ == "__main__":
    sys.exit(main())
