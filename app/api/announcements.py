"""
API endpoints for querying and downloading HKEX announcements.

港交所公告查询和下载的 API 端点。
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Announcement
from app.schemas.announcement import (
    AnnouncementDetailResponse,
    AnnouncementListParams,
    AnnouncementListResponse,
    AnnouncementResponse,
    LanguageEnum,
)
from app.services import announcement_service
from app.storage.factory import create_storage_backend

router = APIRouter(prefix="/announcements", tags=["announcements"])


def _get_lang_fields(ann: Announcement, language: LanguageEnum) -> dict:
    """
    Extract the language-appropriate fields from an Announcement model instance.

    从 Announcement 模型实例中提取指定语言对应的字段。

    Args:
    ann: The Announcement ORM model instance. / Announcement ORM 模型实例。
    language: The requested language enum value. / 请求的语言枚举值。

    Returns:
    dict: Dictionary with keys: title, stock_name, filing_type,
    short_text, long_text, hkex_url.
    包含 title、stock_name、filing_type、short_text、
    long_text、hkex_url 键的字典。

    """
    lang_map = {
        LanguageEnum.en: "en",
        LanguageEnum.zh: "zh",
        LanguageEnum.cn: "cn",
    }
    suffix = lang_map[language]

    title = getattr(ann, f"title_{suffix}", "") or ""
    stock_name = getattr(ann, f"stock_name_{suffix}", "") or ""
    filing_type = getattr(ann, f"filing_type_{suffix}", "") or None
    short_text = getattr(ann, f"short_text_{suffix}", "") or None
    long_text = getattr(ann, f"long_text_{suffix}", "") or None

    if suffix in ("zh", "cn"):
        hkex_url = ann.hkex_url_zh or ann.hkex_url_en or ""
    else:
        hkex_url = ann.hkex_url_en or ""

    return {
        "title": title,
        "stock_name": stock_name,
        "filing_type": filing_type,
        "short_text": short_text,
        "long_text": long_text,
        "hkex_url": hkex_url,
    }


@router.get("", response_model=AnnouncementListResponse)
async def list_announcements(
    stock_code: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    language: LanguageEnum = Query(LanguageEnum.en),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a paginated announcement list with optional filters and language support.

    获取带分页的公告列表，支持可选过滤和多语言。

    Args:
    stock_code: Filter by stock code. / 按股票代码过滤。
    date_from: Filter start date (ISO format). / 过滤起始日期（ISO 格式）。
    date_to: Filter end date (ISO format). / 过滤结束日期（ISO 格式）。
    page: Page number (1-based). / 页码（从 1 开始）。
    page_size: Items per page (max 100). / 每页条数（最大 100）。
    language: Response language (en/zh/cn). / 响应语言。
    db: Async database session (injected). / 异步数据库会话（自动注入）。

    Returns:
    AnnouncementListResponse: Paginated announcement results.
    分页的公告查询结果。

    """
    from datetime import date as date_type

    params = AnnouncementListParams(
        stock_code=stock_code,
        date_from=date_type.fromisoformat(date_from) if date_from else None,
        date_to=date_type.fromisoformat(date_to) if date_to else None,
        status=status,
        page=page,
        page_size=page_size,
        language=language,
    )

    items, total = await announcement_service.get_announcements(db, params)

    responses = []
    for item in items:
        lang_fields = _get_lang_fields(item, language)
        responses.append(
            AnnouncementResponse(
                id=item.id,
                stock_code=item.stock_code,
                news_id=item.news_id,
                title=lang_fields["title"],
                stock_name=lang_fields["stock_name"],
                filing_type=lang_fields["filing_type"],
                short_text=lang_fields["short_text"],
                long_text=lang_fields["long_text"],
                hkex_url=lang_fields["hkex_url"],
                file_type=item.file_type,
                file_size=item.file_size,
                announcement_date=item.announcement_date,
                source=item.source.value,
                is_visible=item.is_visible,
                status=item.status,
                download_url=f"/api/announcements/{item.id}/download",
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
        )

    return AnnouncementListResponse(
        items=responses,
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/{announcement_id}", response_model=AnnouncementDetailResponse)
async def get_announcement(
    announcement_id: uuid.UUID,
    language: LanguageEnum = Query(LanguageEnum.en),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a single announcement's full details in the specified language.

    获取指定语言的单条公告完整详情。

    Args:
    announcement_id: UUID of the announcement. / 公告的 UUID。
    language: Response language (en/zh/cn). / 响应语言。
    db: Async database session (injected). / 异步数据库会话（自动注入）。

    Returns:
    AnnouncementDetailResponse: Detailed announcement data with file metadata.
    包含文件元数据的公告详细数据。

    Raises:
    HTTPException: 404 if announcement not found. / 公告未找到时返回 404。

    """
    announcement = await announcement_service.get_announcement_by_id(db, announcement_id)
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")

    lang_fields = _get_lang_fields(announcement, language)
    return AnnouncementDetailResponse(
        id=announcement.id,
        stock_code=announcement.stock_code,
        news_id=announcement.news_id,
        title=lang_fields["title"],
        stock_name=lang_fields["stock_name"],
        filing_type=lang_fields["filing_type"],
        short_text=lang_fields["short_text"],
        long_text=lang_fields["long_text"],
        hkex_url=lang_fields["hkex_url"],
        file_type=announcement.file_type,
        file_size=announcement.file_size,
        announcement_date=announcement.announcement_date,
        source=announcement.source.value,
        is_visible=announcement.is_visible,
        status=announcement.status,
        download_url=f"/api/announcements/{announcement.id}/download",
        file_hash=announcement.file_hash,
        last_synced_at=announcement.last_synced_at,
        created_at=announcement.created_at,
        updated_at=announcement.updated_at,
    )


@router.get("/{announcement_id}/download")
async def download_announcement(
    announcement_id: uuid.UUID,
    language: LanguageEnum = Query(LanguageEnum.en),
    db: AsyncSession = Depends(get_db),
):
    """
    Download the PDF file for an announcement in the specified language.

    下载指定语言的公告 PDF 文件。

    Args:
    announcement_id: UUID of the announcement. / 公告的 UUID。
    language: Preferred file language (en/zh/cn). / 首选文件语言。
    db: Async database session (injected). / 异步数据库会话（自动注入）。

    Returns:
    StreamingResponse: PDF file stream with download headers.
    带有下载头的 PDF 文件流。

    Raises:
    HTTPException: 404 if announcement or file not found. / 公告或文件未找到时返回 404。

    """
    announcement = await announcement_service.get_announcement_by_id(db, announcement_id)
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")

    if language in (LanguageEnum.zh, LanguageEnum.cn):
        file_path = announcement.file_path_zh or announcement.file_path_en
    else:
        file_path = announcement.file_path_en or announcement.file_path_zh

    if not file_path:
        raise HTTPException(status_code=404, detail="File not available")

    storage = create_storage_backend()
    from app.config import get_settings

    settings = get_settings()

    if settings.STORAGE_BACKEND.value == "s3":
        key = file_path
    else:
        lang_suffix = "zh" if language in (LanguageEnum.zh, LanguageEnum.cn) else "en"
        key = f"{announcement.stock_code}/{announcement.id}_{lang_suffix}.pdf"

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
