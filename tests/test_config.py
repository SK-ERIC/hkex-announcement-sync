"""Tests for application configuration."""
from app.config import Settings


class TestSchedulerConfig:
    def test_scheduler_defaults(self):
        s = Settings()
        assert s.SCHEDULER_ENABLED is False
        assert s.SCHEDULER_INTERVAL_SECONDS == 900
        assert s.SCHEDULER_SMART_BACKOFF is True
        assert s.SCHEDULER_MAX_INTERVAL_SECONDS == 3600


class TestReconcileConfig:
    def test_reconcile_defaults(self):
        s = Settings()
        assert s.RECONCILE_ENABLED is True
        assert s.RECONCILE_DAYS_BACK == 30
