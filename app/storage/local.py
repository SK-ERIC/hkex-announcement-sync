import os
from collections.abc import Iterator
from pathlib import Path

from app.storage.base import StorageBackend


class LocalStorage(StorageBackend):
    """Local filesystem storage backend."""

    def __init__(self, base_path: str):
        self._base_path = Path(base_path)
        self._base_path.mkdir(parents=True, exist_ok=True)

    def _full_path(self, key: str) -> Path:
        path = self._base_path / key
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def save(self, key: str, data: bytes) -> str:
        path = self._full_path(key)
        path.write_bytes(data)
        return str(path)

    def get_url(self, key: str) -> str:
        return str(self._base_path / key)

    def exists(self, key: str) -> bool:
        return self._full_path(key).exists()

    def get_file_stream(self, key: str) -> Iterator[bytes]:
        path = self._full_path(key)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                yield chunk

    def get_file_size(self, key: str) -> int:
        path = self._full_path(key)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return os.path.getsize(path)
