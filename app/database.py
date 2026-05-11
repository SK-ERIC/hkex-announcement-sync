"""
Database engine, session factory, and dependency injection helpers.

数据库引擎、会话工厂和依赖注入辅助模块。
"""

from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings


def _create_engine():
    settings = get_settings()

    # SQLite has limited support for concurrent connections
    if settings.is_sqlite:
        # Ensure parent directory exists for SQLite file
        db_path = settings.DATABASE_URL.split("///")[-1]
        parent = Path(db_path).parent
        if parent and str(parent) != ".":
            parent.mkdir(parents=True, exist_ok=True)

        return create_async_engine(
            settings.DATABASE_URL,
            echo=False,
        )

    return create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )


engine = _create_engine()
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an async database session for FastAPI dependency injection.

    为 FastAPI 依赖注入提供异步数据库会话。
    """
    async with async_session_factory() as session:
        yield session


async def init_db():
    """
    Create all tables. Used for SQLite which doesn't use Alembic migrations in dev.
    """
    from app.models import Base

    settings = get_settings()
    if settings.is_sqlite:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
