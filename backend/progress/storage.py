from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class ResourceStorage(Protocol):
    async def put(self, key: str, data: bytes) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def read(self, key: str) -> bytes: ...
    def path_for(self, key: str) -> Path | None: ...


@dataclass
class StoredFile:
    content_type: str
    filename: str
    inline: bool
    path: Path | None = None
    data: bytes | None = None


class FilesystemResourceStorage:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def _resolve(self, key: str) -> Path:
        candidate = (self.root / key).resolve()
        if not candidate.is_relative_to(self.root):
            raise ValueError("invalid storage key")
        return candidate

    async def put(self, key: str, data: bytes) -> None:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    async def delete(self, key: str) -> None:
        path = self._resolve(key)
        if path.is_file():
            path.unlink()

    async def read(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.is_file():
            raise LookupError("resource file not found")
        return path.read_bytes()

    def path_for(self, key: str) -> Path | None:
        path = self._resolve(key)
        return path if path.is_file() else None
