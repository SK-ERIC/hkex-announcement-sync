"""Tests for HKEX client cancellation tag detection."""
import pytest
from app.scraper.hkex_client import HKEXClient, CANCELLATION_PATTERNS


class TestCancellationTagDetection:
    def test_active_when_no_tag(self):
        status, clean = HKEXClient._parse_cancellation_tag("Monthly Returns")
        assert status == "active"
        assert clean == "Monthly Returns"

    def test_active_when_empty(self):
        status, clean = HKEXClient._parse_cancellation_tag("")
        assert status == "active"
        assert clean == ""

    def test_cancelled_superseded(self):
        text = "(Cancelled since Headlines Superseded and Replaced) Announcements and Notices - [Final Results]"
        status, clean = HKEXClient._parse_cancellation_tag(text)
        assert status == "cancelled_superseded"
        assert "Cancelled" not in clean
        assert "Final Results" in clean

    def test_cancelled_reissued(self):
        text = "(Cancelled and Reissued) Monthly Returns"
        status, clean = HKEXClient._parse_cancellation_tag(text)
        assert status == "cancelled_reissued"
        assert clean == "Monthly Returns"

    def test_headlines_revised(self):
        text = "(Headlines Revised) Announcements and Notices - [Final Results / Modified Report by Auditors]"
        status, clean = HKEXClient._parse_cancellation_tag(text)
        assert status == "headlines_revised"
        assert "Revised" not in clean
        assert "Final Results" in clean

    def test_three_patterns_defined(self):
        assert len(CANCELLATION_PATTERNS) == 3

    def test_parse_single_record_with_cancelled_tag(self):
        raw = {
            "NEWS_ID": "202406280007",
            "TITLE": "MONTHLY RETURN",
            "STOCK_NAME": "CHINA OCEAN GP",
            "LONG_TEXT": "(Cancelled and Reissued) Monthly Returns",
            "SHORT_TEXT": "",
            "FILE_LINK": "/listedco/listconews/sehk/2024/0628/202406280007.pdf",
            "FILE_TYPE": "PDF",
            "DATE_TIME": "28/06/2024 22:50",
        }
        result = HKEXClient._parse_single_record(raw, "08047")
        assert result["status"] == "cancelled_reissued"
        assert result["filing_type"] == "Monthly Returns"
        assert result["news_id"] == "202406280007"

    def test_parse_single_record_active(self):
        raw = {
            "NEWS_ID": "202404070007",
            "TITLE": "MONTHLY RETURN",
            "STOCK_NAME": "CHINA OCEAN GP",
            "LONG_TEXT": "Monthly Returns",
            "SHORT_TEXT": "",
            "FILE_LINK": "/listedco/listconews/sehk/2024/0407/202404070007.pdf",
            "FILE_TYPE": "PDF",
            "DATE_TIME": "07/04/2024 20:55",
        }
        result = HKEXClient._parse_single_record(raw, "08047")
        assert result["status"] == "active"
        assert result["filing_type"] == "Monthly Returns"

    def test_parse_single_record_empty_raw(self):
        result = HKEXClient._parse_single_record({}, "08047")
        assert result["status"] == "active"
        assert result["news_id"] == ""

    def test_clean_text_strips_html(self):
        assert HKEXClient._clean_text("<b>Hello</b> &amp; World") == "Hello & World"
