"""Build a platform-specific offline update bundle inside the runtime image."""
from __future__ import annotations

import hashlib
import json
import os
import tarfile
from datetime import UTC, datetime
from pathlib import Path

from updater.protocol import RUNTIME, architecture


def metadata() -> dict[str, str]:
    return {
        "git_sha": os.environ.get("WORKBENCH_GIT_SHA", "unknown"),
        "built_at": os.environ.get("WORKBENCH_BUILT_AT") or datetime.now(UTC).isoformat(),
        "runtime": RUNTIME,
        "arch": architecture(),
    }


def main() -> None:
    backend = Path("/app/backend")
    info = metadata()
    (backend / "release.json").write_text(json.dumps(info))
    if os.environ.get("METADATA_ONLY"):
        return
    output = Path("/output")
    output.mkdir(exist_ok=True)
    name = f"workbench-linux-{info['arch']}"
    archive = output / f"{name}.tar.gz"
    excluded = {".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "tests"}
    with tarfile.open(archive, "w:gz") as bundle:
        for path in sorted(backend.rglob("*")):
            relative = path.relative_to(backend)
            if path.is_file() and not any(part in excluded for part in relative.parts):
                bundle.add(path, arcname=str(Path("backend") / relative), recursive=False)
        bundle.add("/bundle/wheels", arcname="wheels")
        bundle.add("/bundle/requirements.txt", arcname="requirements.txt")
    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    manifest = {**info, "sha256": digest, "size": archive.stat().st_size}
    (output / f"{name}.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
