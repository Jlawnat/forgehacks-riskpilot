# Render single-service deployment: Vite production assets + Python financial API.
FROM node:22-alpine AS frontend
WORKDIR /build/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

COPY requirements-deploy.txt ./
RUN python -m pip install --no-cache-dir -r requirements-deploy.txt
COPY src/ ./src/
COPY web/public/ ./web/public/
COPY --from=frontend /build/web/dist/ ./web/dist/
COPY scripts/start_render.sh ./scripts/start_render.sh
RUN useradd --create-home --uid 10001 riskpilot && chown -R riskpilot:riskpilot /app
USER riskpilot
EXPOSE 10000
CMD ["sh", "scripts/start_render.sh"]
