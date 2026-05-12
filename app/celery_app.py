from celery import Celery

from app.config import get_settings


settings = get_settings()

celery_app = Celery(
    "redirect_checker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.debug", "app.tasks.redirect_checks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    result_expires=settings.celery_result_expires_seconds,
)
