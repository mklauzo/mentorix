"""Auth endpoints: login, me, register-superadmin."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.core.security import hash_password, verify_password, create_access_token
from app.core.dependencies import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserResponse
from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    def _raise_invalid():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user or not user.is_active:
        _raise_invalid()

    # Check account lockout
    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account locked until {user.locked_until.isoformat()}",
        )

    if not verify_password(body.password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.max_failed_login_attempts:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=settings.lockout_minutes)
            user.failed_login_attempts = 0
        await db.commit()
        _raise_invalid()

    # Successful login – reset brute-force counters
    user.failed_login_attempts = 0
    user.locked_until = None
    await db.commit()

    token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "is_superadmin": user.is_role_superadmin(),
        "tenant_id": str(user.tenant_id) if user.tenant_id else None,
    })

    return TokenResponse(
        access_token=token,
        user_id=str(user.id),
        role=user.role,
        is_superadmin=user.is_role_superadmin(),
        tenant_id=str(user.tenant_id) if user.tenant_id else None,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return the currently authenticated user's profile."""
    return UserResponse.model_validate(current_user)


@router.post("/register-superadmin", include_in_schema=False)
async def register_superadmin(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """One-time endpoint to create superadmin. Disable in production after first use."""
    existing = await db.execute(select(User).where(User.role == "superadmin"))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Superadmin already exists")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        role="superadmin",
        is_superadmin=True,
    )
    db.add(user)
    await db.commit()
    return {"message": "Superadmin created", "email": body.email}
