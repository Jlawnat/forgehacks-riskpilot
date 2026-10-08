"""Deployment gateway checks; require no API key, AI call or external service."""
import base64

from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api.deploy_security import DemoAccessGateway

PASSWORD = "this-is-an-example-reviewer-password"


def client():
    app = FastAPI()

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/scenarios")
    def scenarios():
        return ["synthetic"]

    @app.post("/api/agent")
    def agent():
        return {"answer": "mock only"}

    app.add_middleware(DemoAccessGateway, password=PASSWORD)
    return TestClient(app)


def auth(password=PASSWORD):
    credentials = base64.b64encode(f"demo:{password}".encode()).decode()
    return {"Authorization": f"Basic {credentials}"}


def test_health_is_public_for_render():
    with client() as c:
        assert c.get("/api/health").json() == {"status": "ok"}


def test_all_other_routes_require_correct_basic_auth():
    with client() as c:
        assert c.get("/api/scenarios").status_code == 401
        assert c.get("/api/scenarios").headers["www-authenticate"].startswith("Basic")
        assert c.get("/api/scenarios", headers=auth("wrong-password-123456")).status_code == 401
        assert c.get("/api/scenarios", headers={"Authorization": "Basic not-base64"}).status_code == 401
        good = c.get("/api/scenarios", headers=auth())
        assert good.status_code == 200
        assert good.json() == ["synthetic"]
        assert good.headers["cache-control"] == "no-store"
        assert good.headers["x-content-type-options"] == "nosniff"


def test_request_too_large_is_rejected():
    with client() as c:
        result = c.post("/api/agent", headers={**auth(), "Content-Length": str(21 * 1024 * 1024)})
        assert result.status_code == 413


def test_ai_throttle_protects_usage():
    with client() as c:
        for _ in range(6):
            assert c.post("/api/agent", headers=auth()).status_code == 200
        blocked = c.post("/api/agent", headers=auth())
        assert blocked.status_code == 429
        assert blocked.headers["retry-after"] == "60"


def test_password_requires_minimum_length():
    app = FastAPI()
    app.add_middleware(DemoAccessGateway, password="too-short")
    try:
        with TestClient(app):
            raise AssertionError("Middleware should not start")
    except ValueError as exc:
        assert "at least 16" in str(exc)


def test_frontend_and_api_share_one_origin(tmp_path):
    from fastapi.staticfiles import StaticFiles

    (tmp_path / "index.html").write_text("<html><body>RiskPilot premium app</body></html>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "demo.js").write_text("console.log('demo');")
    app = FastAPI()

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/scenarios")
    def scenarios():
        return [{"id": "harborview_synthetic"}]

    app.add_middleware(DemoAccessGateway, password=PASSWORD)
    app.mount("/", StaticFiles(directory=str(tmp_path), html=True), name="react")

    with TestClient(app) as c:
        assert c.get("/").status_code == 401
        root = c.get("/", headers=auth())
        assert root.status_code == 200
        assert "RiskPilot premium app" in root.text
        assert c.get("/assets/demo.js", headers=auth()).status_code == 200
        api = c.get("/api/scenarios", headers=auth())
        assert api.status_code == 200
        assert api.json()[0]["id"] == "harborview_synthetic"
        assert c.get("/api/health").status_code == 200
