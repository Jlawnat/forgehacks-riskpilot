"""Stdlib-only checks for the Docker/Render deployment bundle."""
from pathlib import Path
import sys

root = Path(__file__).resolve().parent.parent
required = [
    "Dockerfile", ".dockerignore", "render.yaml", "requirements-deploy.txt",
    "scripts/start_render.sh", "src/api/deployment.py", "src/api/deploy_security.py",
    "web/package-lock.json", "web/src/App.jsx", "src/api/premium_web.py",
]
missing = [name for name in required if not (root / name).is_file()]
if missing:
    print("FAIL: Missing deploy files:", ", ".join(missing))
    sys.exit(1)

dockerfile = (root / "Dockerfile").read_text()
yaml = (root / "render.yaml").read_text()
gateway = (root / "src/api/deploy_security.py").read_text()
entry = (root / "src/api/deployment.py").read_text()
assert "npm ci" in dockerfile and "npm run build" in dockerfile
assert "src.api.deployment:app" in (root / "scripts/start_render.sh").read_text()
assert "healthCheckPath: /api/health" in yaml
assert "sync: false" in yaml
assert "app.mount(\"/\"" in entry
assert "DemoAccessGateway" in gateway
assert "OPENAI_API_KEY" not in yaml, "Never store AI keys in render.yaml"
print("PASS: 10 required files found")
print("PASS: React build, FastAPI mount, Basic Auth gateway and Render health path")
print("PASS: AI credentials excluded from deployment configuration")
