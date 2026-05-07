from abc import ABC, abstractmethod
from collections.abc import Iterator


class StorageBackend(ABC):
    """Abstract base class for file storage backends."""

    @abstractmethod
    def save(self, key: str, data: bytes) -> str:
        """Save data and return the storage path/key."""
        ...

    @abstractmethod
    def get_url(self, key: str) -> str:
        """Get a public or presigned URL for the file."""
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if a file exists at the given key."""
        ...

    @abstractmethod
    def get_file_stream(self, key: str) -> Iterator[bytes]:
        """Stream file content in chunks."""
        ...

    @abstractmethod
    def get_file_size(self, key: str) -> int:
        """Get file size in bytes."""
        ...
