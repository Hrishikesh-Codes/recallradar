"""In-process sliding-window rate limits.

The API runs as a single instance (one container on one VM), so per-process counters are exact
and need no Redis. If it ever runs as several instances, each enforces its own limit.
"""

import threading
import time
from collections import OrderedDict, deque

from fastapi import HTTPException, Request, status


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float, max_keys: int = 10_000) -> None:
        self.limit = limit
        self.window = window_seconds
        self.max_keys = max_keys
        self._hits: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        with self._lock:
            hits = self._hits.pop(key, None) or deque()
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            allowed = len(hits) < self.limit
            if allowed:
                hits.append(now)
            self._hits[key] = hits  # most recently used last
            while len(self._hits) > self.max_keys:
                self._hits.popitem(last=False)
            return allowed

    def retry_after(self, key: str, now: float | None = None) -> int:
        now = time.monotonic() if now is None else now
        with self._lock:
            hits = self._hits.get(key)
            if not hits:
                return 0
            return max(1, round(hits[0] + self.window - now))


def client_key(request: Request) -> str:
    # Behind Caddy, uvicorn's --proxy-headers sets this from X-Forwarded-For, which it trusts only
    # from FORWARDED_ALLOW_IPS (the compose network), so clients can't choose their own address.
    return request.client.host if request.client else "unknown"


def enforce(limiters: list[RateLimiter], key: str) -> None:
    for limiter in limiters:
        if not limiter.allow(key):
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many checks from your network. Please wait a moment and try again.",
                headers={"Retry-After": str(limiter.retry_after(key))},
            )
