from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "mentorix",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.process_document"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "app.tasks.process_document.process_document": {"queue": "document_processing"},
    },
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
)
