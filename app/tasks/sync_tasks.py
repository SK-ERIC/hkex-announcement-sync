import asyncio
import logging
from typing import Any

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.sync_tasks.sync_announcements_task",
    bind=True,
    max_retries=1,
)
def sync_announcements_task(
    self,
    stock_codes: list[str] | None = None,
    mode: str = "incremental",
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    """Celery task to sync announcements from HKEX."""
    from app.config import Settings
    from app.database import async_session_factory
    from app.services.sync_service import SyncService

    settings = Settings()
    if stock_codes:
        settings = settings.model_copy(update={"SYNC_STOCK_CODES": stock_codes})

    self.update_state(state="RUNNING", meta={"progress": {"total": 0, "synced": 0, "skipped": 0, "failed": 0}})

    async def _run():
        async with async_session_factory() as db:
            task_state = {}
            service = SyncService(db, settings)
            result = service.run(task_state)
            return result

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(_run())
    finally:
        loop.close()

    logger.info("Sync task completed: %s", result)
    return result


@celery_app.task(name="app.tasks.sync_tasks.scheduled_incremental_sync")
def scheduled_incremental_sync() -> dict[str, Any]:
    """Beat-scheduled incremental sync for all configured stock codes."""
    logger.info("Starting scheduled incremental sync")
    return sync_announcements_task.delay(mode="incremental").id
