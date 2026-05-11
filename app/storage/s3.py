from collections.abc import Iterator

import boto3
from botocore.config import Config as BotoConfig

from app.storage.base import StorageBackend


class S3Storage(StorageBackend):
    """S3-compatible storage backend (works with AWS, Aliyun OSS, MinIO, etc.)."""

    def __init__(
        self,
        endpoint: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: str = "",
    ):
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=BotoConfig(signature_version="s3v4"),
        )
        self._ensure_bucket()

    def _ensure_bucket(self):
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except Exception:
            self._client.create_bucket(Bucket=self._bucket)

    def save(self, key: str, data: bytes) -> str:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data)
        return key

    def get_url(self, key: str) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=3600,
        )

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except Exception:
            return False

    def get_file_stream(self, key: str) -> Iterator[bytes]:
        resp = self._client.get_object(Bucket=self._bucket, Key=key)
        yield from resp["Body"].iter_chunks(8192)

    def get_file_size(self, key: str) -> int:
        resp = self._client.head_object(Bucket=self._bucket, Key=key)
        return resp["ContentLength"]
