from fastapi import APIRouter, HTTPException
from celery.result import AsyncResult

from app.schemas.sync import SyncRequest, SyncStatusResponse, SyncProgress
from app.tasks.sync_tasks import sync_announcements_task

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("", response_model=dict)
async def trigger_sync(request: SyncRequest):
    """Trigger a sync task. Returns task_id for status polling."""
    task = sync_announcements_task.delay(
        stock_codes=request.stock_codes,
        mode=request.mode.value,
        date_from=request.date_from.isoformat() if request.date_from else None,
        date_to=request.date_to.isoformat() if request.date_to else None,
    )
    return {"task_id": task.id}


@router.get("/status/{task_id}", response_model=SyncStatusResponse)
async def get_sync_status(task_id: str):
    """Query the status of a sync task."""
    result = AsyncResult(task_id)

    if result.state == "PENDING":
        return SyncStatusResponse(
            task_id=task_id,
            status="pending",
            progress=SyncProgress(),
        )
    elif result.state == "RUNNING":
        meta = result.info or {}
        progress = meta.get("progress", {})
        return SyncStatusResponse(
            task_id=task_id,
            status="running",
            progress=SyncProgress(**progress),
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
        return SyncStatusResponse(
            task_id=task_id,
            status="failed",
            error=str(result.info),
        )
    else:
        return SyncStatusResponse(
            task_id=task_id,
            status=result.state.lower(),
        )
