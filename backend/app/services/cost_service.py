"""Cost tracking and limit enforcement."""
from datetime import date, datetime, timezone
from decimal import Decimal
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant
from app.models.api_usage import ApiUsage

# Pricing per 1M tokens (USD)
PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "text-embedding-3-small": {"input": 0.02, "output": 0.0},
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int = 0) -> Decimal:
    pricing = PRICING.get(model, PRICING["gpt-4o-mini"])
    cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
    return Decimal(str(round(cost, 6)))


async def check_and_increment_usage(
    tenant_id: uuid.UUID,
    estimated_tokens: int,
    db: AsyncSession,
) -> Tenant:
    """
    SELECT FOR UPDATE tenant, reset counters if needed, check limits, increment.
    Raises HTTP 429 if limits exceeded.
    """
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id).with_for_update()
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if not tenant.is_active or tenant.is_blocked:
        raise HTTPException(status_code=403, detail="Tenant is blocked or inactive")

    today = date.today()
    current_month = today.month

    # Reset daily counter
    if tenant.last_reset_daily != today:
        tenant.tokens_used_day = 0
        tenant.last_reset_daily = today

    # Reset monthly counter
    if tenant.last_reset_monthly != current_month:
        tenant.tokens_used_month = 0
        tenant.last_reset_monthly = current_month

    # Check limits
    if tenant.tokens_used_day + estimated_tokens > tenant.daily_token_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily token limit exceeded ({tenant.daily_token_limit:,} tokens/day)",
        )
    if tenant.tokens_used_month + estimated_tokens > tenant.monthly_token_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Monthly token limit exceeded ({tenant.monthly_token_limit:,} tokens/month)",
        )

    # Increment
    tenant.tokens_used_day += estimated_tokens
    tenant.tokens_used_month += estimated_tokens

    return tenant


async def update_usage_after_call(
    tenant_id: uuid.UUID,
    model: str,
    input_tokens: int,
    output_tokens: int,
    embedding_tokens: int,
    db: AsyncSession,
) -> None:
    """Upsert api_usage record for today."""
    today = date.today()
    cost = estimate_cost(model, input_tokens, output_tokens) + estimate_cost(
        "text-embedding-3-small", embedding_tokens
    )

    stmt = pg_insert(ApiUsage).values(
        tenant_id=tenant_id,
        date=today,
        embedding_tokens=embedding_tokens,
        chat_tokens_input=input_tokens,
        chat_tokens_output=output_tokens,
        cost_usd=cost,
        total_queries=1,
    ).on_conflict_do_update(
        index_elements=["tenant_id", "date"],
        set_={
            "embedding_tokens": ApiUsage.embedding_tokens + embedding_tokens,
            "chat_tokens_input": ApiUsage.chat_tokens_input + input_tokens,
            "chat_tokens_output": ApiUsage.chat_tokens_output + output_tokens,
            "cost_usd": ApiUsage.cost_usd + cost,
            "total_queries": ApiUsage.total_queries + 1,
            "updated_at": datetime.now(timezone.utc),
        },
    )
    await db.execute(stmt)
