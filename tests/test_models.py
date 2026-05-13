"""Tests for ORM models and enums."""
from app.models import AnnouncementStatus


class TestAnnouncementStatus:
    def test_all_status_values(self):
        values = [s.value for s in AnnouncementStatus]
        assert "active" in values
        assert "cancelled_superseded" in values
        assert "cancelled_reissued" in values
        assert "headlines_revised" in values

    def test_enum_count(self):
        assert len(AnnouncementStatus) == 4

    def test_string_comparison(self):
        assert AnnouncementStatus.ACTIVE == "active"
        assert AnnouncementStatus.CANCELLED_SUPERSEDED == "cancelled_superseded"
