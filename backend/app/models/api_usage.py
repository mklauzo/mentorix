import uuid
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.db.database import Base


class ApiUsage(Base):
    __tablename__ = "api_usage"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    embedding_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    chat_tokens_input: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    chat_tokens_output: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0, nullable=False)
    total_queries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
