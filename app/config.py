from enum import Enum
from functools import lru_cache

from pydantic import computed_field
from pydantic_settings import BaseSettings


class StorageBackend(str, Enum):
    """Supported file storage backend types.

    支持的文件存储后端类型枚举。

    Attributes:
        LOCAL: Local filesystem storage. / 本地文件系统存储。
        S3: S3-compatible object storage. / S3 兼容的对象存储。
    """

    LOCAL = "local"
    S3 = "s3"


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file.

    从环境变量和 .env 文件加载的应用配置类。

    Manages configuration for database, Celery task queue, file storage,
    HKEX API endpoints, HTTP client behavior, and API defaults.

    管理数据库、Celery 任务队列、文件存储、港交所 API 端点、
    HTTP 客户端行为和 API 默认值的配置。

    Attributes:
        DATABASE_URL: SQLAlchemy async database connection string. / 数据库连接字符串。
        CELERY_ENABLED: Whether to use Celery for async task processing. / 是否启用 Celery。
        REDIS_URL: Redis connection URL. / Redis 连接 URL。
        CELERY_BROKER_URL: Celery broker URL. / Celery 代理 URL。
        CELERY_RESULT_BACKEND: Celery result backend URL. / Celery 结果后端 URL。
        STORAGE_BACKEND: Storage backend type (local/s3). / 存储后端类型。
        STORAGE_LOCAL_PATH: Local storage directory path. / 本地存储目录路径。
        S3_ENDPOINT: S3 endpoint URL. / S3 端点 URL。
        S3_BUCKET: S3 bucket name. / S3 桶名称。
        S3_ACCESS_KEY: S3 access key. / S3 访问密钥。
        S3_SECRET_KEY: S3 secret key. / S3 密钥。
        S3_REGION: S3 region. / S3 区域。
        SYNC_STOCK_CODES: Comma-separated stock codes to sync. / 逗号分隔的同步股票代码。
        SYNC_CONCURRENCY: Number of concurrent sync workers. / 并发同步工作线程数。
        SYNC_CRON_SCHEDULE: Cron expression for scheduled sync. / 定时同步的 Cron 表达式。
        HKEX_BASE_URL: HKEX base URL. / 港交所基础 URL。
        HKEX_SEARCH_URL: HKEX search API URL. / 港交所搜索 API URL。
        HKEX_PREFIX_URL: HKEX prefix lookup URL. / 港交所前缀查询 URL。
        HKEX_FULL_HISTORY_START: Start date for full history sync. / 全量历史同步的起始日期。
        HTTP_TIMEOUT: HTTP request timeout in seconds. / HTTP 请求超时时间（秒）。
        HTTP_MAX_RETRIES: Maximum HTTP retry attempts. / HTTP 最大重试次数。
        HTTP_RETRY_BACKOFF: Retry backoff factor in seconds. / 重试退避因子（秒）。
        API_PREFIX: API route prefix. / API 路由前缀。
        PAGE_SIZE_DEFAULT: Default pagination page size. / 默认分页大小。
        PAGE_SIZE_MAX: Maximum pagination page size. / 最大分页大小。
        DEFAULT_LANGUAGE: Default response language. / 默认响应语言。
    """

    # Database — SQLite for local dev, MySQL/PostgreSQL for production
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/hkex_sync.db"

    # Celery — set CELERY_ENABLED=true when Redis is available
    CELERY_ENABLED: bool = False
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

    # Sync — use comma-separated string in env: SYNC_STOCK_CODES=00700,09988
    SYNC_STOCK_CODES: str = "00700"
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
    DEFAULT_LANGUAGE: str = "en"

    @computed_field
    @property
    def stock_codes(self) -> list[str]:
        return [code.strip() for code in self.SYNC_STOCK_CODES.split(",") if code.strip()]

    @property
    def is_sqlite(self) -> bool:
        return "sqlite" in self.DATABASE_URL

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    """Get a cached singleton Settings instance.

    获取缓存的 Settings 单例实例。

    Returns:
        Settings: The application settings object. / 应用配置对象。
    """
    return Settings()
