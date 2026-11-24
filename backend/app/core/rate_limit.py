"""Process-local sliding-window limits for chat and authentication endpoints."""

import hashlib
import math
import threading
import time
from collections import deque
from typing import Optional

from fastapi import HTTPException, Request


class InMemoryRateLimiter:
    """Track request timestamps per client key for a fixed rolling time window."""

    def __init__(self, limit: int, window_seconds: int) -> None:
        """Create a limiter that permits limit requests per time window."""
        if limit <= 0:
            raise ValueError("limit must be a positive integer.")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be a positive integer.")
        # Maximum number of timestamps retained per client during one window.
        self.limit = limit
        # Duration over which each client's timestamps remain active.
        self.window_seconds = window_seconds
        # Per-client request timestamps used to calculate the rolling window.
        self._requests: dict[str, deque[float]] = {}
        # Controls how often stale client entries are removed from memory.
        self._last_cleanup = time.monotonic()
        # Protects shared state when requests are handled by multiple threads.
        self._lock = threading.Lock()

    def check(self, client_id: str) -> Optional[int]:
        """Record an allowed request or return seconds until it may retry."""
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
    """Reject chat requests that exceed the configured client-IP allowance."""
    client = request.client
    client_id = client.host if client is not None else "unknown"
    retry_after = request.app.state.chat_rate_limiter.check(client_id)
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Too many chat requests. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )


def enforce_auth_rate_limit(request: Request, email: str) -> None:
    """Enforce both per-IP and per-IP/email limits on auth attempts."""
    client = request.client
    client_id = client.host if client is not None else "unknown"

    retry_after = request.app.state.auth_ip_rate_limiter.check(client_id)
    if retry_after is None:
        email_hash = hashlib.sha256(email.strip().lower().encode()).hexdigest()
        retry_after = request.app.state.auth_pair_rate_limiter.check(
            f"{client_id}:{email_hash}"
        )

    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Too many authentication attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )
