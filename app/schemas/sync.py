from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class SyncMode(str, Enum):
    FULL = "full"
    INCREMENTAL = "incremental"


class SyncRequest(BaseModel):
    stock_codes: list[str] | None = None
    date_from: date | None = None
    date_to: date | None = None
    mode: SyncMode = SyncMode.INCREMENTAL


class SyncProgress(BaseModel):
    total: int = 0
    synced: int = 0
    skipped: int = 0
    failed: int = 0


class SyncStatusResponse(BaseModel):
    task_id: str
    status: str  # pending, running, success, failed
    progress: SyncProgress = Field(default_factory=SyncProgress)
    error: str | None = None


class SyncResult(BaseModel):
    total: int = 0
    synced: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = Field(default_factory=list)
