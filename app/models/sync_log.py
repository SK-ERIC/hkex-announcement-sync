"""
ORM model for tracking sync operation history.

同步操作历史记录的 ORM 模型。
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.announcement import Base


class SyncStatus(str, PyEnum):
    """
    Status of a sync operation.

    同步操作的状态枚举。

    Attributes:
    PENDING: Sync has been triggered but not started. / 同步已触发但未开始。
    RUNNING: Sync is currently in progress. / 同步正在执行中。
    SUCCESS: Sync completed successfully. / 同步成功完成。
    FAILED: Sync failed with errors. / 同步失败。

    """

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class SyncLog(Base):
    """
    ORM model representing a sync operation log entry.

    同步操作日志记录的 ORM 模型。

    Attributes:
    id: Unique UUID primary key. / 唯一 UUID 主键。
    stock_codes: Comma-separated stock codes that were synced. / 同步的股票代码（逗号分隔）。
    mode: Sync mode (full or incremental). / 同步模式（全量或增量）。
    status: Current status of the sync. / 同步的当前状态。
    total: Total number of records processed. / 处理的总记录数。
    synced: Number of new records synced. / 新同步的记录数。
    skipped: Number of records skipped (already existed). / 跳过的记录数。
    failed: Number of records that failed. / 失败的记录数。
    error: Error message if failed. / 失败时的错误信息。
    started_at: When the sync started. / 同步开始时间。
    finished_at: When the sync finished. / 同步完成时间。
    duration_seconds: How long the sync took. / 同步耗时（秒）。
    created_at: Record creation timestamp. / 记录创建时间戳。

    """

    __tablename__ = "sync_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    stock_codes: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="incremental")
    status: Mapped[SyncStatus] = mapped_column(Enum(SyncStatus), nullable=False, default=SyncStatus.PENDING)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    synced: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
