"""
Pheonix S3 / MinIO Cloud Storage Driver
Persists binary blobs into AWS S3 or MinIO object storage buckets.
"""

import os
from typing import Any, Optional
from .base import StorageDriver

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    boto3 = None  # type: ignore
    ClientError = Exception  # type: ignore


class S3Driver(StorageDriver):
    """Stores binary objects on AWS S3 or compatible object storage (MinIO, Ceph, Cloudflare R2)."""

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        region_name: Optional[str] = None,
        client: Optional[Any] = None,
        prefix: str = "blobs/",
    ):
        self.bucket_name = bucket_name or os.getenv("PHEONIX_STORAGE_S3_BUCKET", "pheonix-storage")
        self.endpoint_url = endpoint_url or os.getenv("PHEONIX_STORAGE_S3_ENDPOINT")
        self.prefix = prefix
        self.region_name = region_name or os.getenv("AWS_DEFAULT_REGION", "us-east-1")

        if client is not None:
            self._client = client
        elif boto3 is not None:
            kwargs: dict[str, Any] = {
                "region_name": self.region_name,
            }
            if self.endpoint_url:
                kwargs["endpoint_url"] = self.endpoint_url
            access_key = aws_access_key_id or os.getenv("AWS_ACCESS_KEY_ID")
            secret_key = aws_secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY")
            if access_key and secret_key:
                kwargs["aws_access_key_id"] = access_key
                kwargs["aws_secret_access_key"] = secret_key

            self._client = boto3.client("s3", **kwargs)
        else:
            self._client = None

    def _resolve_key(self, key: str) -> str:
        # Prevent directory traversal and normalize S3 key
        clean_key = os.path.basename(key)
        return f"{self.prefix}{clean_key}" if self.prefix else clean_key

    def _ensure_client(self) -> Any:
        if self._client is None:
            raise RuntimeError("boto3 client is not available or not configured for S3Driver")
        return self._client

    def write_blob(self, key: str, data: bytes) -> int:
        client = self._ensure_client()
        s3_key = self._resolve_key(key)
        client.put_object(
            Bucket=self.bucket_name,
            Key=s3_key,
            Body=data,
            ContentLength=len(data),
        )
        return len(data)

    def read_blob(self, key: str) -> bytes:
        client = self._ensure_client()
        s3_key = self._resolve_key(key)
        try:
            response = client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key,
            )
            body = response.get("Body")
            if hasattr(body, "read"):
                return body.read()
            elif isinstance(body, bytes):
                return body
            return bytes(body)
        except ClientError as e:
            error_code = ""
            if hasattr(e, "response") and isinstance(e.response, dict):
                error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("NoSuchKey", "404", "NotFound"):
                raise FileNotFoundError(f"Storage blob '{key}' not found in bucket '{self.bucket_name}'")
            raise
        except Exception as e:
            if "NoSuchKey" in str(e) or "not found" in str(e).lower() or "404" in str(e):
                raise FileNotFoundError(f"Storage blob '{key}' not found in bucket '{self.bucket_name}'")
            raise

    def delete_blob(self, key: str) -> bool:
        if not self.exists(key):
            return False
        client = self._ensure_client()
        s3_key = self._resolve_key(key)
        try:
            client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key,
            )
            return True
        except Exception:
            return False

    def exists(self, key: str) -> bool:
        client = self._ensure_client()
        s3_key = self._resolve_key(key)
        try:
            client.head_object(
                Bucket=self.bucket_name,
                Key=s3_key,
            )
            return True
        except ClientError as e:
            error_code = ""
            if hasattr(e, "response") and isinstance(e.response, dict):
                error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("404", "NoSuchKey", "NotFound"):
                return False
            return False
        except Exception:
            return False

    def get_size(self, key: str) -> int:
        client = self._ensure_client()
        s3_key = self._resolve_key(key)
        try:
            response = client.head_object(
                Bucket=self.bucket_name,
                Key=s3_key,
            )
            return int(response.get("ContentLength", 0))
        except Exception:
            return 0


class MinIODriver(S3Driver):
    """Driver optimized for local/on-prem MinIO S3-compatible object storage."""

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        region_name: str = "us-east-1",
        client: Optional[Any] = None,
        prefix: str = "blobs/",
    ):
        minio_endpoint = endpoint_url or os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
        minio_user = aws_access_key_id or os.getenv("MINIO_ROOT_USER", os.getenv("MINIO_ACCESS_KEY", "minioadmin"))
        minio_password = aws_secret_access_key or os.getenv("MINIO_ROOT_PASSWORD", os.getenv("MINIO_SECRET_KEY", "minioadmin"))
        super().__init__(
            bucket_name=bucket_name or os.getenv("MINIO_BUCKET", "pheonix-blobs"),
            endpoint_url=minio_endpoint,
            aws_access_key_id=minio_user,
            aws_secret_access_key=minio_password,
            region_name=region_name,
            client=client,
            prefix=prefix,
        )
