"""Admin API: conversation history, usage stats, Ollama model management."""
import asyncio
import uuid
from datetime import date
from typing import Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.dependencies import get_current_admin
from app.core.dependencies import get_current_user
from app.db.database import get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.schemas.chat import ConversationSummary, MessageDetail

router = APIRouter(prefix="/admin", tags=["admin"])
settings = get_settings()


# ── Ollama model management ────────────────────────────────────

@router.get("/ollama/models")
async def list_ollama_models(
    current_user: User = Depends(get_current_admin),
) -> dict:
    """List models currently available in Ollama."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{settings.ollama_url}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            names = [m["name"] for m in data.get("models", [])]
            return {"models": names}
    except Exception:
        return {"models": []}


@router.post("/ollama/pull")
async def pull_ollama_model(
    body: dict,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_admin),
) -> dict:
    """Start pulling an Ollama model in the background."""
    model = body.get("model", "").strip()
    if not model:
        raise HTTPException(status_code=400, detail="model is required")
    # Validate: only allow ollama model names (alphanumeric, colon, dash, dot)
    import re
    if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9:._-]{0,99}$', model):
        raise HTTPException(status_code=400, detail="Invalid model name")

    background_tasks.add_task(_pull_model_bg, model)
    return {"status": "pulling", "model": model}


async def _pull_model_bg(model: str) -> None:
    """Background task: call Ollama pull API (stream=false, long timeout)."""
    try:
        async with httpx.AsyncClient(timeout=600) as client:
            await client.post(
                f"{settings.ollama_url}/api/pull",
                json={"name": model, "stream": False},
            )
    except Exception:
        pass  # Errors are non-fatal; frontend polls model list to check status


@router.post("/models/fetch")
async def fetch_provider_models(
    body: dict,
    current_user: User = Depends(get_current_admin),
) -> dict:
    """
    Fetch available models from a provider.
    provider: ollama | openai | gemini | anthropic
    api_key: optional, required for cloud providers
    """
    provider = body.get("provider", "").strip()
    api_key = body.get("api_key", "").strip()

    if provider == "ollama":
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{settings.ollama_url}/api/tags")
                resp.raise_for_status()
                models = [
                    {"id": m["name"], "size_gb": round(m.get("size", 0) / 1e9, 1)}
                    for m in resp.json().get("models", [])
                ]
                return {"models": models}
        except Exception:
            return {"models": [], "error": "Ollama niedostępny"}

    if provider == "openai":
        if not api_key.startswith("sk-"):
            raise HTTPException(400, "Wymagany klucz OpenAI (sk-...)")
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                resp.raise_for_status()
                models = sorted(
                    [{"id": m["id"]} for m in resp.json()["data"]
                     if "gpt" in m["id"] and "instruct" not in m["id"]],
                    key=lambda x: x["id"], reverse=True,
                )
                return {"models": models}
        except httpx.HTTPStatusError as e:
            raise HTTPException(400, f"OpenAI API error: {e.response.status_code}")

    if provider == "gemini":
        if not api_key:
            raise HTTPException(400, "Wymagany klucz Google API (AIza...)")
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://generativelanguage.googleapis.com/v1beta/models",
                    params={"key": api_key},
                )
                resp.raise_for_status()
                models = [
                    {"id": m["name"].replace("models/", "")}
                    for m in resp.json().get("models", [])
                    if "gemini" in m.get("name", "")
                    and "generateContent" in m.get("supportedGenerationMethods", [])
                ]
                return {"models": models}
        except httpx.HTTPStatusError as e:
            raise HTTPException(400, f"Google API error: {e.response.status_code}")

    if provider == "anthropic":
        # Anthropic has no public models-list endpoint — return known models
        return {"models": [
            {"id": "claude-opus-4-5"},
            {"id": "claude-sonnet-4-5"},
            {"id": "claude-haiku-4-5-20251001"},
            {"id": "claude-3-5-sonnet-20241022"},
            {"id": "claude-3-5-haiku-20241022"},
            {"id": "claude-3-opus-20240229"},
        ]}

    raise HTTPException(400, "Unknown provider")


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    tenant_id: Optional[uuid.UUID] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationSummary]:
    """
    List conversations.
    - Superadmin: can filter by any tenant_id
    - Tenant admin: sees only own tenant's conversations
    """
    # Determine tenant scope
    if current_user.is_superadmin:
        effective_tenant_id = tenant_id
    else:
        if not current_user.tenant_id:
            raise HTTPException(status_code=403, detail="No tenant assigned")
        effective_tenant_id = current_user.tenant_id
        # Tenant admin cannot query other tenants
        if tenant_id and tenant_id != effective_tenant_id:
            raise HTTPException(status_code=403, detail="Access denied")

    # Count messages per conversation (subquery)
    msg_count_sq = (
        select(Message.conversation_id, func.count(Message.id).label("message_count"))
        .group_by(Message.conversation_id)
        .subquery()
    )

    query = select(
        Conversation,
        func.coalesce(msg_count_sq.c.message_count, 0).label("message_count"),
    ).outerjoin(msg_count_sq, msg_count_sq.c.conversation_id == Conversation.id)

    if effective_tenant_id:
        query = query.where(Conversation.tenant_id == effective_tenant_id)

    if date_from:
        query = query.where(Conversation.started_at >= date_from)
    if date_to:
        query = query.where(Conversation.started_at <= date_to)

    query = query.order_by(Conversation.last_message_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    rows = result.all()

    summaries = []
    for row in rows:
        conv = row[0]
        msg_count = row[1]
        summaries.append(ConversationSummary(
            id=conv.id,
            session_id=conv.session_id,
            started_at=conv.started_at,
            last_message_at=conv.last_message_at,
            message_count=msg_count,
            user_ip_hash=conv.user_ip_hash,
        ))
    return summaries


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a conversation and all its messages. Admin: own tenant only. Superadmin: any."""
    from sqlalchemy import delete as sa_delete
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if not current_user.is_superadmin and current_user.tenant_id != conv.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    await db.delete(conv)
    await db.commit()


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageDetail])
async def get_conversation_messages(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MessageDetail]:
    """Get all messages in a conversation thread."""
    # Verify access
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if not current_user.is_superadmin and current_user.tenant_id != conv.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    messages = result.scalars().all()
    return [MessageDetail.model_validate(m) for m in messages]
