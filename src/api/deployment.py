"""Render single-origin entry point: existing FastAPI routes and compiled React.

RISKPILOT_PUBLIC_INTERACTIVE=1 enables the synthetic, anonymous reviewer sandbox.
Without it, the original password-protected private mode is preserved.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi.staticfiles import StaticFiles

from src.api.deploy_security import DemoAccessGateway
from src.api.public_interactive import public_interactive_enabled
from src.api.premium_web import app

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"
if not (FRONTEND_DIST / "index.html").is_file():
    raise RuntimeError(f"React build not found: {FRONTEND_DIST / 'index.html'}")

INTERACTIVE = public_interactive_enabled()
PASSWORD = os.environ.get("RISKPILOT_DEMO_PASSWORD", "")
if not INTERACTIVE and len(PASSWORD) < 16:
    raise RuntimeError("Set RISKPILOT_DEMO_PASSWORD to at least 16 characters before exposing RiskPilot.")

app.add_middleware(DemoAccessGateway, password=PASSWORD, interactive=INTERACTIVE)
app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="premium_react")
