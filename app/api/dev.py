from fastapi import APIRouter, HTTPException, Query

from app.celery_app import celery_app
from app.config import get_settings
from app.db import get_database
from app.repositories.pages import (
    count_active_pages_for_website,
    list_active_pages_for_website,
)
from app.schemas import CeleryEchoRequest
from app.repositories.websites import get_website_by_id
from app.services.expected_url import build_expected_aiweave_url
from app.tasks.debug import echo
from app.utils.serialization import serialize_document, serialize_value


router = APIRouter(prefix="/dev", tags=["dev"])
settings = get_settings()


@router.get("/websites/{website_id}/pages-summary")
async def get_website_pages_summary(
    website_id: str,
    sample_limit: int = Query(default=10, ge=1, le=50),
) -> dict:
    database = get_database()

    website = await get_website_by_id(database, website_id)
    if website is None:
        raise HTTPException(status_code=404, detail="Website not found")

    active_pages_count = await count_active_pages_for_website(database, website_id)
    sample_pages = await list_active_pages_for_website(
        database,
        website_id,
        limit=sample_limit,
    )

    return {
        "website": serialize_document(website),
        "active_pages_count": active_pages_count,
        "sample_pages": [serialize_document(page) for page in sample_pages],
    }


@router.get("/websites/{website_id}/expected-urls")
async def preview_expected_urls(
    website_id: str,
    sample_limit: int = Query(default=10, ge=1, le=50),
) -> dict:
    database = get_database()

    website = await get_website_by_id(database, website_id)
    if website is None:
        raise HTTPException(status_code=404, detail="Website not found")

    website_domain = str(website.get("domain") or "")
    sample_pages = await list_active_pages_for_website(
        database,
        website_id,
        limit=sample_limit,
    )

    previews = []
    for page in sample_pages:
        original_url = str(page.get("page_url") or "")
        error = None
        expected_url = None

        try:
            expected_url = build_expected_aiweave_url(
                original_url=original_url,
                website_domain=website_domain,
                aiweave_base_url=settings.aiweave_base_url,
            )
        except ValueError as exc:
            error = str(exc)

        previews.append(
            {
                "page_id": serialize_value(page.get("_id")),
                "original_url": original_url,
                "database_slug": page.get("slug"),
                "expected_url": expected_url,
                "error": error,
            }
        )

    return {
        "website_id": serialize_value(website.get("_id")),
        "website_domain": website_domain,
        "aiweave_base_url": settings.aiweave_base_url,
        "sample_count": len(previews),
        "previews": previews,
    }


@router.post("/celery/echo")
async def enqueue_celery_echo(payload: CeleryEchoRequest) -> dict:
    task = echo.delay(payload.message)
    return {
        "task_id": task.id,
        "status": task.status,
        "message": "Task queued",
    }


@router.get("/celery/tasks/{task_id}")
async def get_celery_task_status(task_id: str) -> dict:
    task_result = celery_app.AsyncResult(task_id)
    response = {
        "task_id": task_id,
        "status": task_result.status,
        "ready": task_result.ready(),
        "successful": task_result.successful(),
        "result": None,
    }

    if task_result.ready():
        response["result"] = task_result.result

    return response
