from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.object_ids import parse_object_id


ACTIVE_PAGES_FILTER = {
    "status": "active",
    "page_url": {"$exists": True, "$ne": ""},
}


async def count_active_pages_for_website(
    database: AsyncIOMotorDatabase,
    website_id: str,
) -> int:
    object_id = parse_object_id(website_id)
    if object_id is None:
        return 0

    return await database.pages.count_documents(
        {
            "website_id": object_id,
            **ACTIVE_PAGES_FILTER,
        }
    )


async def list_active_pages_for_website(
    database: AsyncIOMotorDatabase,
    website_id: str,
    *,
    limit: int | None = 10,
) -> list[dict]:
    object_id = parse_object_id(website_id)
    if object_id is None:
        return []

    cursor = database.pages.find(
        {
            "website_id": object_id,
            **ACTIVE_PAGES_FILTER,
        },
        {
            "page_url": 1,
            "slug": 1,
            "status": 1,
            "content_status": 1,
            "variant": 1,
            "ai_status": 1,
            "updatedAt": 1,
        },
    ).sort("updatedAt", -1)

    if limit is not None:
        cursor = cursor.limit(limit)

    return await cursor.to_list(length=limit)


async def list_all_active_pages_for_website(
    database: AsyncIOMotorDatabase,
    website_id: str,
) -> list[dict]:
    return await list_active_pages_for_website(
        database,
        website_id,
        limit=None,
    )
