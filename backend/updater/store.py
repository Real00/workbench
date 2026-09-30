from __future__ import annotations

import fcntl
import json
import os
import tempfile
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from updater.protocol import ACTIVE_STATES


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".state-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(name).unlink(missing_ok=True)


class UpdateStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def read(self) -> dict[str, Any]:
        path = self.root / "state.json"
        if not path.exists():
            return {
                "current": "base",
                "previous": "base",
                "pending": None,
                "status": {"id": "", "state": "idle", "message": "", "finished_at": None},
            }
        result: dict[str, Any] = json.loads(path.read_text())
        return result

    @contextmanager
    def edit(self) -> Iterator[dict[str, Any]]:
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / "state.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            data = self.read()
            yield data
            atomic_json(self.root / "state.json", data)

    def available(self) -> bool:
        try:
            return time.time() - (self.root / "heartbeat").stat().st_mtime < 15
        except FileNotFoundError:
            return False

    def enqueue(self) -> dict[str, Any]:
        with self.edit() as state:
            if state["status"]["state"] in ACTIVE_STATES:
                raise ValueError("已有更新正在进行，请等待完成")
            request_id = uuid.uuid4().hex
            state["status"] = self.status(request_id, "queued", "更新已排队")
        return {"accepted": True, "request_id": request_id, "message": "更新已排队"}

    @staticmethod
    def status(request_id: str, phase: str, message: str) -> dict[str, Any]:
        return {
            "id": request_id,
            "state": phase,
            "phase": phase,
            "message": message,
            "finished_at": datetime.now(UTC).isoformat()
            if phase in {"succeeded", "failed"}
            else None,
        }

    def report(self, request_id: str, phase: str, message: str) -> None:
        with self.edit() as state:
            state["status"] = self.status(request_id, phase, message)
