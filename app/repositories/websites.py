from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.object_ids import parse_object_id


async def get_website_by_id(
    database: AsyncIOMotorDatabase,
    website_id: str,
) -> dict | None:
    object_id = parse_object_id(website_id)
    if object_id is None:
        return None

    return await database.websites.find_one({"_id": object_id})
