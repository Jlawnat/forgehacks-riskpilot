#!/bin/sh
set -eu

: "${RISKPILOT_DEMO_PASSWORD:?Set RISKPILOT_DEMO_PASSWORD in Render Environment}"

PORT="${PORT:-10000}"
case "$PORT" in
  ''|*[!0-9]*) echo 'Invalid PORT' >&2; exit 2 ;;
esac

exec python -m uvicorn src.api.deployment:app \
  --host 0.0.0.0 \
  --port "$PORT" \
  --workers 1 \
  --no-access-log
