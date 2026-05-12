from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "8thLeap Redirect Checker"
    app_version: str = "0.1.0"
    environment: str = "development"

    mongodb_uri: str = ""
    mongodb_database: str = "8thleep"
    mongodb_server_selection_timeout_ms: int = 5000

    aiweave_base_url: str = "https://aiweave.app"
    redis_url: str = "redis://localhost:6379/0"
    celery_result_expires_seconds: int = 3600

    request_timeout_seconds: int = 30
    max_concurrency: int = 10
    bot_user_agents_csv: str = (
        "OAI-SearchBot,ChatGPT-User,Claude-SearchBot,PerplexityBot"
    )

    @field_validator("aiweave_base_url")
    @classmethod
    def normalize_base_url(cls, value: str) -> str:
        return value.rstrip("/")

    @property
    def bot_user_agents(self) -> list[str]:
        return [
            user_agent.strip()
            for user_agent in self.bot_user_agents_csv.split(",")
            if user_agent.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
