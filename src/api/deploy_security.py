"""RiskPilot Render demo gateway: private login or isolated public synthetic sandbox.

The public sandbox has no customer account, persistence, distributed rate limiter,
or guarantee against financial service abuse. Use synthetic fixtures only.
"""
from __future__ import annotations

import base64
import binascii
from collections import deque
import hashlib
import hmac
from secrets import compare_digest, token_bytes, token_urlsafe
from threading import Lock, BoundedSemaphore
from time import monotonic
from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from src.api.public_interactive import reset_public_visitor, set_public_visitor


PUBLIC_GET = frozenset({
    "/api/health", "/api/scenarios", "/api/demo/harborview-cash.csv",
    "/api/customer/template", "/api/forecast/history",
})
PUBLIC_GET_PREFIX = (
    "/api/command-center/", "/api/agent/verified-workspace/",
    "/api/recovery-options/", "/api/evidence/weeks/",
    "/api/reports/", "/api/monitoring/", "/api/demo/samples/",
)
PUBLIC_POST = frozenset({
    "/api/what-if", "/api/agent", "/api/recovery/optimise",
    "/api/recovery/validate-plan", "/api/recovery/decision-insight",
    "/api/customer/import", "/api/customer/mapping/preview",
    "/api/customer/mapping/import", "/api/customer/multi/import",
    "/api/legacy/monthly/import", "/api/legacy/monthly/stress",
    "/api/legacy/monthly/reverse-stress", "/api/legacy/monthly/agent",
    "/api/forecast/history/save", "/api/forecast/history/compare",
    "/api/forecast/history/actuals",
})
HEAVY_POST = PUBLIC_POST - frozenset({"/api/customer/mapping/preview"})
_COOKIE_NAME = "rp_judge_session"


class DemoAccessGateway(BaseHTTPMiddleware):
    """Enforce private Basic auth OR public sandbox routing/visitor cookie/quotas."""

    def __init__(self, app, *, password: str, username: str = "demo", interactive: bool = False):
        super().__init__(app)
        if not interactive and (not password or len(password) < 16):
            raise ValueError("RISKPILOT_DEMO_PASSWORD must contain at least 16 characters")
        self._interactive = interactive
        self._username = username
        self._password = password
        self._secret = token_bytes(32)
        self._lock = Lock()
        self._requests: dict[tuple[str, str], deque[float]] = {}
        self._heavy_slots = BoundedSemaphore(2)

    def _authorized(self, header: str | None) -> bool:
        if not header or not header.startswith("Basic "):
            return False
        try:
            raw = base64.b64decode(header[6:].strip(), validate=True).decode("utf-8")
        except (UnicodeError, ValueError, binascii.Error):
            return False
        user, delimiter, password = raw.partition(":")
        return bool(delimiter) and compare_digest(user, self._username) and compare_digest(password, self._password)

    def _cookie(self, identifier: str) -> str:
        signature = hmac.new(self._secret, identifier.encode("ascii"), hashlib.sha256).hexdigest()
        return f"{identifier}.{signature}"

    def _visitor(self, request) -> tuple[str, bool]:
        cookie = request.cookies.get(_COOKIE_NAME, "")
        if len(cookie) < 160:
            identifier, separator, signature = cookie.partition(".")
            if (separator and 24 <= len(identifier) <= 80
                and len(signature) == 64
                and all(ch.isalnum() or ch in "-_" for ch in identifier)
                and compare_digest(self._cookie(identifier), cookie)):
                return identifier, False
        return token_urlsafe(32), True

    def _public_route(self, path: str, method: str) -> bool:
        if path.startswith("/api/"):
            if method in {"GET", "HEAD"}:
                return path in PUBLIC_GET or any(path.startswith(p) for p in PUBLIC_GET_PREFIX)
            return method == "POST" and path in PUBLIC_POST
        return method in {"GET", "HEAD"} and path not in {"/docs", "/redoc", "/openapi.json"}

    def _allowed(self, key: tuple[str, str], *, limit: int, interval: int) -> bool:
        now = monotonic()
        with self._lock:
            queue = self._requests.setdefault(key, deque())
            while queue and now - queue[0] >= interval:
                queue.popleft()
            if len(queue) >= limit:
                return False
            queue.append(now)
            if len(self._requests) > 2048:
                for old_key in list(self._requests)[:512]:
                    if old_key != key:
                        self._requests.pop(old_key, None)
            return True

    async def dispatch(self, request, call_next):
        path = request.url.path
        if path == "/api/health":
            return await call_next(request)

        if self._interactive:
            if not self._public_route(path, request.method):
                return JSONResponse({"detail": "Not available in the synthetic judge sandbox."}, status_code=403)
            if request.method not in {"GET", "HEAD"}:
                origin = request.headers.get("origin", "")
                host = request.headers.get("host", "").lower()
                site = request.headers.get("sec-fetch-site", "").lower()
                if site == "cross-site" or (origin and urlsplit(origin).netloc.lower() != host):
                    return JSONResponse({"detail": "Cross-origin writes are disabled."}, status_code=403)
            visitor, new_cookie = self._visitor(request)
        else:
            if not self._authorized(request.headers.get("authorization")):
                return JSONResponse(
                    {"detail": "RiskPilot private demo: sign in as demo with the reviewer password."},
                    status_code=401,
                    headers={"WWW-Authenticate": 'Basic realm="RiskPilot Demo", charset="UTF-8"',
                             "Cache-Control": "no-store"},
                )
            visitor, new_cookie = "", False

        try:
            size = int(request.headers.get("content-length", "0"))
        except ValueError:
            return JSONResponse({"detail": "Invalid request length."}, status_code=400)
        if size < 0 or size > 20 * 1024 * 1024:
            return JSONResponse({"detail": "Request too large (20 MB limit)."}, status_code=413)

        ip = request.client.host if request.client else "unknown"
        prefix = "public" if self._interactive else "private"
        if not self._allowed((prefix, "all"), limit=150 if self._interactive else 300, interval=60):
            return JSONResponse({"detail": "Demo service is busy. Retry in one minute."}, status_code=429)
        if not self._allowed((ip, "all"), limit=90 if self._interactive else 100, interval=60):
            return JSONResponse({"detail": "Too many requests. Retry shortly."}, status_code=429)
        is_ai = request.method == "POST" and (path.endswith("/agent") or "decision-insight" in path)
        if is_ai and not self._allowed((ip, "ai"), limit=3 if self._interactive else 6, interval=60):
            return JSONResponse({"detail": "AI demo rate limit reached."}, status_code=429, headers={"Retry-After": "60"})
        if is_ai and not self._allowed((prefix, "ai-hour"), limit=20 if self._interactive else 40, interval=3600):
            return JSONResponse({"detail": "AI demo hourly budget reached."}, status_code=429, headers={"Retry-After": "3600"})

        heavy = self._interactive and request.method == "POST" and path in HEAVY_POST
        if heavy and not self._heavy_slots.acquire(blocking=False):
            return JSONResponse({"detail": "Demo calculations are busy. Retry in five seconds."},
                                status_code=429, headers={"Retry-After": "5"})
        token = set_public_visitor(visitor) if self._interactive else None
        try:
            response = await call_next(request)
        finally:
            if token is not None:
                reset_public_visitor(token)
            if heavy:
                self._heavy_slots.release()

        if self._interactive and new_cookie:
            response.set_cookie(_COOKIE_NAME, self._cookie(visitor), max_age=7200,
                                httponly=True, secure=True, samesite="lax", path="/")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        if path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response
