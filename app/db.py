from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import Settings


_client: AsyncIOMotorClient | None = None
_database: AsyncIOMotorDatabase | None = None


async def connect_to_mongo(settings: Settings) -> None:
    global _client, _database

    if _client is not None:
        return

    if not settings.mongodb_uri.strip():
        raise RuntimeError("MONGODB_URI is required")

    _client = AsyncIOMotorClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=settings.mongodb_server_selection_timeout_ms,
    )
    await _client.admin.command("ping")
    _database = _client[settings.mongodb_database]


async def close_mongo_connection() -> None:
    global _client, _database

    if _client is not None:
        _client.close()

    _client = None
    _database = None


def get_database() -> AsyncIOMotorDatabase:
    if _database is None:
        raise RuntimeError("MongoDB is not connected")

    return _database


async def ping_mongo() -> bool:
    if _client is None:
        return False

    await _client.admin.command("ping")
    return True


@asynccontextmanager
async def mongo_connection(settings: Settings) -> AsyncIterator[AsyncIOMotorDatabase]:
    """Open a dedicated Motor client for the current asyncio loop and close on exit.

    Use this inside Celery tasks that call ``asyncio.run(...)`` so the client is never
    shared with FastAPI's global singleton (which is bound to a different event loop)
    or reused across separate ``asyncio.run`` invocations after close.
    """
    if not settings.mongodb_uri.strip():
        raise RuntimeError("MONGODB_URI is required")

    client = AsyncIOMotorClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=settings.mongodb_server_selection_timeout_ms,
    )
    try:
        await client.admin.command("ping")
        yield client[settings.mongodb_database]
    finally:
        client.close()
