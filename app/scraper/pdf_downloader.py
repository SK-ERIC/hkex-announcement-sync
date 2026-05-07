import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import Settings
from app.storage.base import StorageBackend

logger = logging.getLogger(__name__)


@dataclass
class DownloadResult:
    key: str
    file_path: str | None = None
    file_size: int = 0
    file_hash: str | None = None
    success: bool = False
    error: str | None = None


class PDFDownloader:
    """Concurrent PDF downloader with retry support."""

    def __init__(self, storage: StorageBackend, settings: Settings | None = None):
        self._storage = storage
        self._settings = settings or Settings()
        self._http = httpx.Client(
            timeout=self._settings.HTTP_TIMEOUT,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            },
            follow_redirects=True,
        )

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
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
        """Download a single PDF and store it."""
        try:
            data = self._download_bytes(url)
            file_hash = hashlib.md5(data).hexdigest()
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
        """Download multiple PDFs concurrently.

        Args:
            tasks: List of (url, storage_key) tuples.
        """
        results: list[DownloadResult] = []
        concurrency = self._settings.SYNC_CONCURRENCY

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {
                executor.submit(self.download_single, url, key): key
                for url, key in tasks
            }
            for future in as_completed(futures):
                results.append(future.result())

        success = sum(1 for r in results if r.success)
        failed = len(results) - success
        logger.info("Batch download complete: %d success, %d failed", success, failed)
        return results
