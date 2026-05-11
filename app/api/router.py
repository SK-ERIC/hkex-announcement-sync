from fastapi import APIRouter

from app.api.announcements import router as announcements_router
from app.api.bulletin import router as bulletin_router
from app.api.sync import router as sync_router

api_router = APIRouter(prefix="/api")
api_router.include_router(sync_router)
api_router.include_router(announcements_router)
api_router.include_router(bulletin_router)
