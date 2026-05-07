from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "hkex_sync",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Hong_Kong",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

celery_app.conf.beat_schedule = {
    "scheduled-incremental-sync": {
        "task": "app.tasks.sync_tasks.scheduled_incremental_sync",
        "schedule": 3600.0,  # Every hour
    },
}

celery_app.autodiscover_tasks(["app.tasks"])
