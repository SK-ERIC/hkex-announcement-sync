"""
S3-compatible storage backend implementation.

S3 兼容存储后端实现。
"""

from collections.abc import Iterator

import boto3
from botocore.config import Config as BotoConfig

from app.storage.base import StorageBackend


class S3Storage(StorageBackend):
    """
    S3-compatible storage backend (works with AWS, Aliyun OSS, MinIO, etc.).
    """

    def __init__(
        self,
        endpoint: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: str = "",
    ):
        """
            Initialize S3 storage with connection credentials.

        使用连接凭证初始化 S3 存储。
        """
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
        """
            Upload data to S3 and return the key.

        上传数据到 S3 并返回 key。
        """
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data)
        return key

    def get_url(self, key: str) -> str:
        """
            Generate a presigned download URL for the file.

        生成文件的预签名下载 URL。
        """
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=3600,
        )

    def exists(self, key: str) -> bool:
        """
            Check if an object exists in the S3 bucket.

        检查 S3 桶中对象是否存在。
        """
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except Exception:
            return False

    def get_file_stream(self, key: str) -> Iterator[bytes]:
        """
            Stream object content in chunks from S3.

        从 S3 以分块方式流式读取对象内容。
        """
        resp = self._client.get_object(Bucket=self._bucket, Key=key)
        yield from resp["Body"].iter_chunks(8192)

    def get_file_size(self, key: str) -> int:
        """
            Get object size in bytes from S3 metadata.

        从 S3 元数据获取对象大小（字节）。
        """
        resp = self._client.head_object(Bucket=self._bucket, Key=key)
        return resp["ContentLength"]
