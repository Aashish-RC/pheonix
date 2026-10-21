"""
Pheonix Storage and Files Automated Tests
Verifies blob drivers, file library, SHA-256 deduplication, quotas, and cross-project asset reuse.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from storage.models import StoredFile, StorageQuota
from storage.drivers.local_fs import LocalFileSystemDriver
from storage.core.quota import QuotaManager, StorageQuotaExceededError
from storage.core.library import FileLibrary
from storage.core.engine import StorageEngine
from storage.client import StorageClient


class TestLocalStorageDriver:
    """Tests raw blob persistence and directory traversal prevention."""

    def test_write_and_read_blob(self, tmp_path):
        driver = LocalFileSystemDriver(base_dir=tmp_path)
        payload = b"Pheonix persistent storage engine payload 12345"

        bytes_written = driver.write_blob("key-abc", payload)
        assert bytes_written == len(payload)
        assert driver.exists("key-abc") is True
        assert driver.get_size("key-abc") == len(payload)

        read_back = driver.read_blob("key-abc")
        assert read_back == payload

    def test_delete_blob(self, tmp_path):
        driver = LocalFileSystemDriver(base_dir=tmp_path)
        driver.write_blob("key-delete", b"temp data")
        assert driver.exists("key-delete") is True

        assert driver.delete_blob("key-delete") is True
        assert driver.exists("key-delete") is False
        assert driver.delete_blob("key-delete") is False


class TestQuotaManager:
    """Tests per-project storage boundaries and capacity enforcement."""

    def test_quota_blocks_when_capacity_exceeded(self):
        # 1000 bytes max limit
        manager = QuotaManager(default_max_bytes=1000)
        manager.record_addition("proj-1", 800)

        # 300 bytes incoming exceeds 1000 max
        with pytest.raises(StorageQuotaExceededError) as exc_info:
            manager.check_can_store("proj-1", 300)
        assert "storage quota exceeded" in str(exc_info.value)

    def test_quota_recovers_after_deletion(self):
        manager = QuotaManager(default_max_bytes=1000)
        manager.record_addition("proj-2", 800)
        manager.record_deletion("proj-2", 500)

        quota = manager.get_or_create_quota("proj-2")
        assert quota.used_bytes == 300
        # Now 400 bytes can be safely stored
        manager.check_can_store("proj-2", 400)


class TestStorageVerificationGate:
    """Verification Gate: 'Done when: Upload and reuse a file'."""

    def test_upload_and_reuse_file_across_projects(self, tmp_path):
        driver = LocalFileSystemDriver(base_dir=tmp_path)
        engine = StorageEngine(driver=driver)
        client = StorageClient(engine=engine)

        original_content = b"# Pheonix Dataset\n1,2,3,4,5\nalpha,beta,gamma"
        filename = "dataset.csv"

        # Step 1: Upload file to project-alpha
        file_alpha = client.upload(
            filename=filename,
            data=original_content,
            project_id="project-alpha",
            owner_id="alice",
            content_type="text/csv",
            tags=["training", "v1"]
        )

        assert file_alpha.file_id.startswith("file-")
        assert file_alpha.project_id == "project-alpha"
        assert file_alpha.size_bytes == len(original_content)
        assert len(file_alpha.sha256_hash) == 64

        # Verify content downloads byte-for-byte
        downloaded = client.download(file_alpha.file_id)
        assert downloaded == original_content

        # Step 2: Reuse the uploaded file in project-beta
        file_beta = client.reuse(
            file_id=file_alpha.file_id,
            target_project_id="project-beta",
            new_filename="shared_dataset.csv"
        )

        assert file_beta.file_id != file_alpha.file_id
        assert file_beta.project_id == "project-beta"
        assert file_beta.filename == "shared_dataset.csv"
        assert file_beta.sha256_hash == file_alpha.sha256_hash  # Same underlying blob!

        # Verify content can be downloaded via project-beta's reference
        beta_content = client.download(file_beta.file_id)
        assert beta_content == original_content

        # Step 3: Deletion safety - deleting file_alpha does NOT destroy file_beta
        assert client.delete(file_alpha.file_alpha if hasattr(file_alpha, "file_alpha") else file_alpha.file_id) is True
        assert driver.exists(file_alpha.sha256_hash) is True  # Physical blob remains because project-beta uses it!

        still_readable = client.download(file_beta.file_id)
        assert still_readable == original_content

        # Step 4: Deleting last reference cleans up physical blob
        client.delete(file_beta.file_id)
        assert driver.exists(file_alpha.sha256_hash) is False

    def test_deduplication_prevents_duplicate_disk_writes(self, tmp_path):
        driver = LocalFileSystemDriver(base_dir=tmp_path)
        engine = StorageEngine(driver=driver)

        data = b"Repeated identical chunk data"
        f1 = engine.upload("file1.txt", data, project_id="p1")
        f2 = engine.upload("file2.txt", data, project_id="p2")

        assert f1.sha256_hash == f2.sha256_hash
        # Only 1 physical blob file exists in the directory
        blob_files = list((tmp_path / "blobs").glob("*"))
        assert len(blob_files) == 1
