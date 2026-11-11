"""Celery application used by backend (producer) and worker (consumer)."""
from celery import Celery

from src.config.settings import settings

celery_app = Celery(
    "featpoint",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["src.tasks.sample_job", "src.tasks.backfill"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    worker_hijack_root_logger=False,
    task_acks_late=False,
    task_default_queue="featpoint",
)

app = celery_app
celery = celery_app
