"""
Local filesystem storage backend implementation.

本地文件系统存储后端实现。
"""

import os
from collections.abc import Iterator
from pathlib import Path

from app.storage.base import StorageBackend


class LocalStorage(StorageBackend):
    """
    Local filesystem storage backend.
    """

    def __init__(self, base_path: str):
        """
        Initialize local storage at the given base directory.

        在指定基础目录初始化本地存储。
        """
        self._base_path = Path(base_path)
        self._base_path.mkdir(parents=True, exist_ok=True)

    def _full_path(self, key: str) -> Path:
        path = self._base_path / key
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def save(self, key: str, data: bytes) -> str:
        """
        Save data to a file and return its path.

        将数据保存到文件并返回路径。
        """
        path = self._full_path(key)
        path.write_bytes(data)
        return str(path)

    def get_url(self, key: str) -> str:
        """
        Get the local file path as a URL.

        获取本地文件路径作为 URL。
        """
        return str(self._base_path / key)

    def exists(self, key: str) -> bool:
        """
        Check if the file exists at the given key.

        检查给定 key 的文件是否存在。
        """
        return self._full_path(key).exists()

    def get_file_stream(self, key: str) -> Iterator[bytes]:
        """
        Stream file content in chunks.

        以分块方式流式读取文件内容。
        """
        path = self._full_path(key)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                yield chunk

    def get_file_size(self, key: str) -> int:
        """
        Get file size in bytes.

        获取文件大小（字节）。
        """
        path = self._full_path(key)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return os.path.getsize(path)
