from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.dev import router as dev_router
from app.api.redirect_check_runs import router as redirect_check_runs_router
from app.config import get_settings
from app.db import close_mongo_connection, connect_to_mongo, ping_mongo


settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await connect_to_mongo(settings)
    try:
        yield
    finally:
        await close_mongo_connection()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.include_router(dev_router)
app.include_router(redirect_check_runs_router)


@app.get("/health")
def health_check() -> dict[str, str | list[str]]:
    return {
        "status": "healthy",
        "environment": settings.environment,
        "aiweave_base_url": settings.aiweave_base_url,
        "bot_user_agents": settings.bot_user_agents,
    }


@app.get("/health/db")
async def database_health_check() -> dict[str, str | bool]:
    is_connected = await ping_mongo()
    return {
        "status": "healthy" if is_connected else "unhealthy",
        "database": settings.mongodb_database,
        "connected": is_connected,
    }
