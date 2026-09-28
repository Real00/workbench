from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

UpdateState = Literal["idle", "queued", "running", "succeeded", "failed"]


@dataclass(frozen=True)
class UpdateRequest:
    id: str
    requested_at: str
    signature: str

    @classmethod
    def create(cls, token: str, *, now: datetime | None = None) -> UpdateRequest:
        stamp = (now or datetime.now(UTC)).isoformat().replace("+00:00", "Z")
        request_id = uuid.uuid4().hex
        return cls(
            id=request_id,
            requested_at=stamp,
            signature=sign_update_request(token, request_id, stamp),
        )

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class UpdateStatus:
    id: str
    state: UpdateState
    message: str = ""
    finished_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def sign_update_request(token: str, request_id: str, requested_at: str) -> str:
    payload = f"{request_id}|{requested_at}".encode()
    return hmac.new(token.encode(), payload, hashlib.sha256).hexdigest()


def verify_update_request(token: str, request: UpdateRequest) -> bool:
    expected = sign_update_request(token, request.id, request.requested_at)
    return hmac.compare_digest(expected, request.signature)


class UpdateControlStore:
    """共享控制目录：应用写 request，宿主机 Agent 写 status。"""

    def __init__(self, control_dir: Path, token: str) -> None:
        self.control_dir = control_dir
        self.token = token
        self.request_path = control_dir / "request.json"
        self.status_path = control_dir / "status.json"

    @property
    def configured(self) -> bool:
        return bool(self.token) and self.control_dir is not None

    def ensure_dir(self) -> None:
        self.control_dir.mkdir(parents=True, exist_ok=True)

    def write_request(self, request: UpdateRequest) -> None:
        self.ensure_dir()
        tmp = self.request_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(request.to_dict(), ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.request_path)
        self.write_status(
            UpdateStatus(id=request.id, state="queued", message="等待宿主机 Update Agent 处理")
        )

    def read_status(self) -> UpdateStatus:
        if not self.status_path.is_file():
            return UpdateStatus(id="", state="idle", message="")
        raw = json.loads(self.status_path.read_text(encoding="utf-8"))
        state = raw.get("state", "idle")
        if state not in {"idle", "queued", "running", "succeeded", "failed"}:
            state = "idle"
        return UpdateStatus(
            id=str(raw.get("id") or ""),
            state=state,
            message=str(raw.get("message") or ""),
            finished_at=raw.get("finished_at"),
        )

    def write_status(self, status: UpdateStatus) -> None:
        self.ensure_dir()
        tmp = self.status_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(status.to_dict(), ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.status_path)


def short_sha(sha: str) -> str:
    return sha[:12] if sha and sha != "unknown" else sha


def sha_matches(current: str, remote: str) -> bool:
    if not current or current == "unknown" or not remote:
        return False
    return current.startswith(remote) or remote.startswith(current)
