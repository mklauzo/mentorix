"""Tenant (Profile) management API.

Role access:
  superadmin – full CRUD on all tenants
  admin      – GET/PATCH their own tenant only; cannot create/delete tenants
  user       – GET their own tenant only (read-only)
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_current_superadmin, require_tenant_access
from app.db.database import get_db
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.tenant import TenantCreate, TenantUpdate, TenantResponse

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("", response_model=list[TenantResponse])
async def list_tenants(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TenantResponse]:
    """
    Superadmin: all tenants.
    Admin/user: returns only their own tenant (as a list of 1).
    """
    if current_user.is_role_superadmin():
        result = await db.execute(select(Tenant).order_by(Tenant.created_at.desc()))
        tenants = result.scalars().all()
    elif current_user.tenant_id:
        result = await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))
        tenants = result.scalars().all()
    else:
        tenants = []
    return [TenantResponse.model_validate(t) for t in tenants]


@router.post("", response_model=TenantResponse, status_code=201)
async def create_tenant(
    body: TenantCreate,
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
) -> TenantResponse:
    """Only superadmin can create new profiles."""
    existing = await db.execute(select(Tenant).where(Tenant.slug == body.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Slug already taken")

    tenant = Tenant(**body.model_dump())
    db.add(tenant)
    await db.flush()
    await db.refresh(tenant)
    return TenantResponse.model_validate(tenant)


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: uuid.UUID,
    tenant: Tenant = Depends(require_tenant_access),
) -> TenantResponse:
    return TenantResponse.model_validate(tenant)


@router.patch("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: uuid.UUID,
    body: TenantUpdate,
    tenant: Tenant = Depends(require_tenant_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TenantResponse:
    """Superadmin: any field. Admin: limited (no is_blocked/is_active by non-superadmin)."""
    update_data = body.model_dump(exclude_unset=True)

    # Non-superadmin cannot block/unblock a tenant
    if not current_user.is_role_superadmin():
        update_data.pop("is_blocked", None)
        update_data.pop("blocked_reason", None)

    for field, value in update_data.items():
        setattr(tenant, field, value)

    await db.flush()
    await db.refresh(tenant)
    return TenantResponse.model_validate(tenant)


@router.delete("/{tenant_id}", status_code=204)
async def delete_tenant(
    tenant_id: uuid.UUID,
    current_user: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Only superadmin can delete profiles."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    await db.delete(tenant)
