"""
Pheonix Storage Driver Interface
Abstract definition for physical asset persistence (Local FS, MinIO, S3).
"""

from abc import ABC, abstractmethod


class StorageDriver(ABC):
    """Abstract interface for storing raw binary blobs."""

    @abstractmethod
    def write_blob(self, key: str, data: bytes) -> int:
        """Writes raw bytes to storage under key. Returns number of bytes written."""
        pass

    @abstractmethod
    def read_blob(self, key: str) -> bytes:
        """Reads raw bytes for key. Raises FileNotFoundError if missing."""
        pass

    @abstractmethod
    def delete_blob(self, key: str) -> bool:
        """Deletes raw blob. Returns True if deleted, False if not found."""
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Checks if key exists in storage."""
        pass

    @abstractmethod
    def get_size(self, key: str) -> int:
        """Returns byte size of stored blob."""
        pass
