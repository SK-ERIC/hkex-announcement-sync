"""
FastAPI application entry point with lifespan management.

FastAPI 应用入口，包含生命周期管理。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.utils.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
        Manage application startup and shutdown lifecycle.

    管理应用启动和关闭生命周期。
    """
    setup_logging()

    # Auto-create SQLite tables on startup (dev mode)
    from app.database import init_db

    await init_db()

    yield


app = FastAPI(
    title="HKEX Announcement Sync",
    description="Sync HKEX company announcements and provide REST API for integration",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_router)


@app.get("/health")
async def health_check():
    """
        Health check endpoint returning service status.

    健康检查端点，返回服务状态。
    """
    return {"status": "ok"}
