"""
Pheonix File Library & Deduplication Engine
Maintains metadata indexing, SHA-256 deduplication, and cross-project asset reuse.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from ..models import StoredFile


class FileLibrary:
    """Manages file metadata indexing and content-addressed deduplication."""

    def __init__(self):
        self._files: Dict[str, StoredFile] = {}
        # Maps sha256_hash -> set of file_ids referencing that blob
        self._blob_refs: Dict[str, set[str]] = {}

    def add_file(self, file: StoredFile) -> None:
        self._files[file.file_id] = file
        if file.sha256_hash not in self._blob_refs:
            self._blob_refs[file.sha256_hash] = set()
        self._blob_refs[file.sha256_hash].add(file.file_id)

    def get_file(self, file_id: str) -> Optional[StoredFile]:
        return self._files.get(file_id)

    def find_by_hash(self, sha256_hash: str) -> Optional[StoredFile]:
        """Finds any existing file sharing the identical SHA-256 payload."""
        refs = self._blob_refs.get(sha256_hash)
        if refs:
            first_id = next(iter(refs))
            return self._files.get(first_id)
        return None

    def list_files(self, project_id: Optional[str] = None) -> List[StoredFile]:
        files = list(self._files.values())
        if project_id:
            files = [f for f in files if f.project_id == project_id]
        return files

    def reuse_file(
        self,
        source_file_id: str,
        target_project_id: str,
        target_owner_id: Optional[str] = None,
        new_filename: Optional[str] = None
    ) -> StoredFile:
        """
        Creates a new project-scoped file reference pointing to the identical underlying blob.
        Zero duplication of physical storage blocks.
        """
        source = self.get_file(source_file_id)
        if not source:
            raise FileNotFoundError(f"Source file '{source_file_id}' not found in library.")

        new_file_id = f"file-{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        reused = StoredFile(
            file_id=new_file_id,
            filename=new_filename or source.filename,
            content_type=source.content_type,
            size_bytes=source.size_bytes,
            sha256_hash=source.sha256_hash,
            project_id=target_project_id,
            owner_id=target_owner_id or source.owner_id,
            created_at=now_iso,
            uri=f"pheonix://files/{new_file_id}",
            tags=list(source.tags)
        )

        self.add_file(reused)
        return reused

    def remove_file(self, file_id: str) -> Tuple[Optional[StoredFile], bool]:
        """
        Removes file from library.
        Returns (removed_file, should_delete_physical_blob).
        Physical blob is only marked for deletion when reference count reaches zero.
        """
        file = self._files.pop(file_id, None)
        if not file:
            return None, False

        refs = self._blob_refs.get(file.sha256_hash, set())
        refs.discard(file_id)

        should_delete_blob = False
        if len(refs) == 0:
            self._blob_refs.pop(file.sha256_hash, None)
            should_delete_blob = True

        return file, should_delete_blob
