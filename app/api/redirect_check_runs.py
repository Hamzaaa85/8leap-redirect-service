from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.db import get_database
from app.repositories.pages import list_all_active_pages_for_website
from app.repositories.redirect_check_runs import (
    create_redirect_check_run,
    get_redirect_check_run_by_id,
    list_redirect_check_results,
)
from app.repositories.websites import get_website_by_id
from app.schemas import CreateRedirectCheckRunRequest
from app.tasks.redirect_checks import process_redirect_check_run
from app.utils.serialization import serialize_document


router = APIRouter(prefix="/redirect-check-runs", tags=["redirect-check-runs"])
settings = get_settings()


def normalize_bot_user_agents(user_agents: list[str] | None) -> list[str]:
    if user_agents is None:
        return settings.bot_user_agents

    normalized = [user_agent.strip() for user_agent in user_agents if user_agent.strip()]
    if not normalized:
        raise HTTPException(
            status_code=400,
            detail="At least one bot user agent is required",
        )

    return normalized


@router.post("")
async def create_run(payload: CreateRedirectCheckRunRequest) -> dict:
    database = get_database()

    website = await get_website_by_id(database, payload.website_id)
    if website is None:
        raise HTTPException(status_code=404, detail="Website not found")

    pages = await list_all_active_pages_for_website(database, payload.website_id)
    bot_user_agents = normalize_bot_user_agents(payload.bot_user_agents)

    run = await create_redirect_check_run(
        database,
        website=website,
        pages=pages,
        bot_user_agents=bot_user_agents,
        settings=settings,
    )

    task_id = None
    if run and run.get("queued_checks", 0) > 0:
        task = process_redirect_check_run.delay(str(run["_id"]))
        task_id = task.id

    return {
        "run": serialize_document(run),
        "task_id": task_id,
    }


@router.get("/{run_id}")
async def get_run(run_id: str) -> dict:
    database = get_database()

    run = await get_redirect_check_run_by_id(database, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Redirect check run not found")

    return {"run": serialize_document(run)}


@router.get("/{run_id}/results")
async def get_run_results(
    run_id: str,
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict:
    database = get_database()

    run = await get_redirect_check_run_by_id(database, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Redirect check run not found")

    results = await list_redirect_check_results(
        database,
        run_id,
        status=status,
        limit=limit,
    )

    return {
        "run_id": run_id,
        "count": len(results),
        "results": [serialize_document(result) for result in results],
    }
