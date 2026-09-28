#!/usr/bin/env python3
"""宿主机 Update Agent：轮询控制目录，执行固定的 compose pull/up。

工作台容器不挂 Docker socket；仅本进程在宿主机调用 docker compose。
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

POLL_SECONDS = float(os.environ.get("UPDATE_POLL_SECONDS", "2"))
CONTROL_DIR = Path(os.environ.get("UPDATE_CONTROL_DIR", "")).expanduser()
TOKEN = os.environ.get("UPDATE_AGENT_TOKEN", "")
COMPOSE_DIR = Path(os.environ.get("COMPOSE_DIR", ".")).expanduser()
COMPOSE_FILE = os.environ.get("COMPOSE_FILE", "")  # 可选，如 compose.ghcr.yaml
COMPOSE_SERVICE = os.environ.get("COMPOSE_SERVICE", "app")
# docker compose 会读取该环境变量；与安装脚本探测到的项目名保持一致，避免挂错 volume
COMPOSE_PROJECT_NAME = os.environ.get("COMPOSE_PROJECT_NAME", "")

REQUEST_NAME = "request.json"
STATUS_NAME = "status.json"
HANDLED_NAME = "handled_request_id"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _log(message: str) -> None:
    print(f"[workbench-update-agent] {message}", flush=True)


def _sign(request_id: str, requested_at: str) -> str:
    payload = f"{request_id}|{requested_at}".encode()
    return hmac.new(TOKEN.encode(), payload, hashlib.sha256).hexdigest()


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _write_status(
    *,
    request_id: str,
    state: str,
    message: str,
    finished: bool = False,
) -> None:
    payload = {
        "id": request_id,
        "state": state,
        "message": message,
        "finished_at": _now() if finished else None,
    }
    _write_json(CONTROL_DIR / STATUS_NAME, payload)


def _compose_cmd(*args: str) -> list[str]:
    cmd = ["docker", "compose"]
    if COMPOSE_FILE:
        cmd.extend(["-f", COMPOSE_FILE])
    cmd.extend(args)
    return cmd


def _run_compose(args: list[str]) -> None:
    env = os.environ.copy()
    if COMPOSE_PROJECT_NAME:
        env["COMPOSE_PROJECT_NAME"] = COMPOSE_PROJECT_NAME
    _log(
        f"running: {' '.join(args)} (cwd={COMPOSE_DIR}"
        f"{f', project={COMPOSE_PROJECT_NAME}' if COMPOSE_PROJECT_NAME else ''})"
    )
    subprocess.run(args, cwd=COMPOSE_DIR, check=True, env=env)


def _handled_path() -> Path:
    return CONTROL_DIR / HANDLED_NAME


def _already_handled(request_id: str) -> bool:
    path = _handled_path()
    return path.is_file() and path.read_text(encoding="utf-8").strip() == request_id


def _mark_handled(request_id: str) -> None:
    _handled_path().write_text(request_id, encoding="utf-8")


def _process_request(raw: dict) -> None:
    request_id = str(raw.get("id") or "")
    requested_at = str(raw.get("requested_at") or "")
    signature = str(raw.get("signature") or "")
    if not request_id or not requested_at or not signature:
        _write_status(
            request_id=request_id,
            state="failed",
            message="request.json 字段不完整",
            finished=True,
        )
        return
    if _already_handled(request_id):
        return
    expected = _sign(request_id, requested_at)
    if not hmac.compare_digest(expected, signature):
        _log(f"invalid signature for request {request_id}")
        _write_status(
            request_id=request_id,
            state="failed",
            message="签名校验失败",
            finished=True,
        )
        _mark_handled(request_id)
        return

    _write_status(request_id=request_id, state="running", message="正在拉取并重启容器")
    try:
        _run_compose(_compose_cmd("pull", COMPOSE_SERVICE))
        _run_compose(_compose_cmd("up", "-d", COMPOSE_SERVICE))
    except subprocess.CalledProcessError as exc:
        _log(f"compose failed: {exc}")
        _write_status(
            request_id=request_id,
            state="failed",
            message=f"docker compose 失败（exit {exc.returncode}）",
            finished=True,
        )
        _mark_handled(request_id)
        return
    except FileNotFoundError:
        _write_status(
            request_id=request_id,
            state="failed",
            message="未找到 docker 或 compose 命令",
            finished=True,
        )
        _mark_handled(request_id)
        return

    _write_status(
        request_id=request_id,
        state="succeeded",
        message="已拉取最新镜像并重启 app",
        finished=True,
    )
    _mark_handled(request_id)
    _log(f"request {request_id} completed")


def _poll_once() -> None:
    request_path = CONTROL_DIR / REQUEST_NAME
    if not request_path.is_file():
        return
    try:
        raw = json.loads(request_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _log(f"cannot read request.json: {exc}")
        return
    if not isinstance(raw, dict):
        return
    _process_request(raw)


def main() -> int:
    if not CONTROL_DIR or not str(CONTROL_DIR):
        _log("UPDATE_CONTROL_DIR is required")
        return 1
    if not TOKEN:
        _log("UPDATE_AGENT_TOKEN is required")
        return 1
    if not COMPOSE_DIR.is_dir():
        _log(f"COMPOSE_DIR does not exist: {COMPOSE_DIR}")
        return 1

    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    _log(
        f"watching {CONTROL_DIR} compose_dir={COMPOSE_DIR} "
        f"file={COMPOSE_FILE or '(default)'} service={COMPOSE_SERVICE}"
    )
    while True:
        try:
            _poll_once()
        except Exception as exc:  # noqa: BLE001 — 守护进程不能因单次异常退出
            _log(f"poll error: {exc}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    sys.exit(main())
