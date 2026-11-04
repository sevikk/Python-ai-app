import math
import threading
import time
from collections import deque
from typing import Optional

from fastapi import HTTPException, Request


class InMemoryRateLimiter:
    def __init__(self, limit: int, window_seconds: int) -> None:
        if limit <= 0:
            raise ValueError("limit must be a positive integer.")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be a positive integer.")
        self.limit = limit
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = {}
        self._last_cleanup = time.monotonic()
        self._lock = threading.Lock()

    def check(self, client_id: str) -> Optional[int]:
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            requests = self._requests.setdefault(client_id, deque())
            while requests and requests[0] <= cutoff:
                requests.popleft()

            if len(requests) >= self.limit:
                return max(
                    1,
                    math.ceil(self.window_seconds - (now - requests[0])),
                )

            requests.append(now)
            if now - self._last_cleanup >= self.window_seconds:
                active_requests: dict[str, deque[float]] = {}
                for key, timestamps in self._requests.items():
                    while timestamps and timestamps[0] <= cutoff:
                        timestamps.popleft()
                    if timestamps:
                        active_requests[key] = timestamps
                self._requests = active_requests
                self._last_cleanup = now
            return None


def enforce_chat_rate_limit(request: Request) -> None:
    client = request.client
    client_id = client.host if client is not None else "unknown"
    retry_after = request.app.state.chat_rate_limiter.check(client_id)
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Too many chat requests. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )
