"""
Pydantic schemas for sync task request/response models.

同步任务请求/响应模型的 Pydantic 模式。
"""

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class SyncMode(str, Enum):
    """
    Sync mode selector (full or incremental).

    同步模式选择器（全量或增量）。
    """

    FULL = "full"
    INCREMENTAL = "incremental"


class SyncRequest(BaseModel):
    """
    Request body for triggering a sync task.

    触发同步任务的请求体。
    """

    stock_codes: list[str] | None = None
    date_from: date | None = None
    date_to: date | None = None
    mode: SyncMode = SyncMode.INCREMENTAL


class SyncProgress(BaseModel):
    """
    Progress counters for a running sync task.

    正在运行的同步任务的进度计数器。
    """

    total: int = 0
    synced: int = 0
    skipped: int = 0
    failed: int = 0


class SyncStatusResponse(BaseModel):
    """
    Response schema for querying sync task status.

    查询同步任务状态的响应模式。
    """

    task_id: str
    status: str  # pending, running, success, failed
    progress: SyncProgress = Field(default_factory=SyncProgress)
    error: str | None = None


class SyncResult(BaseModel):
    """
    Final result summary of a completed sync task.

    已完成同步任务的最终结果摘要。
    """

    total: int = 0
    synced: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = Field(default_factory=list)
