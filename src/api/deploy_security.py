"""Single-instance, password-protected competition demonstration gateway.

This is not a multi-tenant customer service, persistent data store, or an
API-key billing control. It deliberately changes no RiskPilot finance engines.
"""
from __future__ import annotations

import base64
import binascii
from collections import deque
from secrets import compare_digest
from threading import Lock
from time import monotonic

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class DemoAccessGateway(BaseHTTPMiddleware):
    """HTTP Basic entry gate, request size limit and per-process throttling."""

    def __init__(self, app, *, password: str, username: str = "demo"):
        super().__init__(app)
        if not password or len(password) < 16:
            raise ValueError("RISKPILOT_DEMO_PASSWORD must contain at least 16 characters")
        self._username = username
        self._password = password
        self._lock = Lock()
        self._requests: dict[tuple[str, str], deque[float]] = {}

    def _authorized(self, header: str | None) -> bool:
        if not header or not header.startswith("Basic "):
            return False
        try:
            raw = base64.b64decode(header[6:].strip(), validate=True).decode("utf-8")
        except (UnicodeError, ValueError, binascii.Error):
            return False
        user, separator, password = raw.partition(":")
        return bool(separator) and compare_digest(user, self._username) and compare_digest(password, self._password)

    def _allowed(self, key: tuple[str, str], *, limit: int, interval: int) -> bool:
        now = monotonic()
        with self._lock:
            queue = self._requests.setdefault(key, deque())
            while queue and now - queue[0] >= interval:
                queue.popleft()
            if len(queue) >= limit:
                return False
            queue.append(now)
            # Prevent unlimited client identifiers filling process memory.
            if len(self._requests) > 2048:
                for old_key in list(self._requests)[:512]:
                    if old_key != key:
                        self._requests.pop(old_key, None)
            return True

    async def dispatch(self, request, call_next):
        path = request.url.path
        if path == "/api/health":
            return await call_next(request)

        if not self._authorized(request.headers.get("authorization")):
            return JSONResponse(
                {"detail": "RiskPilot private demo: sign in as demo with the reviewer password."},
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="RiskPilot Demo", charset="UTF-8"',
                         "Cache-Control": "no-store"},
            )

        try:
            content_length = int(request.headers.get("content-length", "0"))
        except ValueError:
            return JSONResponse({"detail": "Invalid request length"}, status_code=400)
        if content_length > 20 * 1024 * 1024:
            return JSONResponse({"detail": "Request exceeds 20 MB demo limit"}, status_code=413)

        client = request.client.host if request.client else "unknown"
        is_ai = request.method == "POST" and (
            path.endswith("/agent") or "decision-ai" in path or "ai-decision" in path
            or "decision-insight" in path
        )
        if not self._allowed(("global", "all"), limit=300, interval=60):
            return JSONResponse({"detail": "Demo service is busy. Try again shortly."}, status_code=429,
                                headers={"Retry-After": "60"})
        if not self._allowed((client, "all"), limit=100, interval=60):
            return JSONResponse({"detail": "Demo traffic limit reached. Try again shortly."}, status_code=429,
                                headers={"Retry-After": "60"})
        if is_ai and not self._allowed((client, "ai"), limit=6, interval=60):
            return JSONResponse({"detail": "Demo AI usage limit reached. Try again shortly."}, status_code=429,
                                headers={"Retry-After": "60"})

        if is_ai and not self._allowed(("global", "ai_hour"), limit=40, interval=3600):
            return JSONResponse({"detail": "Demo AI hourly budget reached. Try again later."}, status_code=429,
                                headers={"Retry-After": "3600"})

        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        if path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response
