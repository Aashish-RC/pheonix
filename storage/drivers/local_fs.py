"""
Pheonix Local Filesystem Storage Driver
Persists binary blobs atomically into local directory hierarchy.
"""

from pathlib import Path
from typing import Optional
from .base import StorageDriver


class LocalFileSystemDriver(StorageDriver):
    """Stores binary objects on local filesystem."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir or Path.home() / ".pheonix" / "storage")
        self.blobs_dir = self.base_dir / "blobs"
        self.blobs_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, key: str) -> Path:
        # Prevent directory traversal
        clean_key = Path(key).name
        return self.blobs_dir / clean_key

    def write_blob(self, key: str, data: bytes) -> int:
        target = self._resolve_path(key)
        # Atomic write via temporary file
        temp_file = target.with_suffix(".tmp")
        with open(temp_file, "wb") as f:
            f.write(data)
        temp_file.replace(target)
        return len(data)

    def read_blob(self, key: str) -> bytes:
        target = self._resolve_path(key)
        if not target.exists():
            raise FileNotFoundError(f"Storage blob '{key}' not found at {target}")
        with open(target, "rb") as f:
            return f.read()

    def delete_blob(self, key: str) -> bool:
        target = self._resolve_path(key)
        if target.exists():
            target.unlink()
            return True
        return False

    def exists(self, key: str) -> bool:
        return self._resolve_path(key).exists()

    def get_size(self, key: str) -> int:
        target = self._resolve_path(key)
        if not target.exists():
            return 0
        return target.stat().st_size
