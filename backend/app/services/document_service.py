"""Document management: save upload, validate, track in DB."""
import os
import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.config import get_settings
from app.models.document import Document
from app.services.parser_service import ALLOWED_MIME_TYPES, ALLOWED_EXTENSIONS

settings = get_settings()

MAX_BYTES = settings.upload_max_size_mb * 1024 * 1024


def sanitize_filename(filename: str) -> str:
    """Remove path traversal and dangerous characters."""
    # Strip directory components
    name = Path(filename).name
    # Replace anything that's not alphanumeric, dash, underscore, dot
    name = re.sub(r"[^\w\-.]", "_", name)
    # Collapse multiple dots
    name = re.sub(r"\.{2,}", ".", name)
    return name or "upload"


def _safe_path(tenant_id: uuid.UUID, filename: str) -> Path:
    upload_dir = Path(settings.upload_dir)
    tenant_dir = upload_dir / str(tenant_id)
    tenant_dir.mkdir(parents=True, exist_ok=True)

    safe_name = sanitize_filename(filename)
    file_id = uuid.uuid4().hex[:8]
    final_name = f"{file_id}_{safe_name}"
    file_path = tenant_dir / final_name

    # Guard against path traversal
    resolved = file_path.resolve()
    base_resolved = upload_dir.resolve()
    if not str(resolved).startswith(str(base_resolved)):
        raise ValueError("Path traversal detected")

    return file_path


async def save_upload(
    tenant_id: uuid.UUID,
    file: UploadFile,
    db: AsyncSession,
) -> Document:
    # Validate MIME type
    mime = file.content_type or ""
    ext = Path(file.filename or "").suffix.lower()

    if mime not in ALLOWED_MIME_TYPES and ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {mime}",
        )

    # Read and validate size
    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large (max {settings.upload_max_size_mb}MB)",
        )

    # Save to disk
    try:
        file_path = _safe_path(tenant_id, file.filename or "upload")
        file_path.write_bytes(content)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")

    # Create DB record
    doc = Document(
        tenant_id=tenant_id,
        name=sanitize_filename(file.filename or "upload"),
        file_path=str(file_path),
        mime_type=mime or ext,
        size_bytes=len(content),
        status="pending",
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)
    return doc


async def get_document(doc_id: uuid.UUID, tenant_id: uuid.UUID, db: AsyncSession) -> Document:
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.tenant_id == tenant_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


async def list_documents(tenant_id: uuid.UUID, db: AsyncSession) -> list[Document]:
    result = await db.execute(
        select(Document).where(Document.tenant_id == tenant_id).order_by(Document.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_document(doc_id: uuid.UUID, tenant_id: uuid.UUID, db: AsyncSession) -> None:
    doc = await get_document(doc_id, tenant_id, db)

    # Remove file from disk
    if doc.file_path and os.path.exists(doc.file_path):
        # Safety check
        upload_dir = Path(settings.upload_dir).resolve()
        file_path = Path(doc.file_path).resolve()
        if str(file_path).startswith(str(upload_dir)):
            os.unlink(file_path)

    await db.delete(doc)
