from __future__ import annotations


def short_sha(sha: str) -> str:
    return sha[:12] if sha and sha != "unknown" else sha


def sha_matches(current: str, remote: str) -> bool:
    if not current or current == "unknown" or not remote:
        return False
    return current.startswith(remote) or remote.startswith(current)


def normalize_desktop_version(version: str) -> str:
    return version.strip().lstrip("vV")


def desktop_update_available(current: str, latest: str) -> bool:
    cur = normalize_desktop_version(current)
    lat = normalize_desktop_version(latest)
    if not lat or lat == "unknown":
        return False
    if not cur or cur in {"unknown", "0.0.0"}:
        return True
    return cur != lat
