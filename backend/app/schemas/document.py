import uuid
from datetime import datetime
from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    mime_type: str | None
    size_bytes: int | None
    status: str
    error_message: str | None
    chunk_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
