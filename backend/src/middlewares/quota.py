"""Cross-cutting limits: Redis sliding-window rate limit + per-role daily quota.

* ``RateLimitMiddleware``: every write request passes a per-user sliding window
  (``RATE_WINDOW_SECONDS`` / ``RATE_WINDOW_MAX``); overflow → 429 with
  ``retry_after``. Falls back to an in-process window when Redis is down.
* ``consume_daily_quota``: called by controllers before a sample-job run or a
  backfill run; consumes ``users.daily_quota`` (viewer has 0 by policy).
"""
import time
from datetime import date

from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from src.config.settings import settings
from src.constants.enums import Role
from src.constants.error_codes import AppError, ErrorCode
from src.models import User
from src.utils.logger import log_event

_client = None
_mem_window: dict[str, list[float]] = {}
_init_attempted = False


def get_redis():
    global _client, _init_attempted
    if _client is not None:
        return _client
    if _init_attempted:
        return None
    _init_attempted = True
    try:
        import redis

        client = redis.Redis.from_url(
            settings.REDIS_URL, socket_timeout=0.4, socket_connect_timeout=0.4, decode_responses=True
        )
        client.ping()
        _client = client
    except Exception:
        _client = None
    return _client


def rate_limit_allow(user_id: int) -> bool:
    window = settings.RATE_WINDOW_SECONDS
    max_hits = settings.RATE_WINDOW_MAX
    now = time.time()
    key = f"rl:featpoint:{user_id}"
    client = get_redis()
    if client is not None:
        try:
            pipe = client.pipeline()
            pipe.zremrangebyscore(key, 0, now - window)
            pipe.zadd(key, {f"{now:.6f}": now})
            pipe.zcard(key)
            pipe.expire(key, window)
            _, _, count, _ = pipe.execute()
            return int(count) <= max_hits
        except Exception:
            pass
    hits = [t for t in _mem_window.get(key, []) if t > now - window]
    hits.append(now)
    _mem_window[key] = hits
    return len(hits) <= max_hits


def quota_snapshot(user: User) -> dict:
    quota = int(user.daily_quota or 0)
    used = int(user.quota_used or 0)
    return {
        "daily_quota": quota,
        "quota_used": used,
        "quota_remaining": max(0, quota - used),
        "rate_window_seconds": settings.RATE_WINDOW_SECONDS,
        "rate_window_max": settings.RATE_WINDOW_MAX,
    }


def consume_daily_quota(db: Session, user: User, action: str) -> dict:
    today = date.today()
    if user.quota_date != today:
        user.quota_date = today
        user.quota_used = 0
    if user.role == Role.VIEWER.value:
        raise AppError(
            ErrorCode.FORBIDDEN,
            message="只读角色（viewer）不能消耗计算资源",
            detail={"role": user.role, "action": action},
        )
    if user.quota_used >= int(user.daily_quota or 0):
        log_event("AUDIT_QUOTA_REJECTED", user=user.email, action=action, used=user.quota_used)
        raise AppError(
            ErrorCode.QUOTA_EXHAUSTED,
            detail={"quota": user.daily_quota, "used": user.quota_used},
        )
    user.quota_used += 1
    db.commit()
    return quota_snapshot(user)


class RateLimitMiddleware(BaseHTTPMiddleware):
    WRITE_METHODS = {"POST", "PATCH", "PUT", "DELETE"}

    async def dispatch(self, request, call_next):
        if request.method in self.WRITE_METHODS:
            claims = getattr(request.state, "user_claims", None) or {}
            user_id = claims.get("sub")
            if user_id and not rate_limit_allow(int(user_id)):
                from starlette.responses import JSONResponse

                from src.schemas.common import error_envelope

                return JSONResponse(
                    status_code=429,
                    content=error_envelope(
                        ErrorCode.RATE_LIMITED.value,
                        "请求过于频繁",
                        getattr(request.state, "request_id", None),
                        {"retry_after": settings.RATE_WINDOW_SECONDS},
                    ),
                )
        return await call_next(request)
