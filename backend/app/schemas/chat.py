import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: uuid.UUID
    conversation_id: uuid.UUID | None = None


class SourceChunk(BaseModel):
    chunk_id: uuid.UUID
    document_name: str
    content_preview: str  # first 200 chars


class ChatMessageResponse(BaseModel):
    answer: str
    conversation_id: uuid.UUID
    sources: list[SourceChunk]
    tokens_used: int
    estimated_cost_usd: float


class ConversationSummary(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    started_at: datetime
    last_message_at: datetime
    message_count: int
    user_ip_hash: str | None

    model_config = {"from_attributes": True}


class MessageDetail(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime
    total_tokens: int | None
    retrieved_chunk_ids: list[uuid.UUID] | None

    model_config = {"from_attributes": True}
