import time
from dataclasses import dataclass
from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings


def get_redis() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after: int  # seconds until reset


def _window_key(prefix: str, identifier: str, window_seconds: int) -> tuple[str, int]:
    """
    Fixed-window key: key includes the current window number.
    """
    now = int(time.time())
    window = now // window_seconds
    reset_at = (window + 1) * window_seconds
    retry_after = max(0, reset_at - now)
    key = f"rl:{prefix}:{identifier}:{window}"
    return key, retry_after


def check_rate_limit(prefix: str, identifier: str, limit: int, window_seconds: int) -> RateLimitResult:
    """
    Fixed window: INCR a key for this identifier+window, EXPIRE it to window_seconds.
    If count > limit => blocked.
    """
    _redis = get_redis()
    
    key, retry_after = _window_key(prefix, identifier, window_seconds)

    try:
        pipe = _redis.pipeline()
        pipe.incr(key, 1)
        pipe.expire(key, window_seconds)
        count, _ = pipe.execute()

        remaining = max(0, limit - int(count))
        allowed = int(count) <= limit
        return RateLimitResult(allowed=allowed, remaining=remaining, retry_after=retry_after)

    except RedisError:
        # Fail-open vs fail-closed decision:
        # For availability, we fail-open (allow) if Redis is down.
        # In some environments you may choose fail-closed for auth endpoints.
        return RateLimitResult(allowed=True, remaining=limit, retry_after=0)
