import uuid
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Announcement, SourceType
from app.schemas.announcement import AnnouncementListParams


async def get_announcements(
    db: AsyncSession,
    params: AnnouncementListParams,
) -> tuple[list[Announcement], int]:
    """Get paginated announcements with filters."""
    query = select(Announcement).where(Announcement.is_visible == True)  # noqa: E712

    if params.stock_code:
        query = query.where(Announcement.stock_code == params.stock_code)
    if params.date_from:
        query = query.where(Announcement.announcement_date >= params.date_from)
    if params.date_to:
        query = query.where(Announcement.announcement_date <= params.date_to)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(Announcement.announcement_date.desc())
    offset = (params.page - 1) * params.page_size
    query = query.offset(offset).limit(params.page_size)

    result = await db.execute(query)
    items = list(result.scalars().all())

    return items, total


async def get_announcement_by_id(
    db: AsyncSession,
    announcement_id: uuid.UUID,
) -> Announcement | None:
    result = await db.execute(
        select(Announcement).where(Announcement.id == announcement_id)
    )
    return result.scalar_one_or_none()


async def get_existing_urls(
    db: AsyncSession,
    stock_code: str,
    urls: list[str],
) -> set[str]:
    """Get set of hkex_urls that already exist for a stock code."""
    if not urls:
        return set()
    result = await db.execute(
        select(Announcement.hkex_url).where(
            Announcement.stock_code == stock_code,
            Announcement.hkex_url.in_(urls),
        )
    )
    return {row[0] for row in result.all()}


async def get_last_sync_date(
    db: AsyncSession,
    stock_code: str,
) -> date | None:
    """Get the most recent announcement_date for a stock code."""
    result = await db.execute(
        select(func.max(Announcement.announcement_date)).where(
            Announcement.stock_code == stock_code
        )
    )
    return result.scalar()


async def bulk_insert_announcements(
    db: AsyncSession,
    records: list[dict],
) -> int:
    """Bulk insert announcement records. Returns count of inserted rows."""
    if not records:
        return 0
    objects = [Announcement(**r) for r in records]
    db.add_all(objects)
    await db.flush()
    return len(objects)


async def update_announcement_file(
    db: AsyncSession,
    announcement_id: uuid.UUID,
    file_path: str,
    file_size: int,
    file_hash: str,
) -> None:
    announcement = await get_announcement_by_id(db, announcement_id)
    if announcement:
        announcement.file_path = file_path
        announcement.file_size = file_size
        announcement.file_hash = file_hash
        announcement.last_synced_at = datetime.utcnow()
        await db.flush()
