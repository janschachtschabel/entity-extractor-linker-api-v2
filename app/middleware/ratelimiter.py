"""Simple in-memory rate limiting middleware (token bucket per client IP).

Not suitable for multi-instance deployments but sufficient for local / small
setups. Limits are configurable via settings.py.
"""

from __future__ import annotations

from collections import defaultdict, deque
from time import time
from typing import ClassVar

from fastapi.responses import JSONResponse
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send


class RateLimitMiddleware:
    """Rate limiting middleware for FastAPI applications."""

    _buckets: ClassVar[dict[str, deque[float]]] = defaultdict(deque)

    def __init__(self, app: ASGIApp, *, limit: int = 60, window: int = 60) -> None:
        """Initialize rate limiter with specified limits."""
        self.app = app
        self.limit = limit
        self.window = window

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process request with rate limiting."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        client_ip = request.client.host if request.client else "anonymous"
        bucket = self._buckets[client_ip]
        now = time()
        # Remove expired tokens
        while bucket and bucket[0] <= now - self.window:
            bucket.popleft()
        if len(bucket) >= self.limit:
            retry_after = int(bucket[0] + self.window - now) + 1
            response = JSONResponse(
                {"detail": "Rate limit exceeded. Try again later."},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )
            await response(scope, receive, send)
            return
        bucket.append(now)
        await self.app(scope, receive, send)
