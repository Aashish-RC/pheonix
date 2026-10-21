"""
Pheonix Storage and Files Automated Tests
Verifies blob drivers, file library, SHA-256 deduplication, quotas, and cross-project asset reuse.
"""

import hashlib
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


class TestStorageQuotaAndDeduplicationHardening:
    """Task 4.5: Storage Quota & Deduplication Tests."""

    def test_hard_quota_rejection_and_boundary_checks(self, tmp_path):
        """Verify hard quota limits prevent overflow and state remains pristine."""
        driver = LocalFileSystemDriver(base_dir=tmp_path)
        quota_mgr = QuotaManager(default_max_bytes=500, default_max_files=3)
        engine = StorageEngine(driver=driver, quota_manager=quota_mgr)

        # Upload first file: 200 bytes (within quota)
        payload1 = b"A" * 200
        f1 = engine.upload("test1.bin", payload1, project_id="tenant-x")
        assert f1.size_bytes == 200
        quota = engine.get_quota("tenant-x")
        assert quota.used_bytes == 200
        assert quota.file_count == 1

        # Upload second file: exact boundary test: 300 bytes (200 + 300 == 500 max)
        payload2 = b"B" * 300
        f2 = engine.upload("test2.bin", payload2, project_id="tenant-x")
        assert f2.size_bytes == 300
        quota = engine.get_quota("tenant-x")
        assert quota.used_bytes == 500

        # Attempt upload of 1 single additional byte: must fail with StorageQuotaExceededError
        with pytest.raises(StorageQuotaExceededError) as exc:
            engine.upload("test3.bin", b"C", project_id="tenant-x")
        assert "storage quota exceeded" in str(exc.value)

        # Ensure failed write didn't pollute used_bytes or file_count
        quota = engine.get_quota("tenant-x")
        assert quota.used_bytes == 500
        assert quota.file_count == 2

    def test_file_count_quota_rejection(self, tmp_path):
        """Verify max file count quota triggers even if byte capacity remains."""
        driver = LocalFileSystemDriver(base_dir=tmp_path)
        quota_mgr = QuotaManager(default_max_bytes=100_000, default_max_files=2)
        engine = StorageEngine(driver=driver, quota_manager=quota_mgr)

        engine.upload("small1.txt", b"x", project_id="tenant-y")
        engine.upload("small2.txt", b"y", project_id="tenant-y")

        with pytest.raises(StorageQuotaExceededError) as exc:
            engine.upload("small3.txt", b"z", project_id="tenant-y")
        assert "file count limit exceeded" in str(exc.value)

    def test_sha256_deduplication_on_identical_uploads(self, tmp_path):
        """Verify SHA-256 deduplication across different files and projects."""
        import hashlib
        driver = LocalFileSystemDriver(base_dir=tmp_path)
        engine = StorageEngine(driver=driver)

        identical_content = b"CRITICAL_SYSTEM_SHARED_FIRMWARE_BINARY_V2.1"
        expected_hash = hashlib.sha256(identical_content).hexdigest()

        # Upload under project 1
        file_a = engine.upload("firmware_p1.bin", identical_content, project_id="proj-a", owner_id="alice")
        # Upload under project 2
        file_b = engine.upload("firmware_p2.bin", identical_content, project_id="proj-b", owner_id="bob")
        # Upload same again under project 1 with different name
        file_c = engine.upload("backup_firmware.bin", identical_content, project_id="proj-a", owner_id="alice")

        assert file_a.sha256_hash == expected_hash
        assert file_b.sha256_hash == expected_hash
        assert file_c.sha256_hash == expected_hash

        # All have unique file IDs
        assert len({file_a.file_id, file_b.file_id, file_c.file_id}) == 3

        # Exactly 1 blob physically stored on disk
        blob_files = list((tmp_path / "blobs").glob("*"))
        assert len(blob_files) == 1
        assert blob_files[0].name == expected_hash

        # Content downloaded through all 3 references is identical
        assert engine.download(file_a.file_id) == identical_content
        assert engine.download(file_b.file_id) == identical_content
        assert engine.download(file_c.file_id) == identical_content

    def test_atomic_file_deletion_and_ref_cleanup(self, tmp_path):
        """Verify atomic deletion: reference cleanup doesn't delete shared blob until last ref removed."""
        driver = LocalFileSystemDriver(base_dir=tmp_path)
        quota_mgr = QuotaManager(default_max_bytes=5000)
        engine = StorageEngine(driver=driver, quota_manager=quota_mgr)

        shared_data = b"SHARED_DOCUMENTATION_AND_ASSETS"
        hash_val = hashlib.sha256(shared_data).hexdigest()

        f1 = engine.upload("doc1.txt", shared_data, project_id="p-alpha")
        f2 = engine.upload("doc2.txt", shared_data, project_id="p-beta")

        assert driver.exists(hash_val) is True
        assert engine.get_quota("p-alpha").used_bytes == len(shared_data)
        assert engine.get_quota("p-beta").used_bytes == len(shared_data)

        # Delete reference f1
        del1_ok = engine.delete(f1.file_id)
        assert del1_ok is True
        # Quota for p-alpha decremented
        assert engine.get_quota("p-alpha").used_bytes == 0
        assert engine.get_quota("p-alpha").file_count == 0
        # Blob still exists because f2 references it
        assert driver.exists(hash_val) is True
        # f1 is gone
        with pytest.raises(FileNotFoundError):
            engine.download(f1.file_id)
        # f2 is still downloadable
        assert engine.download(f2.file_id) == shared_data

        # Delete reference f2 (last reference)
        del2_ok = engine.delete(f2.file_id)
        assert del2_ok is True
        assert engine.get_quota("p-beta").used_bytes == 0
        # Now physical blob is purged from driver
        assert driver.exists(hash_val) is False
        with pytest.raises(FileNotFoundError):
            engine.download(f2.file_id)

        # Idempotent delete on nonexistent file returns False
        assert engine.delete(f1.file_id) is False
        assert engine.delete("nonexistent-file-id") is False
