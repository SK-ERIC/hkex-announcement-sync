from enum import Enum
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings


class StorageBackend(str, Enum):
    LOCAL = "local"
    S3 = "s3"


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "mysql+asyncmy://root:root@localhost:3306/hkex_sync"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Storage
    STORAGE_BACKEND: StorageBackend = StorageBackend.LOCAL
    STORAGE_LOCAL_PATH: str = "./data/pdfs"
    S3_ENDPOINT: str = ""
    S3_BUCKET: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_REGION: str = ""

    # Sync
    SYNC_STOCK_CODES: list[str] = ["00700"]
    SYNC_CONCURRENCY: int = 5
    SYNC_CRON_SCHEDULE: str = "0 * * * *"

    # HKEX API
    HKEX_BASE_URL: str = "https://www1.hkexnews.hk"
    HKEX_SEARCH_URL: str = "https://www1.hkexnews.hk/search/titleSearchServlet.do"
    HKEX_PREFIX_URL: str = "https://www1.hkexnews.hk/search/prefix.do"
    HKEX_FULL_HISTORY_START: str = "2000-01-01"

    # HTTP
    HTTP_TIMEOUT: int = 60
    HTTP_MAX_RETRIES: int = 3
    HTTP_RETRY_BACKOFF: float = 1.0

    # API
    API_PREFIX: str = "/api"
    PAGE_SIZE_DEFAULT: int = 20
    PAGE_SIZE_MAX: int = 100

    @field_validator("SYNC_STOCK_CODES", mode="before")
    @classmethod
    def parse_stock_codes(cls, v):
        if isinstance(v, str):
            return [code.strip() for code in v.split(",") if code.strip()]
        return v

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
