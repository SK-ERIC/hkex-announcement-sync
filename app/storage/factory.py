from app.config import Settings, StorageBackend as StorageBackendEnum
from app.storage.base import StorageBackend
from app.storage.local import LocalStorage
from app.storage.s3 import S3Storage


def create_storage_backend(settings: Settings | None = None) -> StorageBackend:
    settings = settings or Settings()
    if settings.STORAGE_BACKEND == StorageBackendEnum.S3:
        return S3Storage(
            endpoint=settings.S3_ENDPOINT,
            bucket=settings.S3_BUCKET,
            access_key=settings.S3_ACCESS_KEY,
            secret_key=settings.S3_SECRET_KEY,
            region=settings.S3_REGION,
        )
    return LocalStorage(base_path=settings.STORAGE_LOCAL_PATH)
