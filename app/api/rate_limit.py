from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.rate_limiter import check_rate_limit
from app.models.user import User


def get_client_ip(request: Request) -> str:
    # In production behind a reverse proxy, you'd use X-Forwarded-For carefully.
    # For local dev, client.host is fine.
    return request.client.host if request.client else "unknown"


def rate_limit_ip(prefix: str, limit: int, window_seconds: int):
    """
    Dependency factory: rate limit per client IP.
    Usage: Depends(rate_limit_ip("login", 5, 60))
    """
    def _dep(request: Request):
        ip = get_client_ip(request)
        res = check_rate_limit(prefix=prefix, identifier=ip, limit=limit, window_seconds=window_seconds)
        if not res.allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests",
                headers={"Retry-After": str(res.retry_after)},
            )
        return res
    return _dep


def rate_limit_user(prefix: str, limit: int, window_seconds: int):
    """
    Dependency factory: rate limit per authenticated user.
    Usage: Depends(rate_limit_user("notes", 60, 60))
    """
    def _dep(current_user: User = Depends(get_current_user)):
        res = check_rate_limit(prefix=prefix, identifier=str(current_user.id), limit=limit, window_seconds=window_seconds)
        if not res.allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests",
                headers={"Retry-After": str(res.retry_after)},
            )
        return res
    return _dep
