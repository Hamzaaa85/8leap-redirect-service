from datetime import UTC, datetime

from app.celery_app import celery_app


@celery_app.task(name="debug.echo")
def echo(message: str) -> dict[str, str]:
    return {
        "message": message,
        "processed_at": datetime.now(UTC).isoformat(),
    }
