import uuid
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
import bleach


class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    llm_model: str = Field(default="ollama:llama3.2", max_length=100)
    llm_api_key: str | None = Field(default=None, max_length=200)
    embedding_api_key: str | None = Field(default=None, max_length=200)
    embedding_model: str = Field(default="ollama:nomic-embed-text", max_length=100)
    system_prompt: str | None = Field(default=None, max_length=4000)
    welcome_message: str = Field(default="Cześć! Jak mogę Ci pomóc? 👋", max_length=500)
    chat_title: str = Field(default="AI Assistant", max_length=255)
    chat_color: str = Field(default="#6366f1", pattern=r"^#[0-9a-fA-F]{6}$")
    monthly_token_limit: int = Field(default=1_000_000, ge=1000)
    daily_token_limit: int = Field(default=50_000, ge=100)

    @field_validator("welcome_message")
    @classmethod
    def sanitize_welcome_message(cls, v: str) -> str:
        return bleach.clean(v, tags=[], strip=True)


class TenantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    llm_model: str | None = Field(default=None, max_length=100)
    llm_api_key: str | None = Field(default=None, max_length=200)
    embedding_api_key: str | None = Field(default=None, max_length=200)
    embedding_model: str | None = Field(default=None, max_length=100)
    system_prompt: str | None = Field(default=None, max_length=4000)
    welcome_message: str | None = Field(default=None, max_length=500)
    chat_title: str | None = Field(default=None, max_length=255)
    chat_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    monthly_token_limit: int | None = Field(default=None, ge=1000)
    daily_token_limit: int | None = Field(default=None, ge=100)
    is_active: bool | None = None
    is_blocked: bool | None = None
    blocked_reason: str | None = None

    @field_validator("welcome_message")
    @classmethod
    def sanitize_welcome_message(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return bleach.clean(v, tags=[], strip=True)


class TenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    is_active: bool
    is_blocked: bool
    blocked_reason: str | None
    llm_model: str
    llm_api_key: str | None
    embedding_api_key: str | None
    embedding_model: str
    system_prompt: str | None
    welcome_message: str
    chat_title: str
    chat_color: str
    chat_logo_url: str | None
    monthly_token_limit: int
    daily_token_limit: int
    tokens_used_month: int
    tokens_used_day: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatConfig(BaseModel):
    chat_title: str
    chat_color: str
    welcome_message: str
    is_active: bool
    chat_logo_url: str | None = None
