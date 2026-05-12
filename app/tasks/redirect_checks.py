import asyncio

from app.celery_app import celery_app
from app.config import get_settings
from app.db import close_mongo_connection, connect_to_mongo, get_database
from app.repositories.object_ids import parse_object_id
from app.repositories.redirect_check_runs import (
    finalize_redirect_check_result,
    get_redirect_check_run_by_id,
    list_queued_results_for_run,
    mark_redirect_check_result_running,
    mark_redirect_check_run_running,
    refresh_redirect_check_run_counts,
)
from app.services.redirect_checker import check_redirect_result


settings = get_settings()


async def process_redirect_check_run_async(run_id: str) -> dict:
    object_id = parse_object_id(run_id)
    if object_id is None:
        return {"status": "failed", "error": "Invalid run id"}

    await connect_to_mongo(settings)
    database = get_database()

    try:
        run = await get_redirect_check_run_by_id(database, run_id)
        if run is None:
            return {"status": "failed", "error": "Redirect check run not found"}

        await mark_redirect_check_run_running(database, object_id)
        queued_results = await list_queued_results_for_run(database, object_id)

        for result in queued_results:
            await mark_redirect_check_result_running(database, result["_id"])

            outcome = await check_redirect_result(
                original_url=str(result.get("original_url") or ""),
                expected_url=str(result.get("expected_url") or ""),
                user_agent=str(result.get("user_agent") or ""),
                timeout_seconds=settings.request_timeout_seconds,
            )

            await finalize_redirect_check_result(
                database,
                result_id=result["_id"],
                passed=outcome.passed,
                redirect_status_code=outcome.redirect_status_code,
                redirect_location=outcome.redirect_location,
                target_status_code=outcome.target_status_code,
                failure_type=outcome.failure_type,
                error_message=outcome.error_message,
            )
            await refresh_redirect_check_run_counts(database, object_id)

        final_counts = await refresh_redirect_check_run_counts(database, object_id)
        return {
            "status": "completed",
            "run_id": run_id,
            "processed": len(queued_results),
            "counts": final_counts,
        }
    finally:
        await close_mongo_connection()


@celery_app.task(name="redirect_checks.process_run")
def process_redirect_check_run(run_id: str) -> dict:
    return asyncio.run(process_redirect_check_run_async(run_id))
