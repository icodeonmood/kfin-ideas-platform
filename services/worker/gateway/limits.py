"""Rate control (§3.2 step 5): per model tier, a concurrency cap and a requests-per-minute token bucket, in
this worker process. A call that cannot start within its wait limit is refused (`RateLimited`) so the caller
queues it as a job instead of holding a person's scan."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

from core.config import get_settings


class Saturated(Exception):
    pass


class _Bucket:
    def __init__(self, per_minute: int):
        self.capacity = float(per_minute)
        self.tokens = float(per_minute)
        self.rate = per_minute / 60.0
        self.at = time.monotonic()
        self.lock = threading.Lock()

    def take(self) -> float:
        """0 if a token was taken, else seconds until one is available."""
        with self.lock:
            now = time.monotonic()
            self.tokens = min(self.capacity, self.tokens + (now - self.at) * self.rate)
            self.at = now
            if self.tokens >= 1:
                self.tokens -= 1
                return 0.0
            return (1 - self.tokens) / self.rate


class Limiter:
    def __init__(self) -> None:
        s = get_settings()
        self.slots = {
            "fast": threading.BoundedSemaphore(s.llm_max_fast_concurrency),
            "reasoning": threading.BoundedSemaphore(s.llm_max_reasoning_concurrency),
        }
        self.buckets = {
            "fast": _Bucket(s.llm_requests_per_minute_fast),
            "reasoning": _Bucket(s.llm_requests_per_minute_reasoning),
        }

    @contextmanager
    def slot(self, tier: str, wait_s: float) -> Iterator[None]:
        deadline = time.monotonic() + wait_s
        while (delay := self.buckets[tier].take()) > 0:
            if time.monotonic() + delay > deadline:
                raise Saturated("rate")
            time.sleep(delay)
        if not self.slots[tier].acquire(timeout=max(0.0, deadline - time.monotonic())):
            raise Saturated("concurrency")
        try:
            yield
        finally:
            self.slots[tier].release()


_limiter: Limiter | None = None
_lock = threading.Lock()


def limiter() -> Limiter:
    global _limiter
    with _lock:
        if _limiter is None:
            _limiter = Limiter()
        return _limiter


def reset() -> None:
    global _limiter
    with _lock:
        _limiter = None
