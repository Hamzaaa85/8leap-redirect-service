from pydantic import BaseModel, Field


class CreateRedirectCheckRunRequest(BaseModel):
    website_id: str = Field(..., min_length=1)
    bot_user_agents: list[str] | None = None


class CeleryEchoRequest(BaseModel):
    message: str = Field(default="hello celery", min_length=1)
