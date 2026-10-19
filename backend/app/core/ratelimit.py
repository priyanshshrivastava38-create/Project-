"""In-process login throttling (failed attempts per account+IP and per IP, sliding window).

State lives in process memory, so limits are per worker. That is adequate for the single-worker
deployment in render.yaml; for several workers/instances put a shared limiter (proxy or Redis) in front.
"""

import threading
import time
from collections import deque

from app.core.config import get_settings
from app.core.errors import RateLimitedError


class FailureLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float, window: float) -> deque[float]:
        q = self._hits.setdefault(key, deque())
        while q and q[0] <= now - window:
            q.popleft()
        return q

    def check(self, keys: list[tuple[str, int]], window: float) -> None:
        """Raise RateLimitedError if any key already has `limit` failures inside the window."""
        now = time.monotonic()
        with self._lock:
            for key, limit in keys:
                q = self._recent(key, now, window)
                if len(q) >= limit:
                    retry_after = int(q[0] + window - now) + 1
                    raise RateLimitedError(
                        "Too many failed sign-in attempts. Try again later.", details={"retry_after_seconds": retry_after}
                    )

    def fail(self, keys: list[str]) -> None:
        now = time.monotonic()
        with self._lock:
            for key in keys:
                self._hits.setdefault(key, deque()).append(now)
            if len(self._hits) > 10_000:  # bound memory: drop keys with no recent failures
                window = get_settings().login_rate_window_seconds
                for k in [k for k, q in self._hits.items() if not q or q[-1] <= now - window]:
                    del self._hits[k]

    def clear(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


login_limiter = FailureLimiter()
