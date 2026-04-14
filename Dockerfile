# ---- Stage 1: Build frontend ----
FROM node:22-alpine AS frontend-build

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# ---- Stage 2: Production backend ----
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install Python dependencies
COPY backend/pyproject.toml .
RUN uv pip install --system -r pyproject.toml

# Copy backend source
COPY backend/ .

# Copy built frontend into static/ directory
COPY --from=frontend-build /frontend/dist ./static

# Railway injects PORT; default to 8000
ENV PORT=8000

EXPOSE ${PORT}

CMD sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"
