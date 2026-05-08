import logging
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.scraper.hkex_client import HKEXClient
from app.scraper.pdf_downloader import DownloadResult, PDFDownloader
from app.services import announcement_service
from app.storage.factory import create_storage_backend

logger = logging.getLogger(__name__)


class SyncService:
    """Orchestrates the full sync pipeline: scrape metadata -> dedup -> store -> download PDFs."""

    def __init__(self, db: AsyncSession, settings: Settings | None = None):
        self._db = db
        self._settings = settings or Settings()
        self._storage = create_storage_backend(self._settings)

    def run(self, task_state: dict | None = None) -> dict[str, Any]:
        """Run sync. task_state is used to report progress to Celery."""
        stock_codes = self._settings.stock_codes
        total_synced = 0
        total_skipped = 0
        total_failed = 0
        errors: list[str] = []

        with HKEXClient(self._settings, mock=self._settings.HKEX_MOCK) as client, PDFDownloader(self._storage, self._settings) as downloader:
            for stock_code in stock_codes:
                try:
                    s, k, f, e = self._sync_stock(client, downloader, stock_code, task_state)
                    total_synced += s
                    total_skipped += k
                    total_failed += f
                    errors.extend(e)
                except Exception as exc:
                    msg = f"Failed to sync {stock_code}: {exc}"
                    logger.exception(msg)
                    errors.append(msg)
                    total_failed += 1

        return {
            "total": total_synced + total_skipped + total_failed,
            "synced": total_synced,
            "skipped": total_skipped,
            "failed": total_failed,
            "errors": errors,
        }

    def _sync_stock(
        self,
        client: HKEXClient,
        downloader: PDFDownloader,
        stock_code: str,
        task_state: dict | None,
    ) -> tuple[int, int, int, list[str]]:
        """Sync a single stock code. Returns (synced, skipped, failed, errors)."""
        import asyncio

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                self._sync_stock_async(client, downloader, stock_code, task_state)
            )
        finally:
            loop.close()

    async def _sync_stock_async(
        self,
        client: HKEXClient,
        downloader: PDFDownloader,
        stock_code: str,
        task_state: dict | None,
    ) -> tuple[int, int, int, list[str]]:
        # 1. Resolve stock ID
        stock_id = client.get_stock_id(stock_code)

        # 2. Determine date range
        last_sync = await announcement_service.get_last_sync_date(self._db, stock_code)
        if last_sync:
            date_from = last_sync
        else:
            # First run: start from 3 months ago to limit initial sync scope
            date_from = date.today() - timedelta(days=90)
        date_to = date.today()

        # 3. Fetch metadata from HKEX
        raw_records = client.search_announcements(stock_id, date_from, date_to)
        logger.info("Fetched %d raw records for %s", len(raw_records), stock_code)

        # 4. Parse and dedup
        parsed = [HKEXClient.parse_record(r, stock_code) for r in raw_records]
        existing_urls = await announcement_service.get_existing_urls(
            self._db, stock_code, [p["hkex_url"] for p in parsed if p["hkex_url"]]
        )

        new_records = [p for p in parsed if p["hkex_url"] not in existing_urls]
        logger.info("New records after dedup: %d", len(new_records))

        if not new_records:
            return 0, len(parsed), 0, []

        # 5. Insert metadata to DB
        db_records = []
        for r in new_records:
            db_records.append({
                "stock_code": r["stock_code"],
                "stock_name": r["stock_name"],
                "title": r["title"],
                "announcement_date": r["announcement_date"],
                "filing_type": r["filing_type"],
                "hkex_url": r["hkex_url"],
                "source": "auto",
                "last_synced_at": datetime.utcnow(),
            })

        await announcement_service.bulk_insert_announcements(self._db, db_records)
        await self._db.commit()

        # Re-fetch inserted records to get their IDs for PDF download
        inserted_urls = [r["hkex_url"] for r in db_records]
        from sqlalchemy import select
        from app.models import Announcement

        result = await self._db.execute(
            select(Announcement).where(Announcement.hkex_url.in_(inserted_urls))
        )
        inserted_announcements = list(result.scalars().all())

        # 6. Download PDFs concurrently
        download_tasks = []
        ann_map = {}
        for ann in inserted_announcements:
            if ann.hkex_url:
                key = f"{ann.stock_code}/{ann.id}.pdf"
                download_tasks.append((ann.hkex_url, key))
                ann_map[key] = ann

        if download_tasks:
            download_results = downloader.download_batch(download_tasks)

            # 7. Update DB with file info
            for dr in download_results:
                if dr.success and dr.key in ann_map:
                    ann = ann_map[dr.key]
                    ann.file_path = dr.file_path
                    ann.file_size = dr.file_size
                    ann.file_hash = dr.file_hash
                    ann.last_synced_at = datetime.utcnow()

            await self._db.commit()

        # Update task state for progress tracking
        synced = len(new_records)
        skipped = len(parsed) - len(new_records)
        failed_dl = sum(1 for r in download_results if not r.success) if download_tasks else 0

        if task_state is not None:
            task_state["progress"] = {
                "total": len(parsed),
                "synced": synced,
                "skipped": skipped,
                "failed": failed_dl,
            }

        return synced, skipped, failed_dl, []
