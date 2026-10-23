"""In-memory sliding-window rate limiter.

Suitable for a single application instance (the Render free tier runs one). A multi-instance
deployment would need a shared store such as Redis.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from app.core.errors import AppError


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, bucket: str, key: str, limit: int, window_seconds: int = 3600) -> None:
        now = time.monotonic()
        name = f"{bucket}:{key}"
        with self._lock:
            hits = self._hits[name]
            while hits and now - hits[0] > window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                retry = int(window_seconds - (now - hits[0])) + 1
                raise AppError(
                    429,
                    "rate_limited",
                    f"Too many requests for this action. Please try again in about {max(1, retry // 60)} minute(s).",
                )
            hits.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()
