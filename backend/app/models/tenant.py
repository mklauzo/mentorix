import uuid
from datetime import datetime, date
from sqlalchemy import Boolean, BigInteger, DateTime, Date, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # LLM config
    llm_model: Mapped[str] = mapped_column(String(100), default="ollama:llama3.2", nullable=False)
    llm_api_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    embedding_api_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    embedding_model: Mapped[str] = mapped_column(String(100), default="ollama:nomic-embed-text", nullable=False)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    welcome_message: Mapped[str] = mapped_column(Text, default="Cześć! Jak mogę Ci pomóc? 👋", nullable=False)

    # Branding
    chat_title: Mapped[str] = mapped_column(String(255), default="AI Assistant", nullable=False)
    chat_color: Mapped[str] = mapped_column(String(7), default="#6366f1", nullable=False)
    chat_logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Token limits & usage
    monthly_token_limit: Mapped[int] = mapped_column(BigInteger, default=1_000_000, nullable=False)
    daily_token_limit: Mapped[int] = mapped_column(BigInteger, default=50_000, nullable=False)
    tokens_used_month: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    tokens_used_day: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    last_reset_daily: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_reset_monthly: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    users: Mapped[list["User"]] = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    documents: Mapped[list["Document"]] = relationship("Document", back_populates="tenant", cascade="all, delete-orphan")
    conversations: Mapped[list["Conversation"]] = relationship("Conversation", back_populates="tenant", cascade="all, delete-orphan")
