"""Chat API: public chat endpoint + config."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.prompt_guard import check_prompt_injection
from app.core.rate_limit import limiter
from app.core.security import hash_ip
from app.db.database import get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.tenant import Tenant
from app.schemas.chat import ChatMessageRequest, ChatMessageResponse
from app.schemas.tenant import ChatConfig
from app.services.cost_service import check_and_increment_usage, update_usage_after_call, estimate_cost
from app.services.rag_service import run_rag_pipeline

router = APIRouter(prefix="/chat", tags=["chat"])

ESTIMATED_TOKENS_PER_QUERY = 1500  # conservative estimate for limit check


@router.get("/{tenant_id}/config", response_model=ChatConfig)
async def get_chat_config(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ChatConfig:
    """Public endpoint: returns chat branding + welcome message."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Chat not found")
    if not tenant.is_active or tenant.is_blocked:
        raise HTTPException(status_code=403, detail="Chat unavailable")

    return ChatConfig(
        chat_title=tenant.chat_title,
        chat_color=tenant.chat_color,
        welcome_message=tenant.welcome_message,
        is_active=tenant.is_active,
        chat_logo_url=tenant.chat_logo_url,
    )


@router.post("/{tenant_id}/message", response_model=ChatMessageResponse)
@limiter.limit("10/minute")
async def send_message(
    request: Request,
    tenant_id: uuid.UUID,
    body: ChatMessageRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatMessageResponse:
    """
    Main chat endpoint:
    1. Validate tenant
    2. Guard prompt injection
    3. Check token limits
    4. Run RAG pipeline
    5. Persist conversation & message
    6. Update usage stats
    """
    # 1. Validate tenant
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant or not tenant.is_active or tenant.is_blocked:
        raise HTTPException(status_code=403, detail="Chat unavailable")

    # 2. Guard prompt injection
    guard = check_prompt_injection(body.question)
    if not guard.is_safe:
        # Still record the flagged message
        await _persist_flagged_message(tenant_id, body, request, db)
        raise HTTPException(status_code=400, detail=guard.reason)

    # 3. Check and increment token usage
    await check_and_increment_usage(tenant_id, ESTIMATED_TOKENS_PER_QUERY, db)
    await db.commit()

    # 4. Run RAG
    rag_result = await run_rag_pipeline(body.question, tenant, db)

    # 5. Persist conversation & messages
    conversation = await _get_or_create_conversation(tenant_id, body.session_id, request, db)

    # User message
    user_msg = Message(
        conversation_id=conversation.id,
        tenant_id=tenant_id,
        role="user",
        content=body.question,
        flagged_injection=False,
    )
    db.add(user_msg)

    # Assistant message
    total_tokens = rag_result["total_tokens"]
    cost = estimate_cost(tenant.llm_model, rag_result["input_tokens"], rag_result["output_tokens"])
    assistant_msg = Message(
        conversation_id=conversation.id,
        tenant_id=tenant_id,
        role="assistant",
        content=rag_result["answer"],
        total_tokens=total_tokens,
        estimated_cost_usd=cost,
        retrieved_chunk_ids=rag_result["chunk_ids"] or None,
    )
    db.add(assistant_msg)

    # Update conversation timestamp
    conversation.last_message_at = datetime.now(timezone.utc)

    # 6. Update usage stats
    await update_usage_after_call(
        tenant_id=tenant_id,
        model=tenant.llm_model,
        input_tokens=rag_result["input_tokens"],
        output_tokens=rag_result["output_tokens"],
        embedding_tokens=0,  # embedding cost tracked separately in embedding service
        db=db,
    )

    await db.commit()

    return ChatMessageResponse(
        answer=rag_result["answer"],
        conversation_id=conversation.id,
        sources=rag_result["sources"],
        tokens_used=total_tokens,
        estimated_cost_usd=float(cost),
    )


async def _get_or_create_conversation(
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    request: Request,
    db: AsyncSession,
) -> Conversation:
    result = await db.execute(
        select(Conversation).where(
            Conversation.tenant_id == tenant_id,
            Conversation.session_id == session_id,
        )
    )
    conv = result.scalar_one_or_none()
    if conv:
        return conv

    # Hash IP for privacy
    client_ip = request.client.host if request.client else "unknown"
    ip_hash = hash_ip(client_ip)
    user_agent = request.headers.get("user-agent", "")[:500]

    conv = Conversation(
        tenant_id=tenant_id,
        session_id=session_id,
        user_ip_hash=ip_hash,
        user_agent=user_agent,
    )
    db.add(conv)
    await db.flush()
    return conv


async def _persist_flagged_message(
    tenant_id: uuid.UUID,
    body: ChatMessageRequest,
    request: Request,
    db: AsyncSession,
) -> None:
    conv = await _get_or_create_conversation(tenant_id, body.session_id, request, db)
    msg = Message(
        conversation_id=conv.id,
        tenant_id=tenant_id,
        role="user",
        content=body.question[:2000],
        flagged_injection=True,
    )
    db.add(msg)
    await db.commit()
