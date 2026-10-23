"""
Pheonix Storage Client SDK
High-level API for agents, memory layers, and applications to upload, download, and reuse files.
"""

from typing import List, Optional
from .models import StoredFile, StorageQuota
from .core.engine import StorageEngine


class StorageClient:
    """Client for interacting with Pheonix Storage and File Library."""

    def __init__(self, engine: Optional[StorageEngine] = None):
        self.engine = engine or StorageEngine()

    def upload(
        self,
        filename: str,
        data: bytes,
        project_id: str = "default",
        owner_id: str = "anonymous",
        content_type: str = "application/octet-stream",
        tags: Optional[List[str]] = None
    ) -> StoredFile:
        """Uploads a file to storage and registers it in the library."""
        return self.engine.upload(
            filename=filename,
            data=data,
            project_id=project_id,
            owner_id=owner_id,
            content_type=content_type,
            tags=tags
        )

    def download(self, file_id: str) -> bytes:
        """Downloads file content by file identifier."""
        return self.engine.download(file_id)

    def reuse(
        self,
        file_id: str,
        target_project_id: str,
        target_owner_id: Optional[str] = None,
        new_filename: Optional[str] = None
    ) -> StoredFile:
        """Reuses an existing file across projects without duplicating storage."""
        return self.engine.reuse(
            file_id=file_id,
            target_project_id=target_project_id,
            target_owner_id=target_owner_id,
            new_filename=new_filename
        )

    def delete(self, file_id: str) -> bool:
        """Deletes file asset and cleans up physical blob if unreferenced."""
        return self.engine.delete(file_id)

    def list_files(self, project_id: Optional[str] = None) -> List[StoredFile]:
        """Lists files in library, optionally filtered by project."""
        return self.engine.list_files(project_id=project_id)

    def get_quota(self, project_id: str) -> StorageQuota:
        """Retrieves storage quota and utilization for a project."""
        return self.engine.get_quota(project_id)

    def register_upload_webhook(self, callback) -> None:
        """Registers a callback to be invoked on file uploads."""
        self.engine.register_upload_webhook(callback)
