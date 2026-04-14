
# Sea Breeze Analog Webapp Implementation Plan

## Goal

Build a small local-first webapp for bachelor thesis analysis of sea breeze behavior, focused primarily on Los Angeles. The app should use an analog forecasting workflow:

1. Load or fetch weather forecast data.
2. Create meteorological features for a selected location.
3. Compare the current day against historical analog days.
4. Produce a thesis-friendly analysis output with plots and tables.

The existing notebook is only process inspiration. Do not directly reuse notebook code in the application. Rebuild the implementation cleanly as normal backend modules and frontend components.

## Intended Users

The app is for a very small group, initially local-only. It may later be deployed on Railway, so the architecture should remain deployable without overengineering.

No authentication is needed for version 1.

## Core Output

The application should produce a clear analytical view for a selected location and date:

- Sea breeze probability or classification.
- True wind direction over time.
- True wind speed over time.
- Analog days ranked by similarity.
- Forecast or historical analog envelope for the relevant daytime window.
- Summary statistics suitable for a bachelor thesis.

The first useful version should focus on analog analysis, not machine learning.

## Tech Stack

### Frontend

- TypeScript
- HTML
- CSS
- Vite
- Chart.js or Apache ECharts for plots

Recommended: Vite + vanilla TypeScript. Avoid React unless the UI becomes meaningfully complex.

### Backend

- Python
- FastAPI
- Pydantic
- Pandas
- NumPy
- Xarray, optional later if GRIB/NetCDF processing is needed directly
- SQLAlchemy
- Alembic
- PostgreSQL

### Data And Infrastructure

- Docker Compose for local development
- PostgreSQL for metadata, locations, runs, cached forecast records, and analog results
- Local filesystem cache for large raw weather files
- Railway-compatible Docker setup for later deployment

### Suggested External Data Sources

Start with one source and keep the interface abstract enough to add more later.

Possible sources:

- NOAA / GFS forecast data
- Open-Meteo historical and forecast APIs for faster prototyping
- ERA5 or other reanalysis datasets later for robust historical analogs

For phase 1, prefer a source that is easy to fetch and parse. The thesis value comes from the analog workflow and plots first; raw GRIB complexity can be added once the app skeleton works.

## High-Level Architecture

```text
Kandidat/
  backend/
    app/
      main.py
      config.py
      database.py
      models/
      schemas/
      services/
        weather_provider.py
        cache_service.py
        feature_service.py
        analog_service.py
        analysis_service.py
      routers/
        health.py
        locations.py
        forecasts.py
        analogs.py
    alembic/
    tests/
    pyproject.toml
    Dockerfile
  frontend/
    index.html
    package.json
    tsconfig.json
    vite.config.ts
    src/
      main.ts
      api.ts
      charts.ts
      types.ts
    styles.css
  data/
    raw/
    processed/
    cache/
  docker-compose.yml
  .env.example
  WEBAPP_IMPLEMENTATION_PLAN.md
```

## Data Model

### Location

Stores forecast and analysis points.

Fields:

- `id`
- `name`
- `latitude`
- `longitude`
- `timezone`
- `created_at`

Default location:

```text
Los Angeles / San Pedro reference point
Latitude: 33.708965
Longitude: -118.268343
Timezone: America/Los_Angeles
```

### Weather Record

Stores hourly weather data for a location.

Fields:

- `id`
- `location_id`
- `source`
- `valid_time_utc`
- `valid_time_local`
- `true_wind_speed`
- `true_wind_direction`
- `temperature`
- `pressure`
- `cloud_cover`
- `raw_payload`
- `created_at`

Minimum required fields for phase 1:

- `valid_time_utc`
- `true_wind_speed`
- `true_wind_direction`

### Analysis Run

Stores one user-triggered analysis.

Fields:

- `id`
- `location_id`
- `target_date`
- `status`
- `started_at`
- `finished_at`
- `summary`

### Analog Result

Stores ranked analog days for an analysis run.

Fields:

- `id`
- `analysis_run_id`
- `analog_date`
- `rank`
- `similarity_score`
- `distance`
- `summary`

## Backend API

### Health

```text
GET /api/health
```

Returns service and database status.

### Locations

```text
GET /api/locations
POST /api/locations
```

Version 1 can seed a default LA location automatically.

### Weather Data

```text
GET /api/weather?location_id=...&date=...
POST /api/weather/fetch
```

Behavior:

- Check PostgreSQL and filesystem cache first.
- If data already exists for the requested source, location, and date, return cached data.
- If data does not exist, fetch from provider, normalize, store, and return.

### Analysis

```text
POST /api/analysis/run
GET /api/analysis/{run_id}
GET /api/analysis/{run_id}/series
GET /api/analysis/{run_id}/analogs
```

`POST /api/analysis/run` should accept:

```json
{
  "location_id": 1,
  "target_date": "2026-06-15",
  "historical_start_date": "2020-05-01",
  "historical_end_date": "2025-09-30"
}
```

