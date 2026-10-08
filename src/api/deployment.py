"""Render entry point: existing FastAPI endpoints plus compiled React website.

Usage: RISKPILOT_DEMO_PASSWORD=... uvicorn src.api.deployment:app
The API and frontend share one origin; /api routes always take priority.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi.staticfiles import StaticFiles

from src.api.deploy_security import DemoAccessGateway
from src.api.premium_web import app

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"
if not (FRONTEND_DIST / "index.html").is_file():
    raise RuntimeError(
        f"React build not found: {FRONTEND_DIST / 'index.html'}. "
        "Run 'cd web && npm ci && npm run build' before starting the deployment."
    )

DEMO_PASSWORD = os.environ.get("RISKPILOT_DEMO_PASSWORD", "")
if len(DEMO_PASSWORD) < 16:
    raise RuntimeError(
        "Set RISKPILOT_DEMO_PASSWORD to at least 16 characters before exposing RiskPilot."
    )

# Production-only middleware. Local scripts/run_premium_web.sh remains unchanged.
app.add_middleware(DemoAccessGateway, password=DEMO_PASSWORD)

# This mount comes AFTER all /api routes, preserving all original API behavior.
app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="premium_react")
