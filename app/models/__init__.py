import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, Enum, Index, String, Text, func
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SourceType(str, PyEnum):
    AUTO = "auto"
    MANUAL = "manual"


class Announcement(Base):
    __tablename__ = "announcements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    stock_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    stock_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    title: Mapped[str] = mapped_column(Text, nullable=False)
    announcement_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    filing_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    hkex_url: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size: Mapped[int | None] = mapped_column(BIGINT, nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[SourceType] = mapped_column(
        Enum(SourceType), nullable=False, default=SourceType.AUTO
    )
    is_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_stock_code_hkex_url", "stock_code", "hkex_url", unique=True),
    )
