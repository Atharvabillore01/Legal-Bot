"""
FastAPI dependency injection helpers.

Provides:
  - get_current_user: Extracts & validates JWT, returns User ORM object
  - RateLimiter: Simple in-memory rate limiter (replace with Redis for production)
"""

import time
import threading
from collections import defaultdict, deque
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .auth import decode_access_token, get_user_by_id
from .database import User, get_db

bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Extract user from Bearer JWT. Raises 401 if invalid or user not found."""
    payload = decode_access_token(credentials.credentials)
    user_id: str = payload.get("user_id", "")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deactivated")
    return user


# ─── In-memory rate limiter ───────────────────────────────────────────────────

class _RateLimiter:
    """
    Token-bucket style rate limiter stored in memory.
    Not distributed — use Redis in multi-process deployments.
    """

    def __init__(self):
        self._windows: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def is_allowed(self, key: str, max_calls: int, window_seconds: int) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            dq = self._windows[key]
            while dq and dq[0] < cutoff:
                dq.popleft()
            if len(dq) >= max_calls:
                return False
            dq.append(now)
            return True


_rate_limiter = _RateLimiter()


def rate_limit(max_calls: int = 60, window_seconds: int = 60):
    """
    FastAPI dependency factory for rate limiting.

    Usage:
        @router.post("/query")
        async def query(request: Request, _=Depends(rate_limit(10, 60))):
            ...
    """
    async def _check(request: Request, user: User = Depends(get_current_user)):
        key = f"{user.id}:{request.url.path}"
        if not _rate_limiter.is_allowed(key, max_calls, window_seconds):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: {max_calls} requests per {window_seconds}s",
            )
        return user

    return _check
