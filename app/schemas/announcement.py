from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AnnouncementResponse(BaseModel):
    id: UUID
    stock_code: str
    stock_name: str
    title: str
    announcement_date: date | None = None
    filing_type: str | None = None
    hkex_url: str
    file_path: str | None = None
    file_size: int | None = None
    source: str
    is_visible: bool = True
    download_url: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AnnouncementListResponse(BaseModel):
    items: list[AnnouncementResponse]
    total: int
    page: int
    page_size: int


class AnnouncementDetailResponse(AnnouncementResponse):
    file_hash: str | None = None
    last_synced_at: datetime | None = None


class AnnouncementListParams(BaseModel):
    stock_code: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
