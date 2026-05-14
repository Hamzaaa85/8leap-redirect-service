from datetime import UTC, datetime

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import Settings
from app.repositories.object_ids import parse_object_id
from app.services.expected_url import build_expected_aiweave_url


def utc_now() -> datetime:
    return datetime.now(UTC)


async def create_redirect_check_run(
    database: AsyncIOMotorDatabase,
    *,
    website: dict,
    pages: list[dict],
    bot_user_agents: list[str],
    settings: Settings,
) -> dict:
    now = utc_now()
    website_id = website["_id"]
    website_domain = str(website.get("domain") or "")
    total_checks = len(pages) * len(bot_user_agents)

    run_doc = {
        "website_id": website_id,
        "website_name": website.get("name"),
        "website_domain": website_domain,
        "status": "queued" if total_checks > 0 else "completed",
        "total_checks": total_checks,
        "completed_checks": 0,
        "passed_checks": 0,
        "failed_checks": 0,
        "queued_checks": total_checks,
        "bot_user_agents": bot_user_agents,
        "created_by": None,
        "started_at": None,
        "finished_at": now if total_checks == 0 else None,
        "created_at": now,
        "updated_at": now,
    }

    insert_result = await database.redirect_check_runs.insert_one(run_doc)
    run_id = insert_result.inserted_id

    result_docs = []
    failed_preflight_count = 0

    for page in pages:
        original_url = str(page.get("page_url") or "")
        expected_url = None
        preflight_error = None

        try:
            expected_url = build_expected_aiweave_url(
                original_url=original_url,
                website_domain=website_domain,
                aiweave_base_url=settings.aiweave_base_url,
            )
        except ValueError as exc:
            preflight_error = str(exc)

        for user_agent in bot_user_agents:
            status = "failed" if preflight_error else "queued"
            if preflight_error:
                failed_preflight_count += 1

            result_docs.append(
                {
                    "run_id": run_id,
                    "website_id": website_id,
                    "page_id": page.get("_id"),
                    "original_url": original_url,
                    "expected_url": expected_url,
                    "user_agent": user_agent,
                    "status": status,
                    "redirect_status_code": None,
                    "redirect_location": None,
                    "target_status_code": None,
                    "failure_type": (
                        "expected_url_build_error" if preflight_error else None
                    ),
                    "error_message": preflight_error,
                    "checked_at": now if preflight_error else None,
                    "created_at": now,
                    "updated_at": now,
                }
            )

    if result_docs:
        await database.redirect_check_results.insert_many(result_docs)

    if failed_preflight_count:
        queued_checks = total_checks - failed_preflight_count
        run_status = "queued" if queued_checks > 0 else "completed"
        await database.redirect_check_runs.update_one(
            {"_id": run_id},
            {
                "$set": {
                    "status": run_status,
                    "completed_checks": failed_preflight_count,
                    "failed_checks": failed_preflight_count,
                    "queued_checks": queued_checks,
                    "finished_at": now if queued_checks == 0 else None,
                    "updated_at": now,
                }
            },
        )

    return await get_redirect_check_run_by_id(database, str(run_id))


async def get_redirect_check_run_by_id(
    database: AsyncIOMotorDatabase,
    run_id: str,
) -> dict | None:
    object_id = parse_object_id(run_id)
    if object_id is None:
        return None

    return await database.redirect_check_runs.find_one({"_id": object_id})


async def get_latest_redirect_check_run_for_website(
    database: AsyncIOMotorDatabase,
    website_id: str,
) -> dict | None:
    object_id = parse_object_id(website_id)
    if object_id is None:
        return None

    return await database.redirect_check_runs.find_one(
        {"website_id": object_id},
        sort=[("created_at", -1)],
    )


async def list_redirect_check_results(
    database: AsyncIOMotorDatabase,
    run_id: str,
    *,
    status: str | None = None,
    limit: int = 50,
) -> list[dict]:
    object_id = parse_object_id(run_id)
    if object_id is None:
        return []

    query: dict = {"run_id": object_id}
    if status:
        query["status"] = status

    cursor = (
        database.redirect_check_results.find(query)
        .sort("created_at", 1)
        .limit(limit)
    )
    return await cursor.to_list(length=limit)


async def mark_redirect_check_run_running(
    database: AsyncIOMotorDatabase,
    run_id: ObjectId,
) -> None:
    now = utc_now()
    await database.redirect_check_runs.update_one(
        {"_id": run_id},
        {
            "$set": {
                "status": "running",
                "started_at": now,
                "updated_at": now,
            }
        },
    )


async def list_queued_results_for_run(
    database: AsyncIOMotorDatabase,
    run_id: ObjectId,
    *,
    limit: int | None = None,
) -> list[dict]:
    cursor = database.redirect_check_results.find(
        {
            "run_id": run_id,
            "status": "queued",
        }
    ).sort("created_at", 1)
    if limit is not None:
        cursor = cursor.limit(limit)
    return await cursor.to_list(length=limit)


async def has_queued_results_for_run(
    database: AsyncIOMotorDatabase,
    run_id: ObjectId,
) -> bool:
    result = await database.redirect_check_results.find_one(
        {
            "run_id": run_id,
            "status": "queued",
        },
        {"_id": 1},
    )
    return result is not None


async def mark_redirect_check_result_running(
    database: AsyncIOMotorDatabase,
    result_id: ObjectId,
) -> None:
    await database.redirect_check_results.update_one(
        {"_id": result_id},
        {
            "$set": {
                "status": "running",
                "updated_at": utc_now(),
            }
        },
    )


async def finalize_redirect_check_result(
    database: AsyncIOMotorDatabase,
    *,
    result_id: ObjectId,
    passed: bool,
    redirect_status_code: int | None,
    redirect_location: str | None,
    target_status_code: int | None,
    failure_type: str | None,
    error_message: str | None,
) -> None:
    now = utc_now()
    await database.redirect_check_results.update_one(
        {"_id": result_id},
        {
            "$set": {
                "status": "passed" if passed else "failed",
                "redirect_status_code": redirect_status_code,
                "redirect_location": redirect_location,
                "target_status_code": target_status_code,
                "failure_type": failure_type,
                "error_message": error_message,
                "checked_at": now,
                "updated_at": now,
            }
        },
    )


async def refresh_redirect_check_run_counts(
    database: AsyncIOMotorDatabase,
    run_id: ObjectId,
) -> dict:
    pipeline = [
        {"$match": {"run_id": run_id}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]
    rows = await database.redirect_check_results.aggregate(pipeline).to_list(
        length=None
    )
    counts = {row["_id"]: row["count"] for row in rows}

    passed = counts.get("passed", 0)
    failed = counts.get("failed", 0)
    queued = counts.get("queued", 0)
    running = counts.get("running", 0)
    completed = passed + failed
    total = completed + queued + running
    is_done = queued == 0 and running == 0
    now = utc_now()

    update = {
        "total_checks": total,
        "completed_checks": completed,
        "passed_checks": passed,
        "failed_checks": failed,
        "queued_checks": queued,
        "updated_at": now,
    }

    if is_done:
        update["status"] = "completed"
        update["finished_at"] = now
    else:
        update["status"] = "running"

    await database.redirect_check_runs.update_one(
        {"_id": run_id},
        {"$set": update},
    )
    return update
