import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.announcement import (
    AnnouncementDetailResponse,
    AnnouncementListParams,
    AnnouncementListResponse,
    AnnouncementResponse,
)
from app.services import announcement_service
from app.storage.factory import create_storage_backend

router = APIRouter(prefix="/announcements", tags=["announcements"])


@router.get("", response_model=AnnouncementListResponse)
async def list_announcements(
    stock_code: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated announcement list with optional filters."""
    from datetime import date as date_type

    params = AnnouncementListParams(
        stock_code=stock_code,
        date_from=date_type.fromisoformat(date_from) if date_from else None,
        date_to=date_type.fromisoformat(date_to) if date_to else None,
        page=page,
        page_size=page_size,
    )

    items, total = await announcement_service.get_announcements(db, params)

    storage = create_storage_backend()
    responses = []
    for item in items:
        resp = AnnouncementResponse.model_validate(item)
        if item.file_path:
            resp.download_url = f"/api/announcements/{item.id}/download"
        responses.append(resp)

    return AnnouncementListResponse(
        items=responses,
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/{announcement_id}", response_model=AnnouncementDetailResponse)
async def get_announcement(
    announcement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single announcement's full details."""
    announcement = await announcement_service.get_announcement_by_id(db, announcement_id)
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")

    resp = AnnouncementDetailResponse.model_validate(announcement)
    if announcement.file_path:
        resp.download_url = f"/api/announcements/{announcement.id}/download"
    return resp


@router.get("/{announcement_id}/download")
async def download_announcement(
    announcement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Download the PDF file for an announcement."""
    announcement = await announcement_service.get_announcement_by_id(db, announcement_id)
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")
    if not announcement.file_path:
        raise HTTPException(status_code=404, detail="File not available")

    storage = create_storage_backend()

    # For local storage, file_path is absolute; for S3, it's the key
    from app.config import get_settings
    settings = get_settings()

    if settings.STORAGE_BACKEND.value == "s3":
        key = announcement.file_path
    else:
        # Extract relative key from local path
        key = f"{announcement.stock_code}/{announcement.id}.pdf"

    try:
        stream = storage.get_file_stream(key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found on storage")

    filename = f"{announcement.stock_code}_{announcement.announcement_date}_{announcement.id}.pdf"
    return StreamingResponse(
        stream,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
