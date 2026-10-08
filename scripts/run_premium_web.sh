#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."

echo "========================================"
echo "RiskPilot Premium Product UI"
echo "========================================"

if ! command -v npm >/dev/null 2>&1; then
  echo
  echo "ERROR: Node/npm is not installed."
  echo "Install Node.js first, then rerun this script."
  exit 1
fi

if [ ! -d "web/node_modules" ]; then
  echo "Installing React frontend dependencies..."
  (
    cd web
    npm install
  )
fi

echo
echo "Starting RiskPilot Python API on port 8000..."
.venv/bin/python -m uvicorn \
  src.api.premium_web:app \
  --host 127.0.0.1 \
  --port 8000 \
  --reload &

API_PID=$!

cleanup() {
  kill "$API_PID" >/dev/null 2>&1 || true
}

trap cleanup EXIT INT TERM

sleep 2

echo
echo "Starting premium frontend..."
echo
echo "Open:"
echo "http://localhost:5173"
echo

cd web
npm run dev
