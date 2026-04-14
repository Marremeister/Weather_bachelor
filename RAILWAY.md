# Railway Deployment Guide

## Architecture

The production build uses a single Docker container:

1. **Stage 1** — `node:22-alpine` builds the Vite frontend (`npm ci && npm run build`)
2. **Stage 2** — `python:3.12-slim` installs Python deps, copies the backend + built frontend into `static/`, runs Alembic migrations, then starts uvicorn

FastAPI serves the API at `/api/*` and the built SPA at all other routes. One service, one port, no CORS issues.

## Setup Steps

### 1. Create a Railway project

- Link your GitHub repository
- Railway will auto-detect the root `Dockerfile`

### 2. Add a PostgreSQL plugin

- In your Railway project, click **New** → **Database** → **PostgreSQL**
- Railway auto-injects `DATABASE_URL` into your service

### 3. Configure environment variables

Set these in the Railway dashboard under your service's **Variables** tab:

| Variable | Value | Notes |
|----------|-------|-------|
| `DATABASE_URL` | *(auto-injected)* | Railway provides `postgresql://...`; the app auto-converts to `postgresql+psycopg://` |
| `APP_ENV` | `production` | |
| `WEATHER_CACHE_DIR` | `/tmp/cache` | Ephemeral storage; Postgres is the durable cache |
| `CDSAPI_URL` | `https://cds.climate.copernicus.eu/api` | |
| `CDSAPI_KEY` | *(your key)* | From Copernicus CDS |
| `ALLOWED_ORIGINS` | *(your domain)* | Optional — only needed if external clients call the API |

**Note:** `PORT` is auto-injected by Railway. The Dockerfile uses `${PORT:-8000}`.

### 4. Deploy

Push to your linked branch. Railway builds the Dockerfile automatically and runs:

```
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## DATABASE_URL Format

Railway provides:
```
postgresql://user:pass@host:port/dbname
```

psycopg requires:
```
postgresql+psycopg://user:pass@host:port/dbname
```

A `field_validator` in `backend/app/config.py` handles this conversion automatically. No manual editing needed.

## Weather Cache on Railway

Railway containers have ephemeral filesystems — files in `/tmp/cache` are lost on redeploy. This is fine because:

- The weather cache is a performance optimization, not critical data
- Postgres stores all persisted weather data
- The cache rebuilds automatically on cache miss

## Local Production Testing

To test the production build locally:

```bash
docker compose --profile prod up --build postgres app
```

This builds the multi-stage Dockerfile and runs the full app at `http://localhost:8000`.

Standard dev mode (unchanged):

```bash
docker compose up --build
```

Frontend at `http://localhost:5175`, backend API at `http://localhost:8001`.
