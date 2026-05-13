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
    redirect_check_chunk_size: int = 50
    redirect_check_delay_between_checks_seconds: float = 1.0
    redirect_check_delay_between_chunks_seconds: int = 30
    bot_user_agents_csv: str = (
        "OAI-SearchBot,ChatGPT-User,Claude-SearchBot,PerplexityBot"
    )

    @field_validator("aiweave_base_url")
    @classmethod
    def normalize_base_url(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("redirect_check_chunk_size")
    @classmethod
    def validate_chunk_size(cls, value: int) -> int:
        if value < 1:
            raise ValueError("Redirect check chunk size must be at least 1")
        return value

    @field_validator(
        "redirect_check_delay_between_checks_seconds",
        "redirect_check_delay_between_chunks_seconds",
    )
    @classmethod
    def validate_redirect_check_delays(cls, value: int | float) -> int | float:
        if value < 0:
            raise ValueError("Redirect check delays cannot be negative")
        return value

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
