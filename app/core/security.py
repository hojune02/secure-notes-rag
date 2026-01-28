from datetime import datetime, timedelta, timezone
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import jwt, JWTError

from app.core.config import settings


# Argon2id is the default in argon2-cffi PasswordHasher (good default)
_pwd_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _pwd_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _pwd_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def create_access_token(*, subject: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": subject,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    # Raises JWTError if invalid/expired
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
