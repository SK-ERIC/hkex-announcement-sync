import logging
import re
import time
from datetime import date, datetime, timedelta
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import Settings

logger = logging.getLogger(__name__)


class HKEXClient:
    """Client for fetching announcement data from HKEX disclosure platform."""

    def __init__(self, settings: Settings | None = None):
        self._settings = settings or Settings()
        self._session = httpx.Client(
            timeout=self._settings.HTTP_TIMEOUT,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json, text/html, */*",
            },
            follow_redirects=True,
        )

    def close(self):
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    def _get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        resp = self._session.get(url, params=params)
        resp.raise_for_status()
        return resp

    def get_stock_id(self, stock_code: str) -> str:
        """Resolve stock code (e.g. '00700') to HKEX internal stock ID."""
        params = {
            "callback": "callback",
            "lang": "EN",
            "type": "A",
            "name": stock_code,
            "market": "SEHK",
            "_": str(int(time.time() * 1000)),
        }
        resp = self._get(self._settings.HKEX_PREFIX_URL, params=params)
        text = resp.text

        # Strip JSONP wrapper: callback({...})
        match = re.search(r"callback\((.*)\)", text, re.DOTALL)
        if not match:
            raise ValueError(f"Failed to parse stock ID response for {stock_code}")

        import json

        data = json.loads(match.group(1))
        stocks = data.get("stockId", [])
        if not stocks:
            raise ValueError(f"Stock code {stock_code} not found in HKEX")

        stock_id = str(stocks[0]) if isinstance(stocks[0], int) else stocks[0]["stockId"]
        logger.info("Resolved stock_code=%s -> stock_id=%s", stock_code, stock_id)
        return stock_id

    def search_announcements(
        self,
        stock_id: str,
        date_from: date,
        date_to: date,
    ) -> list[dict[str, Any]]:
        """Fetch all announcements for a stock within a date range.

        HKEX API limits queries to ~1 month, so we chunk the range by month.
        """
        all_records: list[dict[str, Any]] = []

        # Chunk by month
        chunk_start = date_from
        while chunk_start < date_to:
            chunk_end = min(
                date(chunk_start.year, chunk_start.month + 1, 1) - timedelta(days=1),
                date_to,
            )
            # Handle year wrap
            if chunk_start.month == 12:
                chunk_end = min(date(chunk_start.year, 12, 31), date_to)

            logger.info(
                "Fetching announcements: stock_id=%s, %s to %s",
                stock_id, chunk_start, chunk_end,
            )
            records = self._fetch_paginated(stock_id, chunk_start, chunk_end)
            all_records.extend(records)

            # Move to next month
            if chunk_start.month == 12:
                chunk_start = date(chunk_start.year + 1, 1, 1)
            else:
                chunk_start = date(chunk_start.year, chunk_start.month + 1, 1)

        logger.info("Total announcements fetched: %d", len(all_records))
        return all_records

    def _fetch_paginated(
        self,
        stock_id: str,
        date_from: date,
        date_to: date,
    ) -> list[dict[str, Any]]:
        """Paginate through HKEX search results."""
        all_records: list[dict[str, Any]] = []
        start_row = 0
        page_size = 5000

        while True:
            params = {
                "sortDir": "0",
                "sortByOptions": "DateTime",
                "category": "0",
                "market": "SEHK",
                "stockId": stock_id,
                "documentType": "-1",
                "fromDate": date_from.strftime("%Y%m%d"),
                "toDate": date_to.strftime("%Y%m%d"),
                "title": "",
                "searchType": "0",
                "t1code": "-2",
                "t2Gcode": "-2",
                "t2code": "-2",
                "rowRange": str(start_row),
                "lang": "EN",
            }

            resp = self._get(self._settings.HKEX_SEARCH_URL, params=params)
            data = resp.json()

            # HKEX returns data in different formats depending on endpoint version
            result = data.get("result", data)
            if isinstance(result, dict):
                records = result.get("stockAnnouncement", result.get("list", []))
                has_next = result.get("hasNextRow", False)
                total = result.get("totalAnnouncement", result.get("total", 0))
            elif isinstance(result, list):
                records = result
                has_next = len(records) >= page_size
                total = len(records)
            else:
                break

            if not records:
                break

            all_records.extend(records)

            if not has_next or len(all_records) >= total:
                break

            start_row += page_size
            time.sleep(0.5)  # Rate limiting between pages

        return all_records

    @staticmethod
    def parse_record(raw: dict[str, Any], stock_code: str) -> dict[str, Any]:
        """Parse a raw HKEX API record into a normalized dict."""
        file_link = raw.get("FILE_LINK", raw.get("fileLink", ""))
        title = raw.get("TITLE", raw.get("title", ""))
        stock_name = raw.get("STOCK_NAME", raw.get("stockName", ""))
        filing_type = raw.get("CATEGORY", raw.get("category", ""))

        # Parse date from various formats HKEX uses
        date_str = raw.get("DATE_TIME", raw.get("dateTime", ""))
        announcement_date = None
        if date_str:
            for fmt in ("%Y/%m/%d %H:%M", "%d/%m/%Y%H:%M", "%Y-%m-%d", "%d/%m/%Y"):
                try:
                    announcement_date = datetime.strptime(date_str.strip(), fmt)
                    break
                except ValueError:
                    continue

        hkex_url = f"https://www1.hkexnews.hk{file_link}" if file_link else ""

        return {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "title": title,
            "announcement_date": announcement_date,
            "filing_type": filing_type,
            "hkex_url": hkex_url,
            "file_link": file_link,
        }
