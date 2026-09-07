# syntax=docker/dockerfile:1

# ---- Stage 1: build the Next.js static export ----
FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python runtime ----
FROM python:3.12-slim AS runtime
WORKDIR /app

# Install uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Install backend dependencies (runtime only, no dev/test extras)
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy backend source
COPY backend/app ./app

# Install the backend project itself
RUN uv sync --frozen --no-dev

# Copy the frontend static export into the location the backend serves by default
COPY --from=frontend-build /frontend/out ./app/static

# Ensure the DB directory exists so it's available even without a volume mount
RUN mkdir -p /app/db

ENV FINALLY_DB_PATH=/app/db/finally.db
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uv", "run", "--no-dev", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
