"""
API endpoints for triggering and monitoring sync tasks.

触发和监控同步任务的 API 端点。
"""

import asyncio
import logging
import uuid
from typing import Any

from fastapi import APIRouter

from app.config import get_settings
from app.schemas.sync import SyncProgress, SyncRequest, SyncStatusResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sync", tags=["sync"])

# In-memory task store for non-Celery mode
_tasks: dict[str, dict[str, Any]] = {}


async def _run_sync_inline(
    task_id: str,
    stock_codes: list[str] | None,
    mode: str,
) -> None:
    """
    Execute sync directly in-process without Celery or Redis.

    在进程内直接执行同步，无需 Celery 或 Redis。

    Args:
    task_id: Unique task identifier for tracking. / 用于跟踪的唯一任务标识符。
    stock_codes: Optional list of stock codes to sync. / 可选的要同步的股票代码列表。
    mode: Sync mode string (e.g. 'full', 'incremental'). / 同步模式字符串。

    """
    from app.config import Settings
    from app.database import async_session_factory
    from app.services.sync_service import SyncService

    settings = Settings()
    if stock_codes:
        settings = settings.model_copy(update={"SYNC_STOCK_CODES": ",".join(stock_codes)})

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
    """
    Trigger a sync task via Celery or inline execution.

    触发同步任务，通过 Celery 或内联执行。

    Uses Celery when CELERY_ENABLED=true and Redis is available.
    Otherwise runs sync directly in-process as an asyncio background task.

    当 CELERY_ENABLED=true 且 Redis 可用时使用 Celery。
    否则作为 asyncio 后台任务在进程内直接运行同步。

    Args:
    request: Sync request body with stock_codes, mode, and date range.
    包含 stock_codes、mode 和日期范围的同步请求体。

    Returns:
    dict: {"task_id": str} for tracking the sync task status.
    {"task_id": str} 用于跟踪同步任务状态。

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
    """
    Query the current status of a sync task by its task ID.

    通过任务 ID 查询同步任务的当前状态。

    Checks Celery result backend when Celery is enabled,
    otherwise looks up the in-memory task store.

    当 Celery 启用时查询 Celery 结果后端，
    否则查询内存中的任务存储。

    Args:
    task_id: The unique task identifier returned by trigger_sync.
    由 trigger_sync 返回的唯一任务标识符。

    Returns:
    SyncStatusResponse: Current task status with progress details and any errors.
    包含进度详情和错误信息的当前任务状态。

    """
    settings = get_settings()

    if settings.CELERY_ENABLED:
        from celery.result import AsyncResult

        result = AsyncResult(task_id)

        if result.state == "PENDING":
            return SyncStatusResponse(task_id=task_id, status="pending", progress=SyncProgress())
        elif result.state == "RUNNING":
            meta = result.info or {}
            progress = meta.get("progress", {})
            return SyncStatusResponse(task_id=task_id, status="running", progress=SyncProgress(**progress))
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
