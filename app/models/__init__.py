"""
SQLAlchemy ORM models for HKEX announcement data.

港交所公告数据的 SQLAlchemy ORM 模型。
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, Enum, Index, String, Text, func
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    SQLAlchemy declarative base class for all ORM models.

    所有 ORM 模型的 SQLAlchemy 声明式基类。
    """

    pass


class SourceType(str, PyEnum):
    """
    Enumeration of announcement data source types.

    公告数据来源类型的枚举。

    Attributes:
    AUTO: Automatically synced from HKEX. / 从港交所自动同步。
    MANUAL: Manually entered by user. / 用户手动录入。

    """

    AUTO = "auto"
    MANUAL = "manual"


class AnnouncementStatus(str, PyEnum):
    """
    HKEX announcement lifecycle status.

    港交所公告生命周期状态枚举。

    Attributes:
    ACTIVE: Normal active announcement. / 正常公告。
    CANCELLED_SUPERSEDED: Replaced by a newer announcement. / 被新公告取代。
    CANCELLED_REISSUED: Withdrawn and corrected version re-published. / 撤回后重新发布。
    HEADLINES_REVISED: Headline was revised. / 标题被修订。

    """

    ACTIVE = "active"
    CANCELLED_SUPERSEDED = "cancelled_superseded"
    CANCELLED_REISSUED = "cancelled_reissued"
    HEADLINES_REVISED = "headlines_revised"


class Announcement(Base):
    """
    ORM model representing an HKEX announcement with multilingual fields.

    港交所公告的 ORM 模型，包含多语言字段。

    Stores announcement metadata in English (EN), Traditional Chinese (ZH),
    and Simplified Chinese (SC/CN), along with file storage information.

    以英文（EN）、繁体中文（ZH）和简体中文（SC/CN）存储公告元数据，
    同时包含文件存储信息。

    Attributes:
    id: Unique UUID primary key. / 唯一 UUID 主键。
    stock_code: HKEX stock code (e.g. '00700'). / 港交所股票代码。
    news_id: HKEX news identifier. / 港交所新闻标识符。
    announcement_date: Date and time of the announcement. / 公告日期时间。
    title_en/zh/cn: Multilingual announcement titles. / 多语言公告标题。
    stock_name_en/zh/cn: Multilingual stock names. / 多语言股票名称。
    filing_type_en/zh/cn: Multilingual filing types. / 多语言文件类型。
    short_text_en/zh/cn: Multilingual short descriptions. / 多语言简短描述。
    long_text_en/zh/cn: Multilingual long descriptions. / 多语言详细描述。
    hkex_url_en/zh: HKEX disclosure URLs per language. / 各语言的港交所披露链接。
    file_type: File format (e.g. 'PDF'). / 文件格式。
    file_path_en/zh: Local storage paths for downloaded files. / 下载文件的本地存储路径。
    file_size: File size in bytes. / 文件大小（字节）。
    file_hash: SHA-256 hash of the file. / 文件的 SHA-256 哈希值。
    source: Data source (auto/manual). / 数据来源（自动/手动）。
    is_visible: Whether the announcement is visible in API. / 公告是否在 API 中可见。
    last_synced_at: Timestamp of last sync. / 上次同步时间戳。
    created_at: Record creation timestamp. / 记录创建时间戳。
    updated_at: Record update timestamp. / 记录更新时间戳。

    """

    __tablename__ = "announcements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    stock_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    news_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    announcement_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)

    # Multilingual titles
    title_en: Mapped[str] = mapped_column(Text, nullable=False, default="")
    title_zh: Mapped[str] = mapped_column(Text, nullable=False, default="")
    title_cn: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Multilingual stock names
    stock_name_en: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    stock_name_zh: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    stock_name_cn: Mapped[str] = mapped_column(String(200), nullable=False, default="")

    # Multilingual filing types
    filing_type_en: Mapped[str | None] = mapped_column(String(200), nullable=True)
    filing_type_zh: Mapped[str | None] = mapped_column(String(200), nullable=True)
    filing_type_cn: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Multilingual short/long text
    short_text_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    short_text_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    short_text_cn: Mapped[str | None] = mapped_column(Text, nullable=True)
    long_text_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    long_text_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    long_text_cn: Mapped[str | None] = mapped_column(Text, nullable=True)

    # File links per language
    hkex_url_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    hkex_url_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_type: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Storage fields (for downloaded files)
    file_path_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size_en: Mapped[int | None] = mapped_column(BIGINT, nullable=True)
    file_size_zh: Mapped[int | None] = mapped_column(BIGINT, nullable=True)
    file_hash_en: Mapped[str | None] = mapped_column(String(64), nullable=True)
    file_hash_zh: Mapped[str | None] = mapped_column(String(64), nullable=True)
    file_size: Mapped[int | None] = mapped_column(BIGINT, nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    source: Mapped[SourceType] = mapped_column(Enum(SourceType), nullable=False, default=SourceType.AUTO)
    is_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="active", server_default="active", index=True
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("ix_stock_code_news_id", "stock_code", "news_id", unique=True),)


from app.models.sync_log import SyncLog as SyncLog, SyncStatus as SyncStatus  # noqa: E402
