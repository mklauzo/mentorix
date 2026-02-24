"""User management API – CRUD with role-based access control."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_current_admin, get_current_superadmin
from app.core.security import hash_password
from app.db.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserResponse, PasswordChangeRequest, CREATABLE_ROLES

router = APIRouter(prefix="/users", tags=["users"])


def _check_target_access(actor: User, target: User) -> None:
    """Raise 403 if actor is not allowed to modify/delete target."""
    # Cannot act on yourself (for delete)
    if actor.id == target.id:
        raise HTTPException(status_code=400, detail="Cannot perform this action on yourself")
    # Admin cannot modify superadmin or another admin
    if actor.role == "admin" and target.role in ("superadmin", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins can only manage 'user' role accounts",
        )
    # Admin can only manage users in own tenant
    if actor.role == "admin" and target.tenant_id != actor.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


@router.get("", response_model=list[UserResponse])
async def list_users(
    role: str | None = Query(None, description="Filter by role"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> list[UserResponse]:
    query = select(User)

    if current_user.is_role_superadmin():
        # Superadmin sees all users
        if role:
            query = query.where(User.role == role)
    else:
        # Admin sees only users in own tenant
        query = query.where(User.tenant_id == current_user.tenant_id)
        if role:
            query = query.where(User.role == role)

    query = query.order_by(User.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    users = result.scalars().all()
    return [UserResponse.model_validate(u) for u in users]


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    body: UserCreate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    # Validate role permissions
    if body.role == "superadmin":
        raise HTTPException(status_code=403, detail="Cannot create superadmin via this endpoint")

    if current_user.role == "admin":
        # Admin can only create users in own tenant
        if body.role not in CREATABLE_ROLES:
            raise HTTPException(status_code=403, detail="Admins can only create 'admin' or 'user' roles")
        # Force tenant_id to admin's tenant
        effective_tenant_id = current_user.tenant_id
    else:
        # Superadmin: use provided tenant_id
        effective_tenant_id = body.tenant_id

    # Check email uniqueness
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        role=body.role,
        tenant_id=effective_tenant_id,
        first_name=body.first_name,
        last_name=body.last_name,
        is_superadmin=(body.role == "superadmin"),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # Access check (don't use _check_target_access – it blocks self)
    if not current_user.is_role_superadmin() and target.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return UserResponse.model_validate(target)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if current_user.id != target.id:
        _check_target_access(current_user, target)

    # Prevent role promotion to superadmin by non-superadmin
    if body.role == "superadmin" and not current_user.is_role_superadmin():
        raise HTTPException(status_code=403, detail="Only superadmin can grant superadmin role")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(target, field, value)

    # Keep legacy is_superadmin in sync
    if body.role is not None:
        target.is_superadmin = (body.role == "superadmin")

    await db.flush()
    await db.refresh(target)
    return UserResponse.model_validate(target)


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # Self-delete check
    if current_user.id == target.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    _check_target_access(current_user, target)
    await db.delete(target)


@router.post("/{user_id}/set-password", status_code=200)
async def set_user_password(
    user_id: uuid.UUID,
    body: PasswordChangeRequest,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if current_user.id != target.id:
        _check_target_access(current_user, target)

    target.hashed_password = hash_password(body.new_password)
    target.failed_login_attempts = 0
    target.locked_until = None
    return {"message": "Password updated"}
