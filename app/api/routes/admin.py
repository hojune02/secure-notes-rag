from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.deps import require_admin, get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.admin import UserAdminOut, UserAdminUpdate

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=dict, dependencies=[Depends(require_admin)])
def list_users(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be >= 0")

    users = db.scalars(
        select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    ).all()

    return {
        "items": [UserAdminOut.model_validate(u).model_dump() for u in users],
        "limit": limit,
        "offset": offset,
        "total": len(users),  # simple for now; can compute exact count later
    }


@router.patch("/users/{user_id}", response_model=UserAdminOut)
def update_user(
    user_id: UUID,
    payload: UserAdminUpdate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    # Safety: prevent admin from disabling themselves (common guardrail)
    if user.id == admin_user.id and payload.is_active is False:
        raise HTTPException(status_code=400, detail="cannot disable your own account")

    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.email is not None:
        user.email = payload.email

    db.add(user)
    db.commit()
    db.refresh(user)
    return user