The app should later allow defaults so the user does not need to fill every field manually.

## Frontend Screens

### Main Analysis Screen

Controls:

- Location selector
- Date selector
- Run analysis button

Summary:

- Sea breeze classification
- Confidence or probability
- Number of analog days used
- Main wind direction shift
- Maximum wind speed
- Time of strongest sea breeze signal

Plots:

- True wind speed over time
- True wind direction over time
- Optional temperature over time
- Optional pressure over time
- Optional analog spread or percentile band

Tables:

- Hourly weather table
- Ranked analog days table
- Summary statistics table

### Design Principle

This is not a marketing site. The first screen should be the analysis tool itself.

Use clear scientific labels:

- `True Wind Speed`
- `True Wind Direction`
- `Local Time`
- `m/s`
- `degrees`
- `Analog Distance`
- `Sea Breeze Classification`

## Analog Method

Start simple and transparent.

### Feature Window

For each target day and historical day, calculate features from the morning and early afternoon:

- morning mean wind speed
- morning mean wind direction using circular mean
- wind direction at selected reference hour
- wind speed at selected reference hour
- temperature at selected reference hour, if available
- wind speed increase from morning to afternoon
- wind direction shift from morning to afternoon
- afternoon maximum wind speed

Suggested default reference hour:

```text
09:00 local time
```

Suggested analysis window:

```text
08:00-16:00 local time
```

Suggested forecast or thesis output window:

```text
11:00-16:00 local time
```

### Sea Breeze Classification

Use a transparent rules-based classification first.

Candidate indicators:

- Wind direction shifts toward onshore sector.
- Wind speed increases after late morning.
- Direction remains within an expected sea breeze sector for part of the afternoon.
- Temperature and pressure patterns can be added later.

For the LA / San Pedro area, the onshore sector should be configurable rather than hardcoded forever.

Initial configurable defaults:

```text
onshore_direction_min = 180
onshore_direction_max = 260
minimum_speed_increase_mps = 1.5
minimum_direction_shift_degrees = 25
minimum_onshore_fraction = 0.5
```

### Similarity

Use standardized Euclidean distance for version 1.

Later alternatives:

- cosine distance
- dynamic time warping for full wind curves
- weighted feature distance
- station-calibrated analog distance

## Caching Strategy

When the user requests data:

1. Check PostgreSQL for normalized hourly records.
2. Check filesystem cache for raw provider response.
3. Fetch from external provider only if missing.
4. Store raw response in `data/cache`.
5. Store normalized hourly records in PostgreSQL.

Cache keys should include:

- source
- location latitude and longitude rounded consistently
- date or date range
- provider model/run if applicable

This makes local usage fast and avoids unnecessary downloads.

## Docker Plan

Use Docker Compose locally:

```text
services:
  backend
  frontend
  postgres
```

For local development:

- frontend runs on `http://localhost:5173`
- backend runs on `http://localhost:8000`
- postgres runs on `localhost:5432`

For Railway later:

- backend can be deployed as a Docker service
- PostgreSQL can use Railway Postgres
- frontend can either be served separately or built into static files served by the backend

For simplicity, version 1 can serve frontend separately in development and decide deployment shape later.

## Environment Variables

Create `.env.example`:

```text
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/seabreeze
APP_ENV=development
WEATHER_CACHE_DIR=../data/cache
DEFAULT_LATITUDE=33.708965
DEFAULT_LONGITUDE=-118.268343
DEFAULT_TIMEZONE=America/Los_Angeles
```

If using an API key based provider later, add:

```text
WEATHER_API_KEY=
```

Do not hardcode secrets in code.

## Implementation Phases

## Phase 1: Project Skeleton

Goal: Create the app foundation.

Tasks:

- Create `backend` folder with FastAPI app.
- Create `frontend` folder with Vite + TypeScript.
- Create `docker-compose.yml` with backend, frontend, and postgres.
- Add `.env.example`.
- Add `GET /api/health`.
- Confirm backend can connect to Postgres.
- Confirm frontend can call backend health endpoint.

Acceptance checks:

- `docker compose up` starts all services.
- `http://localhost:8000/api/health` returns healthy status.
- `http://localhost:5173` loads a basic frontend page.
- Frontend displays backend health status.

## Phase 2: Database Models And Seed Location

Goal: Add persistent storage.

Tasks:

- Add SQLAlchemy setup.
- Add Alembic migrations.
- Create tables:
  - `locations`
  - `weather_records`
  - `analysis_runs`
  - `analog_results`
- Seed default LA location.
- Add `GET /api/locations`.

Acceptance checks:

- Migrations run cleanly.
- Default LA location exists after startup or seed command.
- Frontend can display the LA location.

## Phase 3: Weather Provider Interface And Cache

Goal: Fetch or load hourly weather data through a clean abstraction.

Tasks:

