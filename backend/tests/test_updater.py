from __future__ import annotations

import hashlib
import io
import json
import os
import signal
import socket
import subprocess
import sys
import tarfile
import threading
import time
from pathlib import Path
from urllib.request import Request

import pytest

from updater.__main__ import Supervisor
from updater.github import ReleaseClient, SafeRedirect
from updater.prepare import extract_bundle, prepare
from updater.protocol import RUNTIME, Release, architecture
from updater.store import UpdateStore, atomic_json


def release(**changes):
    return Release(
        **{
            "git_sha": "a" * 40,
            "built_at": "2026-09-30",
            "runtime": RUNTIME,
            "arch": architecture(),
            "sha256": "b" * 64,
            "size": 10,
            **changes,
        }
    )


def test_duplicate_requests_and_stale_supervisor(tmp_path):
    store = UpdateStore(tmp_path)
    assert not store.available()
    (tmp_path / "heartbeat").touch()
    assert store.available()
    errors = []
    accepted = []

    def enqueue():
        try:
            accepted.append(store.enqueue())
        except ValueError as exc:
            errors.append(exc)

    threads = [threading.Thread(target=enqueue) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(accepted) == 1
    assert len(errors) == 7
    os.utime(tmp_path / "heartbeat", (1, 1))
    assert not store.available()


@pytest.mark.parametrize(
    "name,kind",
    [
        ("../escape", tarfile.REGTYPE),
        ("/tmp/escape", tarfile.REGTYPE),
        ("backend/link", tarfile.SYMTYPE),
        ("backend/link", tarfile.LNKTYPE),
        ("backend/device", tarfile.CHRTYPE),
    ],
)
def test_reject_unsafe_archive(tmp_path, name, kind):
    archive = tmp_path / "bundle.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        info = tarfile.TarInfo(name)
        info.type = kind
        info.linkname = "../../escape"
        bundle.addfile(info)
    with pytest.raises(ValueError, match="不安全"):
        extract_bundle(archive, tmp_path / "out")
    assert not (tmp_path / "escape").exists()


def test_download_hash_and_size_checked(tmp_path, monkeypatch):
    client = ReleaseClient("owner/repo")
    monkeypatch.setattr(client, "asset_url", lambda *_: "https://api.github.com/asset")
    monkeypatch.setattr(client, "_open", lambda *_, **__: io.BytesIO(b"archive"))
    data = release(size=7, sha256=hashlib.sha256(b"archive").hexdigest())
    client.download(data, tmp_path / "good")
    with pytest.raises(ValueError, match="校验失败"):
        client.download(release(size=7), tmp_path / "bad")
    with pytest.raises(ValueError, match="大小"):
        client.download(release(size=3), tmp_path / "large")


def test_redirect_strips_token():
    request = Request("https://api.github.com/asset", headers={"Authorization": "Bearer secret"})
    redirected = SafeRedirect().redirect_request(
        request,
        None,
        302,
        "Found",
        {},
        "https://release-assets.githubusercontent.com/asset",
    )
    assert redirected is not None and not redirected.has_header("Authorization")
    with pytest.raises(ValueError):
        SafeRedirect().redirect_request(request, None, 302, "Found", {}, "https://evil.test/asset")


def test_incompatible_release():
    with pytest.raises(ValueError, match="基础镜像"):
        release(runtime="future").require_compatible()


class BundleClient:
    def __init__(self, bad_dependency=False):
        self.bad_dependency = bad_dependency

    def latest(self):
        return release()

    def download(self, _, destination):
        with tarfile.open(destination, "w:gz") as bundle:
            metadata = release().to_dict()
            for name, value in {
                "backend/release.json": json.dumps(metadata).encode(),
                "backend/static/index.html": b"new frontend",
                "backend/workbench/__main__.py": b"",
                "backend/app.py": b"",
                "requirements.txt": b"",
            }.items():
                info = tarfile.TarInfo(name)
                info.size = len(value)
                bundle.addfile(info, io.BytesIO(value))


@pytest.mark.parametrize("fail", [False, True])
def test_preparation_does_not_modify_running_version(tmp_path, monkeypatch, fail):
    store = UpdateStore(tmp_path)
    request_id = store.enqueue()["request_id"]
    commands = []

    def run(args, *, cwd):
        commands.append(args)
        if fail:
            raise ValueError("dependency install failed")

    monkeypatch.setattr("updater.prepare.run_checked", run)
    prepare(store, request_id, BundleClient())
    state = store.read()
    assert state["current"] == "base"
    if fail:
        assert state["pending"] is None
        assert state["status"]["state"] == "failed"
        assert not (tmp_path / "releases" / request_id).exists()
    else:
        assert state["pending"]["release"] == request_id
        assert "--offline" in commands[1]
        assert "--require-hashes" in commands[1]
        assert str(tmp_path / "releases" / request_id / "backend/.venv/bin/python") in commands[1]


def make_app(directory: Path, sha: str, *, broken=False):
    directory.mkdir(parents=True, exist_ok=True)
    atomic_json(directory / "release.json", release(git_sha=sha).to_dict())
    (directory / ".venv/bin").mkdir(parents=True)
    (directory / ".venv/bin/python").symlink_to(sys.executable)
    (directory / "workbench").mkdir()
    (directory / "workbench/__main__.py").write_text(
        "raise SystemExit(1)"
        if broken
        else """
import json, os
from http.server import HTTPServer, BaseHTTPRequestHandler
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps({"instance": os.environ["WORKBENCH_INSTANCE_ID"],
                                    "git_sha": os.environ["WORKBENCH_GIT_SHA"]}).encode())
    def log_message(self, *args): pass
HTTPServer(("127.0.0.1", int(os.environ["WORKBENCH_DEV_API_PORT"])), Handler).serve_forever()
"""
    )


@pytest.fixture
def supervisor(tmp_path, monkeypatch):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    monkeypatch.setenv("WORKBENCH_DEV_API_PORT", str(port))
    base = tmp_path / "base"
    make_app(base, "a" * 40)
    instance = Supervisor(tmp_path / "updates", base, timeout=5)
    instance.recover()
    yield instance
    instance.stop(instance.child)


@pytest.mark.parametrize("broken", [False, True])
def test_real_process_activation_and_rollback(supervisor, broken):
    request_id = "b" * 32
    make_app(supervisor.directory(request_id), "b" * 40, broken=broken)
    pending = {"id": request_id, "release": request_id}
    with supervisor.store.edit() as state:
        state["pending"] = pending
    assert supervisor.activate(pending)
    state = supervisor.store.read()
    assert state["pending"] is None
    assert state["current"] == ("base" if broken else request_id)
    assert state["status"]["state"] == ("failed" if broken else "succeeded")
    assert supervisor.child.poll() is None


def test_interrupted_activation_keeps_committed_version(supervisor):
    with supervisor.store.edit() as state:
        state["pending"] = {"id": "b" * 32, "release": "b" * 32}
        state["status"] = supervisor.store.status("b" * 32, "verifying", "")
    assert supervisor.recover() == "base"
    assert supervisor.store.read()["status"]["state"] == "failed"
    assert supervisor.store.read()["pending"] is None


def test_same_image_retains_update_new_image_uses_base(supervisor):
    request_id = "b" * 32
    make_app(supervisor.directory(request_id), "b" * 40)
    with supervisor.store.edit() as state:
        state["current"] = request_id
    assert supervisor.recover() == request_id
    atomic_json(supervisor.base / "release.json", release(git_sha="c" * 40).to_dict())
    assert supervisor.recover() == "base"


def test_shutdown_is_forwarded_to_application(supervisor, monkeypatch):
    root = supervisor.store.root
    env = os.environ.copy()
    env["WORKBENCH_RELEASE_ROOT"] = str(root)
    code = (
        "from pathlib import Path; from updater.__main__ import Supervisor; "
        f"raise SystemExit(Supervisor(Path({str(root)!r}), Path({str(supervisor.base)!r})).run())"
    )
    process = subprocess.Popen([sys.executable, "-c", code], env=env)
    try:
        deadline = time.monotonic() + 10
        while not (root / "heartbeat").exists() and time.monotonic() < deadline:
            time.sleep(0.1)
        assert (root / "heartbeat").exists()
        process.send_signal(signal.SIGTERM)
        process.wait(timeout=10)
        assert not (root / "heartbeat").exists()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


def test_latest_version_skips_download(tmp_path):
    store = UpdateStore(tmp_path)
    request_id = store.enqueue()["request_id"]
    with store.edit() as state:
        state["current_sha"] = "a" * 40
    prepare(store, request_id, BundleClient())
    assert store.read()["status"]["state"] == "succeeded"
    assert store.read()["pending"] is None
    assert not (tmp_path / "releases").exists()


@pytest.mark.parametrize("manifest", [{}, {"git_sha": None}, None])
def test_invalid_manifest_is_validation_error(manifest):
    with pytest.raises(ValueError):
        Release.parse(manifest)
