from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.utils.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    return {"status": "ok"}
