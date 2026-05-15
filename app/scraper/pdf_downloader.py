"""
Concurrent PDF downloader with retry support.

支持重试的并发 PDF 下载器。
"""

import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import Settings
from app.storage.base import StorageBackend

logger = logging.getLogger(__name__)


@dataclass
class DownloadResult:
    """
    Result of a single PDF download attempt.

    单次 PDF 下载尝试的结果。
    """

    key: str
    file_path: str | None = None
    file_size: int = 0
    file_hash: str | None = None
    success: bool = False
    error: str | None = None


class PDFDownloader:
    """
    Concurrent PDF downloader with retry support.
    """

    def __init__(self, storage: StorageBackend, settings: Settings | None = None):
        """
        Initialize the downloader with a storage backend and optional settings.

        使用存储后端和可选配置初始化下载器。
        """
        self._storage = storage
        self._settings = settings or Settings()
        from app.scraper.http import create_client

        self._http = create_client(self._settings)

    def close(self):
        """
        Close the HTTP client and release resources.

        关闭 HTTP 客户端并释放资源。
        """
        self._http.close()

    def __enter__(self):
        """
        Enter context manager, returning self.

        进入上下文管理器，返回自身。
        """
        return self

    def __exit__(self, *args):
        """
        Exit context manager, closing the HTTP client.

        退出上下文管理器，关闭 HTTP 客户端。
        """
        self.close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    def _download_bytes(self, url: str) -> bytes:
        resp = self._http.get(url)
        resp.raise_for_status()
        return resp.content

    def download_single(self, url: str, storage_key: str) -> DownloadResult:
        """
        Download a single PDF and store it.
        """
        try:
            data = self._download_bytes(url)
            file_hash = hashlib.sha256(data).hexdigest()
            file_path = self._storage.save(storage_key, data)
            return DownloadResult(
                key=storage_key,
                file_path=file_path,
                file_size=len(data),
                file_hash=file_hash,
                success=True,
            )
        except Exception as e:
            logger.error("Failed to download %s: %s", url, e)
            return DownloadResult(key=storage_key, error=str(e))

    def download_batch(
        self,
        tasks: list[tuple[str, str]],
    ) -> list[DownloadResult]:
        """
        Download multiple PDFs concurrently.

        Args:
        tasks: List of (url, storage_key) tuples.

        """
        results: list[DownloadResult] = []
        concurrency = self._settings.SYNC_CONCURRENCY

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {executor.submit(self.download_single, url, key): key for url, key in tasks}
            for future in as_completed(futures):
                results.append(future.result())

        success = sum(1 for r in results if r.success)
        failed = len(results) - success
        logger.info("Batch download complete: %d success, %d failed", success, failed)
        return results
