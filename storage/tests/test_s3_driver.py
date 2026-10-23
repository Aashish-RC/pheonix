"""
Unit tests for S3Driver and MinIODriver cloud storage adapters.
"""

import io
import pytest
from storage.core.engine import StorageEngine
from storage.drivers.s3 import MinIODriver, S3Driver



class FakeS3Client:
    """In-memory fake S3 client for isolated unit verification."""

    def __init__(self):
        self.objects = {}

    def put_object(self, Bucket, Key, Body, ContentLength=None):
        if hasattr(Body, "read"):
            data = Body.read()
        else:
            data = bytes(Body)
        self.objects[(Bucket, Key)] = data
        return {"ETag": "fake-etag"}

    def get_object(self, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            from botocore.exceptions import ClientError
            raise ClientError({"Error": {"Code": "NoSuchKey", "Message": "Key not found"}}, "GetObject")
        return {"Body": io.BytesIO(self.objects[(Bucket, Key)])}

    def head_object(self, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            from botocore.exceptions import ClientError
            raise ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject")
        return {"ContentLength": len(self.objects[(Bucket, Key)])}

    def delete_object(self, Bucket, Key):
        self.objects.pop((Bucket, Key), None)
        return {}


def test_s3_driver_basic_lifecycle():
    fake_client = FakeS3Client()
    driver = S3Driver(
        bucket_name="test-bucket",
        client=fake_client,
        prefix="blobs/",
    )

    data = b"Hello Pheonix S3 Driver Storage"
    key = "asset-12345"

    # Write
    written = driver.write_blob(key, data)
    assert written == len(data)
    assert driver.exists(key) is True
    assert driver.get_size(key) == len(data)

    # Read back
    read_data = driver.read_blob(key)
    assert read_data == data

    # Delete
    deleted = driver.delete_blob(key)
    assert deleted is True
    assert driver.exists(key) is False

    # Second delete returns False
    assert driver.delete_blob(key) is False


def test_s3_driver_missing_key_raises_filenotfound():
    fake_client = FakeS3Client()
    driver = S3Driver(
        bucket_name="test-bucket",
        client=fake_client,
    )

    with pytest.raises(FileNotFoundError):
        driver.read_blob("nonexistent-key")


def test_minio_driver_configuration():
    driver = MinIODriver(
        bucket_name="custom-minio-bucket",
        endpoint_url="http://127.0.0.1:9000",
        aws_access_key_id="minioadmin",
        aws_secret_access_key="minioadmin",
    )
    assert driver.bucket_name == "custom-minio-bucket"
    assert driver.endpoint_url == "http://127.0.0.1:9000"


def test_storage_engine_with_s3_driver(tmp_path):
    fake_client = FakeS3Client()
    driver = S3Driver(bucket_name="engine-bucket", client=fake_client)
    from storage.core.library import FileLibrary

    library = FileLibrary()
    engine = StorageEngine(driver=driver, library=library)

    content = b"Content-addressable S3 asset payload"
    stored = engine.upload(
        filename="report.pdf",
        data=content,
        project_id="p1",
        content_type="application/pdf",
    )

    assert stored.filename == "report.pdf"
    assert stored.size_bytes == len(content)
    assert driver.exists(stored.sha256_hash) is True

    # Download from engine
    downloaded = engine.download(stored.file_id)
    assert downloaded == content


def test_s3_driver_unconfigured_client_raises():
    driver = S3Driver(client=None)
    driver._client = None
    with pytest.raises(RuntimeError, match="boto3 client is not available"):
        driver.read_blob("any-key")


def test_s3_driver_key_normalization_and_traversal():
    driver = S3Driver(client=FakeS3Client(), prefix="safe_prefix/")
    # Traversal in key should be resolved strictly to basename
    resolved = driver._resolve_key("../../etc/passwd")
    assert resolved == "safe_prefix/passwd"


def test_s3_driver_get_size_nonexistent():
    driver = S3Driver(client=FakeS3Client())
    size = driver.get_size("nonexistent_file.bin")
    assert size == 0

