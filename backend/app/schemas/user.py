import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


ALLOWED_ROLES = {"superadmin", "admin", "user"}
CREATABLE_ROLES = {"admin", "user"}  # regular admins can't create superadmins


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field(default="user")
    tenant_id: uuid.UUID | None = None
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)

    def model_post_init(self, __context) -> None:
        if self.role not in ALLOWED_ROLES:
            raise ValueError(f"Invalid role: {self.role}. Must be one of {ALLOWED_ROLES}")


class UserUpdate(BaseModel):
    role: str | None = None
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None

    def model_post_init(self, __context) -> None:
        if self.role is not None and self.role not in ALLOWED_ROLES:
            raise ValueError(f"Invalid role: {self.role}")


class PasswordChangeRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    first_name: str | None
    last_name: str | None
    tenant_id: uuid.UUID | None
    is_active: bool
    full_name: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
