# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Sea Breeze Analog — a bachelor thesis web application for analyzing sea breeze behavior through analog forecasting. Compares a target weather date against historical analog days to predict sea breeze occurrence and strength. Initially focused on the Los Angeles/San Pedro area.

**Stack:** FastAPI (Python 3.12) backend, vanilla TypeScript frontend (Vite + ECharts), PostgreSQL 16, Docker Compose for local dev, Railway for production.

## Common Commands

### Local Development
```bash
docker-compose up                # Starts postgres (5433), backend (8001), frontend (5175)
```

### Backend
```bash
# Run all tests
pytest backend/tests/

# Run a single test file
pytest backend/tests/test_analog_service.py

# Run a specific test
pytest backend/tests/test_analog_service.py::test_function_name -v
```

No linter is configured. FastAPI auto-generates OpenAPI docs at `/docs` when the backend is running.

### Frontend
```bash
cd frontend
npm run dev          # Vite dev server on port 5173 (standalone, outside Docker)
npm run build        # TypeScript + Vite production build → frontend/dist/
npm run preview      # Preview production build
```

### Database Migrations (Alembic)
```bash
# Migrations run automatically on startup via main.py lifespan
# Manual commands (run from backend/):
alembic upgrade head
alembic downgrade -1
alembic revision --autogenerate -m "description"
```

### Production Build
```bash
docker build -t seabreeze:latest .    # Multi-stage: builds frontend, installs backend, serves both
```

## Architecture

### Backend (`backend/app/`)

Standard FastAPI layout with clear separation:

- **`main.py`** — App entrypoint. Registers routers under `/api/*`, configures CORS, seeds default location (LA/San Pedro) and weather station (KLAX) on startup. In production, serves the built frontend as static files with SPA fallback.
- **`config.py`** — `pydantic_settings.BaseSettings` loading from `.env`.
- **`database.py`** — SQLAlchemy async engine and session factory.
- **`models/`** — SQLAlchemy ORM models (Location, WeatherRecord, AnalysisRun, AnalogResult, DailyFeature, etc.).
- **`schemas/`** — Pydantic request/response models.
- **`routers/`** — API endpoints: `analysis`, `weather`, `classification`, `locations`, `library`, `observations`.
- **`services/`** — All business logic (~7k lines). This is where the core algorithm lives.

### Core Algorithm Flow

1. **`analog_service.py`** — `run_analog_analysis()` is the main entry point. Computes Euclidean distance between target and historical days across 9 meteorological features (wind speed, direction, temperature, pressure shifts).
2. **`feature_service.py`** — Extracts daily features from hourly weather data (morning/afternoon means, direction shifts, onshore fractions).
3. **`classification_service.py`** — Sea breeze detection using three threshold indicators: speed increase ≥1.5 m/s, direction shift ≥25°, onshore fraction ≥0.5.
4. **`forecast_service.py`** — Builds probabilistic composites (median, p10/p25/p75/p90) from top-N analog days.
5. **`bias_service.py`** — Applies source-specific bias corrections between different data sources.

### Data Provider Architecture

Abstract `WeatherProvider` base class with concrete implementations:
- **`era5_provider.py`** — Copernicus CDS API (primary historical source, 2015–2024)
- **`open_meteo_provider.py`** — Free historical API (fallback)
- **`gfs_forecast_provider.py`** — NOAA GFS GRIB data
- **`gfs_open_meteo_provider.py`** — Open-Meteo GFS forecast (fallback)
- **`iem_asos_provider.py`** — IEM ASOS station observations (CSV parsing)

### Feature Library

Precomputed daily features stored in the database (ERA5 source). Background `LibraryBuildJob` builds the library in chunks. Enables fast analog matching without re-fetching historical data each time.

### Frontend (`frontend/src/`)

Vanilla TypeScript SPA (no framework). Key modules:
- **`main.ts`** — Application entry point and orchestration (~3,200 lines). Handles analysis form, mode selection (historical vs forecast), result rendering.
- **`api.ts`** — Fetch wrappers for all `/api/*` endpoints.
- **`types.ts`** — TypeScript interfaces matching backend schemas.
- **`charts.ts`** — ECharts configuration and rendering (wind overlays, radar charts, wind roses, heatmaps, histograms, forecast composites).
- **`dashboard.ts`** — UI panel rendering, data tables, gauge displays.
- **`export.ts`** — PNG/CSV/JSON export functionality.

### Two Analysis Modes

- **Historical mode:** Fetches weather data, computes features, ranks past days as analogs.
- **Forecast mode:** Uses GFS forecast data for the target day, builds probabilistic composite from top-N analogs.

## Environment Variables

See `.env.example` for the full list. Key variables:
- `DATABASE_URL` — PostgreSQL connection string
- `APP_ENV` — "development" or "production"
- `CDSAPI_KEY` / `CDSAPI_URL` — Copernicus Climate Data Store credentials (needed for ERA5)
- `DEFAULT_LATITUDE`, `DEFAULT_LONGITUDE`, `DEFAULT_TIMEZONE` — Default analysis location
- `GFS_ANALYSIS_LOCAL_START/END` — Local hours for feature extraction window (default 8–16)

## Database

PostgreSQL 16. Alembic migrations in `backend/alembic/versions/` (prefixed 001–008). Migrations auto-run on app startup. Key tables map to models in `backend/app/models/`.

## Deployment

Production uses a single multi-stage Dockerfile that builds the frontend, installs Python deps, and serves everything from one container. Deployed on Railway — see `RAILWAY.md` for setup details.
