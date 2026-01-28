# Admin can view all the users, update users' info such as is_active and role. We prevent admin from disabling themselves.
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


class UserAdminOut(BaseModel):
    id: UUID
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserAdminUpdate(BaseModel):
    role: str | None = Field(default=None, pattern="^(user|admin)$")
    is_active: bool | None = None
    email: EmailStr | None = None
