from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.security import hash_password, verify_password, create_access_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, MeResponse

from app.api.deps import get_current_user
from app.api.rate_limit import rate_limit_ip

from app.services.audit import audit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=MeResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(rate_limit_ip("register", 3, 60))])
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    email = payload.email.lower()

    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    # Basic password policy. Keep it simple today.
    if len(payload.password) < 10:
        raise HTTPException(status_code=400, detail="Password too short")

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        role="user",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(rate_limit_ip("login", 3, 60))])
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    email = payload.email.lower()

    user = db.scalar(select(User).where(User.email == email))
    # Prevent user enumeration: return same error for missing user or wrong password
    if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    audit(db, user.id, "auth.login", {"role": user.role})
    
    token = create_access_token(subject=str(user.id), role=user.role)
    return TokenResponse(access_token=token, expires_in=15 * 60)


@router.get("/me", response_model=MeResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user
