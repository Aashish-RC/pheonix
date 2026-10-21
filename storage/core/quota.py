"""
Pheonix Storage Quota Manager
Enforces per-project and per-tenant byte limits and file count thresholds.
"""

from typing import Dict
from ..models import StorageQuota


class StorageQuotaExceededError(Exception):
    """Raised when an upload exceeds project or tenant storage boundaries."""
    pass


class QuotaManager:
    """Tracks and enforces storage capacity per project/tenant."""

    def __init__(self, default_max_bytes: int = 104_857_600, default_max_files: int = 1000):
        self.default_max_bytes = default_max_bytes
        self.default_max_files = default_max_files
        self._quotas: Dict[str, StorageQuota] = {}

    def get_or_create_quota(self, project_id: str) -> StorageQuota:
        if project_id not in self._quotas:
            self._quotas[project_id] = StorageQuota(
                project_id=project_id,
                max_bytes=self.default_max_bytes,
                max_files=self.default_max_files,
                used_bytes=0,
                file_count=0
            )
        return self._quotas[project_id]

    def set_quota(self, project_id: str, max_bytes: int, max_files: int = 1000) -> StorageQuota:
        quota = self.get_or_create_quota(project_id)
        quota.max_bytes = max_bytes
        quota.max_files = max_files
        return quota

    def check_can_store(self, project_id: str, incoming_bytes: int) -> None:
        quota = self.get_or_create_quota(project_id)

        if quota.used_bytes + incoming_bytes > quota.max_bytes:
            raise StorageQuotaExceededError(
                f"Project '{project_id}' storage quota exceeded: "
                f"attempting to write {incoming_bytes} bytes, but only "
                f"{quota.max_bytes - quota.used_bytes} bytes remaining "
                f"(Limit: {quota.max_bytes / (1024*1024):.1f} MB)."
            )

        if quota.file_count + 1 > quota.max_files:
            raise StorageQuotaExceededError(
                f"Project '{project_id}' file count limit exceeded ({quota.max_files} files max)."
            )

    def record_addition(self, project_id: str, added_bytes: int) -> None:
        quota = self.get_or_create_quota(project_id)
        quota.used_bytes += added_bytes
        quota.file_count += 1

    def record_deletion(self, project_id: str, freed_bytes: int) -> None:
        quota = self.get_or_create_quota(project_id)
        quota.used_bytes = max(0, quota.used_bytes - freed_bytes)
        quota.file_count = max(0, quota.file_count - 1)