- Create `WeatherProvider` interface.
- Implement first provider.
- Add filesystem raw-response cache.
- Add normalized records in Postgres.
- Add `POST /api/weather/fetch`.
- Add `GET /api/weather`.

Recommended provider for fastest first version:

- Open-Meteo, because it is easy to prototype and returns JSON.

Later provider:

- NOAA/GFS direct download for thesis-grade forecast source.

Acceptance checks:

- Requesting a date range fetches hourly wind speed and direction.
- Repeating the same request uses cached data.
- Weather records are stored in Postgres.
- API returns local-time hourly records.

## Phase 4: Feature Engineering

Goal: Convert hourly records into daily analysis features.

Tasks:

- Implement circular wind direction helpers.
- Implement daily feature calculation.
- Implement configurable analysis windows.
- Add tests for:
  - circular mean
  - direction difference
  - daily feature extraction

Features:

- morning mean wind speed
- morning circular mean wind direction
- reference-hour wind speed
- reference-hour wind direction
- afternoon max wind speed
- afternoon circular mean wind direction
- wind speed increase
- wind direction shift
- onshore fraction

Acceptance checks:

- Backend can produce one daily feature object for a location/date.
- Circular direction cases around `0/360` behave correctly.

## Phase 5: Sea Breeze Classification

Goal: Add transparent rules-based sea breeze detection.

Tasks:

- Implement configurable sea breeze thresholds.
- Classify a day as:
  - `low`
  - `medium`
  - `high`
- Return contributing indicators.

Suggested output:

```json
{
  "classification": "high",
  "score": 0.82,
  "indicators": {
    "speed_increase": true,
    "direction_shift": true,
    "onshore_fraction": true
  }
}
```

Acceptance checks:

- Classification endpoint or analysis service returns a readable result.
- Frontend displays classification and indicators.

## Phase 6: Analog Matching

Goal: Compare target day against historical days.

Tasks:

- Fetch/load historical date range.
- Calculate daily features for each historical day.
- Filter valid days with enough hourly records.
- Standardize feature matrix.
- Compute Euclidean distance.
- Return top analog days.
- Store analog results in Postgres.

Acceptance checks:

- Running analysis returns top analog days.
- Each analog result includes rank, date, distance, and summary values.
- Re-running analysis does not refetch cached historical data unnecessarily.

## Phase 7: Thesis Analysis Dashboard

Goal: Build the first useful frontend.

Tasks:

- Add date picker.
- Add location selector.
- Add run-analysis button.
- Add analysis summary panel.
- Add true wind speed chart.
- Add true wind direction chart.
- Add hourly data table.
- Add analog days table.

Charts:

- x-axis: local time
- wind speed y-axis: `m/s`
- wind direction y-axis: `degrees`

Acceptance checks:

- User can run analysis from the browser.
- Dashboard shows wind speed over time.
- Dashboard shows wind direction over time.
- Dashboard shows analog ranking table.
- Output is understandable for thesis analysis.

## Phase 8: Export And Reproducibility

Goal: Make outputs useful for writing the bachelor thesis.

Tasks:

- Add CSV export for hourly weather records.
- Add CSV export for analog days.
- Add JSON export for full analysis run.
- Add chart image export if easy.
- Store analysis run parameters.

Acceptance checks:

- User can reproduce a previous run.
- User can export data for thesis figures/tables.

## Phase 9: Docker And Railway Readiness

Goal: Make deployment possible without changing the app architecture.

Tasks:

- Add backend Dockerfile.
- Add frontend Dockerfile or static build.
- Confirm Docker Compose works from clean checkout.
- Add production environment variable documentation.
- Add Railway notes.

Acceptance checks:

- App runs locally from Docker.
- Database URL can be swapped for Railway Postgres.
- No local absolute paths are required in production.

## Phase 10: Later Enhancements

Potential additions after the first analog version works:

- Weather station observations.
- Raw GFS GRIB support.
- ERA5 historical reanalysis support.
- Station-vs-forecast validation.
- ML model trained on analog features.
- Multiple locations.
- Map-based location picker.
- PDF report export.
- More advanced analog similarity methods.

## Claude Code Execution Notes

Claude Code should implement one phase at a time.

Before each phase:

- Inspect the current file tree.
- Avoid rewriting completed phases unless needed.
- Keep changes scoped to the phase.
- Run relevant tests or smoke checks.

After each phase:

- Summarize files changed.
- List commands used.
- List verification results.
- Mention any blocked items or assumptions.

Do not start with the notebook. The notebook is background context only.

## Recommended First Prompt To Claude Code

```text
Implement Phase 1 from WEBAPP_IMPLEMENTATION_PLAN.md.

Create a local-first FastAPI backend, Vite TypeScript frontend, Docker Compose setup with Postgres, .env.example, and a health check connection from frontend to backend.

Do not use or import the existing notebook. Keep the implementation clean and minimal.

After implementation, run the available smoke checks and summarize files changed.
```

