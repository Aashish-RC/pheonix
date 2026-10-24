"""
Pheonix Storage Engine
Coordinates storage drivers, file library, deduplication, and quota bounding.
"""
from typing import Any
import hashlib
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from ..models import StoredFile, StorageQuota
from ..drivers.base import StorageDriver
from ..drivers.local_fs import LocalFileSystemDriver
from .quota import QuotaManager
from .library import FileLibrary


class StorageEngine:
    """Central engine for persistent assets, deduplication, and quotas."""

    def __init__(
        self,
        driver: Optional[StorageDriver] = None,
        quota_manager: Optional[QuotaManager] = None,
        library: Optional[FileLibrary] = None,
        auto_index_knowledge: bool = True,
    ):
        self.driver = driver or LocalFileSystemDriver()
        self.quotas = quota_manager or QuotaManager()
        self.library = library or FileLibrary()
        self.auto_index_knowledge = auto_index_knowledge
        self._upload_webhooks: List[Any] = []

    def register_upload_webhook(self, callback: Any) -> None:
        """Registers a webhook/callback invoked after every successful file upload."""
        self._upload_webhooks.append(callback)

    def upload(
        self,
        filename: str,
        data: bytes,
        project_id: str = "default",
        owner_id: str = "anonymous",
        content_type: str = "application/octet-stream",
        tags: Optional[List[str]] = None,
        auto_index_knowledge: Optional[bool] = None,
    ) -> StoredFile:
        """
        Uploads an asset, applies quota limits, deduplicates using SHA-256,
        and triggers upload webhooks (including Knowledge Base indexing).
        """
        size_bytes = len(data)
        # 1. Enforce quota limits
        self.quotas.check_can_store(project_id, size_bytes)

        # 2. Compute SHA-256 hash for deduplication
        sha256_hash = hashlib.sha256(data).hexdigest()

        # 3. Content-addressable physical write (only write blob if not already on disk)
        if not self.driver.exists(sha256_hash):
            self.driver.write_blob(sha256_hash, data)

        # 4. Register in library
        file_id = f"file-{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        stored_file = StoredFile(
            file_id=file_id,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            sha256_hash=sha256_hash,
            project_id=project_id,
            owner_id=owner_id,
            created_at=now_iso,
            uri=f"pheonix://files/{file_id}",
            tags=tags or []
        )

        self.library.add_file(stored_file)
        self.quotas.record_addition(project_id, size_bytes)

        # 5. Trigger upload webhooks
        for hook in list(self._upload_webhooks):
            try:
                hook(stored_file, data)
            except Exception:
                pass

        # 6. Auto-index to knowledge if enabled
        should_index = self.auto_index_knowledge if auto_index_knowledge is None else auto_index_knowledge
        if should_index:
            try:
                from knowledge import index_document
                index_document(
                    file_id=stored_file.file_id,
                    content=data,
                    filename=stored_file.filename,
                    project_id=stored_file.project_id,
                    tags=stored_file.tags,
                )
            except Exception:
                pass

        try:
            from audit.client import get_audit_logger
            get_audit_logger().record(
                module="storage",
                action="file_uploaded",
                tenant_id=project_id,
                project_id=project_id,
                user_id=owner_id,
                resource=stored_file.file_id,
                status="success",
                details={
                    "filename": stored_file.filename,
                    "size_bytes": stored_file.size_bytes,
                    "sha256": stored_file.sha256_hash,
                },
            )
        except Exception:
            pass

        return stored_file

    def download(self, file_id: str) -> bytes:
        """Reads file payload by file identifier."""
        file = self.library.get_file(file_id)
        if not file:
            raise FileNotFoundError(f"File '{file_id}' not found.")
        return self.driver.read_blob(file.sha256_hash)

    def reuse(
        self,
        file_id: str,
        target_project_id: str,
        target_owner_id: Optional[str] = None,
        new_filename: Optional[str] = None
    ) -> StoredFile:
        """
        Reuses an existing file across projects without duplicating underlying storage blocks.
        """
        source = self.library.get_file(file_id)
        if not source:
            raise FileNotFoundError(f"Source file '{file_id}' not found.")

        # Check quota in target project
        self.quotas.check_can_store(target_project_id, source.size_bytes)

        # Link reference
        reused = self.library.reuse_file(
            source_file_id=file_id,
            target_project_id=target_project_id,
            target_owner_id=target_owner_id,
            new_filename=new_filename
        )
        self.quotas.record_addition(target_project_id, source.size_bytes)
        return reused

    def delete(self, file_id: str) -> bool:
        """Deletes file reference and frees physical block if no other references remain."""
        file, should_delete_blob = self.library.remove_file(file_id)
        if not file:
            return False

        if should_delete_blob:
            self.driver.delete_blob(file.sha256_hash)

        self.quotas.record_deletion(file.project_id, file.size_bytes)

        try:
            from audit.client import get_audit_logger
            get_audit_logger().record(
                module="storage",
                action="file_deleted",
                tenant_id=file.project_id,
                project_id=file.project_id,
                resource=file_id,
                status="success",
                details={"filename": file.filename, "size_bytes": file.size_bytes},
            )
        except Exception:
            pass

        return True

    def get_quota(self, project_id: str) -> StorageQuota:
        return self.quotas.get_or_create_quota(project_id)

    def list_files(self, project_id: Optional[str] = None) -> List[StoredFile]:
        return self.library.list_files(project_id=project_id)
