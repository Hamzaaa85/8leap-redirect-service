import asyncio

from pymongo.errors import (
    AutoReconnect,
    ConnectionFailure,
    InvalidOperation,
    NetworkTimeout,
    ServerSelectionTimeoutError,
)

from app.celery_app import celery_app
from app.config import get_settings
from app.db import mongo_connection
from app.repositories.object_ids import parse_object_id
from app.repositories.redirect_check_runs import (
    finalize_redirect_check_result,
    get_redirect_check_run_by_id,
    has_queued_results_for_run,
    list_queued_results_for_run,
    mark_redirect_check_result_running,
    mark_redirect_check_run_running,
    refresh_redirect_check_run_counts,
)
from app.services.redirect_checker import check_redirect_result


settings = get_settings()

_CELERY_RETRYABLE_ERRORS = (
    ConnectionFailure,
    ServerSelectionTimeoutError,
    NetworkTimeout,
    AutoReconnect,
    InvalidOperation,
    RuntimeError,
)


async def process_redirect_check_run_async(run_id: str) -> dict:
    object_id = parse_object_id(run_id)
    if object_id is None:
        return {"status": "failed", "error": "Invalid run id"}

    async with mongo_connection(settings) as database:
        run = await get_redirect_check_run_by_id(database, run_id)
        if run is None:
            return {"status": "failed", "error": "Redirect check run not found"}

        await mark_redirect_check_run_running(database, object_id)
        queued_results = await list_queued_results_for_run(
            database,
            object_id,
            limit=settings.redirect_check_chunk_size,
        )

        for index, result in enumerate(queued_results):
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

            is_last_result = index == len(queued_results) - 1
            if (
                not is_last_result
                and settings.redirect_check_delay_between_checks_seconds > 0
            ):
                await asyncio.sleep(
                    settings.redirect_check_delay_between_checks_seconds
                )

        final_counts = await refresh_redirect_check_run_counts(database, object_id)
        has_more_queued = await has_queued_results_for_run(database, object_id)

        if has_more_queued:
            process_redirect_check_run.apply_async(
                args=[run_id],
                countdown=settings.redirect_check_delay_between_chunks_seconds,
            )

        return {
            "status": "chunk_completed" if has_more_queued else "completed",
            "run_id": run_id,
            "processed": len(queued_results),
            "scheduled_next_chunk": has_more_queued,
            "counts": final_counts,
        }


@celery_app.task(
    bind=True,
    name="redirect_checks.process_run",
    autoretry_for=_CELERY_RETRYABLE_ERRORS,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def process_redirect_check_run(self, run_id: str) -> dict:
    return asyncio.run(process_redirect_check_run_async(run_id))
