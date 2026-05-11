"""
Pydantic schemas for announcement API request/response models.

公告 API 请求/响应模型的 Pydantic 模式。
"""

from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class LanguageEnum(str, Enum):
    """
        Supported language codes for announcement queries.

    公告查询支持的语言代码枚举。

    Attributes:
        en: English / 英文
        zh: Traditional Chinese / 繁体中文
        cn: Simplified Chinese / 简体中文

    """

    en = "en"
    zh = "zh"
    cn = "cn"


class SortOrderEnum(str, Enum):
    """
        Sort order for query results.

    查询结果的排序方向枚举。

    Attributes:
        desc: Descending order / 降序
        asc: Ascending order / 升序

    """

    desc = "desc"
    asc = "asc"


# --- Existing API Schemas (updated with language support) ---


class AnnouncementResponse(BaseModel):
    """
        Pydantic schema for a single announcement in API responses.

    API 响应中单条公告的 Pydantic 模式。

    Returns language-specific fields based on the requested language.
    根据请求的语言返回对应语言的字段。
    """

    id: UUID
    stock_code: str
    news_id: str
    title: str
    stock_name: str
    filing_type: str | None = None
    short_text: str | None = None
    long_text: str | None = None
    hkex_url: str | None = None
    file_type: str | None = None
    file_size: int | None = None
    announcement_date: datetime | None = None
    source: str
    is_visible: bool = True
    download_url: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AnnouncementListResponse(BaseModel):
    """
        Paginated list response wrapping multiple announcement items.

    包含多条公告的分页列表响应模式。
    """

    items: list[AnnouncementResponse]
    total: int
    page: int
    page_size: int


class AnnouncementDetailResponse(AnnouncementResponse):
    """
        Extended announcement response with additional file metadata fields.

    包含额外文件元数据字段的扩展公告响应模式。
    """

    file_hash: str | None = None
    last_synced_at: datetime | None = None


class AnnouncementListParams(BaseModel):
    """
        Query parameters for filtering and paginating announcement list requests.

    用于过滤和分页公告列表请求的查询参数模式。
    """

    stock_code: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    language: LanguageEnum = LanguageEnum.en


# --- Bulletin API Schemas ---


class DataStatus(BaseModel):
    """
        Status metadata for bulletin API responses.

    公告 API 响应的状态元数据模式。
    """

    status_code: int = 100
    status_description: str = "正常返回"
    response_date_time: str = ""
    data_total_count: int = 0


class BulletinData(BaseModel):
    """
        Schema for a single bulletin entry in HKEX-compatible format.

    港交所兼容格式的单条公告数据模式。
    """

    symbol: str
    stock_name: str
    title: str
    short_text: str | None = None
    long_text: str | None = None
    file_size: str | None = None
    file_type: str | None = None
    file_link: str | None = None
    bulletin_date_time: str | None = None
    unique_id: str


class BulletinListResponse(BaseModel):
    """
        Response schema for the bulletin API wrapping status and data list.

    公告 API 的响应模式，包含状态和数据列表。
    """

    data_status: DataStatus
    data: list[BulletinData]


class BulletinQueryParams(BaseModel):
    """
        Query parameters for the bulletin API with pagination, language, and sorting.

    公告 API 的查询参数，包含分页、语言和排序选项。
    """

    symbol: str
    pageindex: int = Field(default=1, ge=1)
    pagesize: int = Field(default=10, ge=1, le=20)
    language: LanguageEnum = LanguageEnum.en
    sortorder: SortOrderEnum = SortOrderEnum.desc
