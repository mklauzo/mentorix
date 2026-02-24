"""Celery task: parse → chunk → embed → store document."""
import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.tenant import Tenant
from app.services.parser_service import parse_document
from app.services.chunker_service import chunk_text
from app.services.embedding_service import embed_texts
from app.tasks.celery_app import celery_app

settings = get_settings()


def _make_session_factory():
    """Create a fresh engine with NullPool for each Celery task.
    NullPool avoids event-loop conflicts: asyncio.run() creates a new loop
    each time, which is incompatible with SQLAlchemy's default connection pool.
    """
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False), engine


@celery_app.task(
    name="app.tasks.process_document.process_document",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def process_document(self, doc_id: str, tenant_id: str) -> dict:
    """
    Full document processing pipeline:
    1. Parse document (PDF/DOCX/TXT/MD/HTML)
    2. Chunk text
    3. Embed chunks in batches
    4. Store embeddings in DB
    """
    return asyncio.run(_process_document_async(doc_id, tenant_id))


async def _process_document_async(doc_id: str, tenant_id: str) -> dict:
    session_factory, engine = _make_session_factory()
    try:
        async with session_factory() as db:
            try:
                result = await db.execute(
                    select(Document).where(
                        Document.id == uuid.UUID(doc_id),
                        Document.tenant_id == uuid.UUID(tenant_id),
                    )
                )
                doc = result.scalar_one_or_none()
                if not doc:
                    return {"error": "Document not found"}

                tenant_result = await db.execute(
                    select(Tenant).where(Tenant.id == uuid.UUID(tenant_id))
                )
                tenant = tenant_result.scalar_one_or_none()
                api_key = (tenant.embedding_api_key or tenant.llm_api_key) if tenant else None
                emb_model = tenant.embedding_model if tenant else "ollama:nomic-embed-text"

                doc.status = "processing"
                doc.updated_at = datetime.now(timezone.utc)
                await db.commit()

                # 1. Parse
                raw_text = parse_document(doc.file_path, doc.mime_type)
                if not raw_text.strip():
                    doc.status = "error"
                    doc.error_message = "No text content found in document"
                    await db.commit()
                    return {"error": "Empty document"}

                # 2. Chunk
                chunks = chunk_text(raw_text)
                if not chunks:
                    doc.status = "error"
                    doc.error_message = "Failed to create chunks"
                    await db.commit()
                    return {"error": "No chunks"}

                # 3. Embed
                embeddings, total_tokens = await embed_texts(chunks, api_key=api_key, embedding_model=emb_model)

                # 4. Store
                for i, (chunk_content, embedding) in enumerate(zip(chunks, embeddings)):
                    embedding_str = "[" + ",".join(map(str, embedding)) + "]"
                    await db.execute(
                        text("""
                            INSERT INTO document_chunks
                                (id, tenant_id, document_id, content, chunk_index, embedding, token_count, created_at)
                            VALUES
                                (:id, :tenant_id, :document_id, :content, :chunk_index, CAST(:embedding AS vector), :token_count, now())
                        """),
                        {
                            "id": str(uuid.uuid4()),
                            "tenant_id": tenant_id,
                            "document_id": doc_id,
                            "content": chunk_content,
                            "chunk_index": i,
                            "embedding": embedding_str,
                            "token_count": len(chunk_content.split()),
                        },
                    )

                doc.status = "done"
                doc.chunk_count = len(chunks)
                doc.updated_at = datetime.now(timezone.utc)
                await db.commit()

                return {
                    "doc_id": doc_id,
                    "status": "done",
                    "chunks": len(chunks),
                    "tokens": total_tokens,
                }

            except Exception as exc:
                await db.rollback()
                async with session_factory() as error_db:
                    result = await error_db.execute(
                        select(Document).where(Document.id == uuid.UUID(doc_id))
                    )
                    doc = result.scalar_one_or_none()
                    if doc:
                        doc.status = "error"
                        doc.error_message = str(exc)[:500]
                        await error_db.commit()
                raise
    finally:
        await engine.dispose()
