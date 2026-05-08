import asyncio
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.schemas.sync import SyncMode, SyncRequest, SyncProgress, SyncStatusResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sync", tags=["sync"])

# In-memory task store for non-Celery mode
_tasks: dict[str, dict[str, Any]] = {}


async def _run_sync_inline(
    task_id: str,
    stock_codes: list[str] | None,
    mode: str,
) -> None:
    """Execute sync directly in-process (no Celery/Redis required)."""
    from app.config import Settings
    from app.database import async_session_factory
    from app.services.sync_service import SyncService

    settings = Settings()
    if stock_codes:
        settings = settings.model_copy(update={"SYNC_STOCK_CODES": ",".join(stock_codes) if stock_codes else settings.SYNC_STOCK_CODES})

    _tasks[task_id]["status"] = "running"

    async with async_session_factory() as db:
        service = SyncService(db, settings)
        # SyncService.run is sync, run it in a thread to not block the event loop
        result = await asyncio.to_thread(service.run)

    _tasks[task_id]["status"] = "success" if not result.get("errors") else "failed"
    _tasks[task_id]["progress"] = SyncProgress(
        total=result.get("total", 0),
        synced=result.get("synced", 0),
        skipped=result.get("skipped", 0),
        failed=result.get("failed", 0),
    )
    if result.get("errors"):
        _tasks[task_id]["error"] = "; ".join(result["errors"][:3])

    logger.info("Inline sync task %s completed: %s", task_id, result)


@router.post("", response_model=dict)
async def trigger_sync(request: SyncRequest):
    """Trigger a sync task.

    Uses Celery when CELERY_ENABLED=true and Redis is available.
    Otherwise runs sync directly in-process.
    """
    settings = get_settings()

    if settings.CELERY_ENABLED:
        from app.tasks.sync_tasks import sync_announcements_task

        task = sync_announcements_task.delay(
            stock_codes=request.stock_codes,
            mode=request.mode.value,
            date_from=request.date_from.isoformat() if request.date_from else None,
            date_to=request.date_to.isoformat() if request.date_to else None,
        )
        return {"task_id": task.id}

    # Inline mode — no Celery/Redis needed
    task_id = str(uuid.uuid4())
    _tasks[task_id] = {
        "status": "pending",
        "progress": SyncProgress(),
        "error": None,
    }

    asyncio.create_task(
        _run_sync_inline(
            task_id,
            request.stock_codes,
            request.mode.value,
        )
    )

    return {"task_id": task_id}


@router.get("/status/{task_id}", response_model=SyncStatusResponse)
async def get_sync_status(task_id: str):
    """Query the status of a sync task."""
    settings = get_settings()

    if settings.CELERY_ENABLED:
        from celery.result import AsyncResult

        result = AsyncResult(task_id)

        if result.state == "PENDING":
            return SyncStatusResponse(task_id=task_id, status="pending", progress=SyncProgress())
        elif result.state == "RUNNING":
            meta = result.info or {}
            progress = meta.get("progress", {})
            return SyncStatusResponse(
                task_id=task_id, status="running", progress=SyncProgress(**progress)
            )
        elif result.state == "SUCCESS":
            info = result.result or {}
            return SyncStatusResponse(
                task_id=task_id,
                status="success",
                progress=SyncProgress(
                    total=info.get("total", 0),
                    synced=info.get("synced", 0),
                    skipped=info.get("skipped", 0),
                    failed=info.get("failed", 0),
                ),
            )
        elif result.state == "FAILURE":
            return SyncStatusResponse(task_id=task_id, status="failed", error=str(result.info))
        else:
            return SyncStatusResponse(task_id=task_id, status=result.state.lower())

    # Inline mode — look up in-memory store
    task = _tasks.get(task_id)
    if not task:
        return SyncStatusResponse(task_id=task_id, status="not_found", error="Task not found")

    return SyncStatusResponse(
        task_id=task_id,
        status=task["status"],
        progress=task["progress"],
        error=task.get("error"),
    )
