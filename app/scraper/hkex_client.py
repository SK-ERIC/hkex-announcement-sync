import json
import logging
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import Settings

logger = logging.getLogger(__name__)

MOCK_DATA_PATH = Path(__file__).parent.parent.parent / "tests" / "mock_hkex_response.json"
HKEX_BASE_URL = "https://www1.hkexnews.hk"
HKEX_SEARCH_PAGE = "https://www1.hkexnews.hk/search/titlesearch.xhtml"
HKEX_API_ENDPOINT = "https://www1.hkexnews.hk/search/titleSearchServlet.do"


class HKEXClient:
    """Client for fetching announcement data from HKEX disclosure platform.

    HKEX search requires a three-step session-based approach:
    1. GET search page with params to get ViewState and form action URL
    2. POST the JSF form with ViewState + date range to initialize session
    3. GET the JSON API with pagination to fetch records

    Reference: https://github.com/simonplmak-cloud/hkex-filing-scraper
    """

    def __init__(self, settings: Settings | None = None, mock: bool = False):
        self._settings = settings or Settings()
        self._mock = mock
        self._session: httpx.Client | None = None

    def close(self):
        if self._session:
            self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _get_session(self) -> httpx.Client:
        if self._session is None:
            self._session = httpx.Client(
                timeout=self._settings.HTTP_TIMEOUT,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                },
                follow_redirects=True,
            )
        return self._session

    def get_stock_id(self, stock_code: str) -> str:
        """Resolve stock code (e.g. '00700') to HKEX internal stock ID."""
        if self._mock:
            logger.info("Mock mode: returning stock_id=7609 for %s", stock_code)
            return "7609"

        params = {
            "callback": "callback",
            "lang": "EN",
            "type": "A",
            "name": stock_code,
            "market": "SEHK",
            "_": str(int(time.time() * 1000)),
        }
        resp = self._get_session().get(self._settings.HKEX_PREFIX_URL, params=params)
        resp.raise_for_status()

        match = re.search(r"callback\((.*)\)", resp.text, re.DOTALL)
        if not match:
            raise ValueError(f"Failed to parse stock ID response for {stock_code}")

        data = json.loads(match.group(1))
        stocks = data.get("stockInfo", [])
        if not stocks:
            raise ValueError(f"Stock code {stock_code} not found in HKEX")

        stock_id = str(stocks[0]["stockId"])
        logger.info("Resolved stock_code=%s -> stock_id=%s", stock_code, stock_id)
        return stock_id

    def search_announcements(
        self,
        stock_id: str,
        date_from: date,
        date_to: date,
    ) -> list[dict[str, Any]]:
        """Fetch all announcements for a stock within a date range."""
        if self._mock:
            return self._mock_search()

        all_records: list[dict[str, Any]] = []

        chunk_start = date_from
        while chunk_start < date_to:
            if chunk_start.month == 12:
                next_month = date(chunk_start.year + 1, 1, 1)
            else:
                next_month = date(chunk_start.year, chunk_start.month + 1, 1)
            chunk_end = min(next_month - timedelta(days=1), date_to)

            logger.info(
                "Fetching: stock_id=%s, %s to %s",
                stock_id, chunk_start, chunk_end,
            )
            records = self._fetch_chunk(stock_id, chunk_start, chunk_end)
            all_records.extend(records)

            if chunk_start.month == 12:
                chunk_start = date(chunk_start.year + 1, 1, 1)
            else:
                chunk_start = date(chunk_start.year, chunk_start.month + 1, 1)

        logger.info("Total announcements fetched: %d", len(all_records))
        return all_records

    def _mock_search(self) -> list[dict[str, Any]]:
        if not MOCK_DATA_PATH.exists():
            logger.warning("Mock data file not found: %s", MOCK_DATA_PATH)
            return []
        with open(MOCK_DATA_PATH) as f:
            records = json.load(f)
        logger.info("Mock mode: returning %d records", len(records))
        return records

    def _fetch_chunk(
        self,
        stock_id: str,
        date_from: date,
        date_to: date,
    ) -> list[dict[str, Any]]:
        """Fetch one month chunk using the JSF session-based approach."""
        session = self._get_session()
        from_str = date_from.strftime("%Y%m%d")
        to_str = date_to.strftime("%Y%m%d")

        # Step 1: GET search page to extract ViewState and form action
        page_resp = session.get(
            HKEX_SEARCH_PAGE,
            params={
                "sortDir": "0",
                "sortByRecordDate": "on",
                "searchType": "0",
                "category": "0",
                "t1code": "-2",
                "t2Gcode": "-2",
                "t2code": "-2",
                "documentType": "-1",
                "rowRange": "0",
                "lang": "EN",
            },
            timeout=30,
        )
        page_resp.raise_for_status()

        html = page_resp.text
        vs_match = re.search(r'javax\.faces\.ViewState.*?value="([^"]+)"', html)
        view_state = vs_match.group(1) if vs_match else ""
        fa_match = re.search(r'<form[^>]*action="([^"]+)"', html)
        form_action = fa_match.group(1) if fa_match else ""

        submit_url = (
            f"{HKEX_BASE_URL}{form_action}"
            if form_action.startswith("/")
            else form_action
        )

        # Step 2: POST JSF form to set date range on server session
        if submit_url and view_state:
            session.post(
                submit_url,
                data={
                    "j_idt10": "j_idt10",
                    "j_idt10:loadMoreRange": "100",
                    "javax.faces.ViewState": view_state,
                    "from": from_str,
                    "to": to_str,
                },
                timeout=30,
            )

        # Step 3: GET JSON API with pagination
        all_records: list[dict[str, Any]] = []
        fetched = 0

        while True:
            api_resp = session.get(
                HKEX_API_ENDPOINT,
                params={
                    "sortDir": "0",
                    "sortByOptions": "DateTime",
                    "category": "0",
                    "market": "SEHK",
                    "stockId": stock_id,
                    "documentType": "-1",
                    "fromDate": from_str,
                    "toDate": to_str,
                    "title": "",
                    "searchType": "0",
                    "t1code": "-2",
                    "t2Gcode": "-2",
                    "t2code": "-2",
                    "rowRange": str(fetched + 5000),
                    "lang": "E",
                },
                headers={
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Referer": HKEX_SEARCH_PAGE,
                    "X-Requested-With": "XMLHttpRequest",
                },
                timeout=120,
            )
            api_resp.raise_for_status()

            data = api_resp.json()
            result_raw = data.get("result", "null")
            if not result_raw or result_raw == "null":
                break

            if isinstance(result_raw, str):
                records = json.loads(result_raw)
            else:
                records = result_raw

            if not records:
                break

            has_next = data.get("hasNextRow", False)
            new_records = records[fetched:] if fetched < len(records) else []
            all_records.extend(new_records)
            fetched = len(records)

            if not has_next:
                break

            time.sleep(0.5)

        return all_records

    @staticmethod
    def parse_record(raw: dict[str, Any], stock_code: str) -> dict[str, Any]:
        """Parse a raw HKEX API record into a normalized dict."""
        file_link = raw.get("FILE_LINK", "")
        title = raw.get("TITLE", "")
        stock_name = raw.get("STOCK_NAME", "").replace("<br/>", " ").strip()
        filing_type = raw.get("LONG_TEXT", raw.get("SHORT_TEXT", ""))
        news_id = raw.get("NEWS_ID", "")

        date_str = raw.get("DATE_TIME", "")
        announcement_date = None
        if date_str:
            for fmt in ("%d/%m/%Y %H:%M", "%Y/%m/%d %H:%M", "%Y-%m-%d"):
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
            "news_id": news_id,
        }
