# Sea Breeze Analog

A web application for analyzing and forecasting sea breeze behavior using analog meteorological methods. Built as a bachelor thesis project, initially focused on the Los Angeles / San Pedro coastline.

The system compares a target day's weather profile against a library of historical days, identifies the most similar "analog" days, and uses their observed afternoon wind patterns to classify sea breeze likelihood and produce probabilistic wind forecasts for the 11:00–16:00 local time window.

## How It Works

### The Analog Forecasting Method

Sea breezes are thermally driven coastal winds that develop when land heats faster than the adjacent ocean. They follow recognizable meteorological patterns — specific combinations of morning wind speed, wind direction, temperature, and pressure tend to precede afternoon sea breeze onset.

The analog method exploits this by finding historical days whose morning conditions most closely resemble the target day. The afternoon wind behavior of those historical days then serves as the basis for the forecast.

### Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         TARGET DAY                                  │
│                                                                     │
│  GFS forecast (future dates)    or    Open-Meteo/ERA5 (past dates) │
│           ↓                                    ↓                    │
│     Hourly weather data: wind speed, direction, temp, pressure      │
│           ↓                                                         │
│     Feature extraction (08:00–16:00 local time window)              │
│           ↓                                                         │
│     9 daily features: morning wind speed/direction, reference-hour  │
│     values, afternoon max, speed increase, direction shift,         │
│     onshore wind fraction                                           │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                    Standardized Euclidean distance
                    (with optional GFS→ERA5 bias correction)
                                │
┌───────────────────────────────┴─────────────────────────────────────┐
│                     ERA5 HISTORICAL LIBRARY                         │
│                                                                     │
│  ~1,500 days (May–Sep 2015–2024) with precomputed feature vectors  │
│  Stored in PostgreSQL for fast retrieval                            │
│           ↓                                                         │
│     Rank all library days by distance to target                     │
│     Select top-K analogs (default K=20)                             │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    ↓                       ↓
          Sea Breeze Classification    Forecast Composite
          (3-indicator rules gate)     (from top-K analog afternoons)
                    │                       │
                    ↓                       ↓
          High / Medium / Low         Hourly 11:00–16:00:
          based on:                   - Median TWS + percentile bands
          - speed increase ≥ 1.5 m/s  - Circular mean TWD + spread
          - direction shift ≥ 25°     - Individual analog traces
          - onshore fraction ≥ 0.5
```

### Three Operating Modes

**Historical Analysis** — Select a past date. The app fetches weather data from Open-Meteo or ERA5, computes features, and ranks historical days by similarity. Shows which past days had the most similar morning weather and whether those days experienced sea breezes.

**Sea Breeze Forecast** — Select a future date (e.g., tomorrow). The app fetches GFS forecast data for the morning window, matches against the ERA5 historical library, and produces a probabilistic TWS/TWD forecast for the afternoon sailing window. If sea breeze probability is low, the system reports this and does not produce a forecast.

**Hindcast Validation** *(planned)* — Select a past date where both GFS and ERA5 data exist. Run the forecast pipeline using actual GFS morning data, then overlay the composite forecast against what ERA5 recorded actually happened. Produces error metrics (MAE, RMSE, circular MAE) for evaluating forecast skill.

### Data Sources

| Source | Role | Format |
|--------|------|--------|
| **ERA5** (Copernicus CDS) | Historical analog library (2015–2024) | GRIB via CDS API |
| **GFS** (NOAA) | Forecast input for future/recent dates | GRIB from NCAR RDA THREDDS |
| **Open-Meteo** | Fallback for both historical and forecast data | JSON API |
| **IEM ASOS** | Weather station observations (e.g., KLAX) | CSV |

### Feature Library

Rather than recomputing features from raw hourly data on every analysis, the app precomputes daily feature vectors for the entire ERA5 historical range and stores them in PostgreSQL. A background job fetches ERA5 data year-by-year, extracts features, and stores them with a configuration hash so that changes to the analysis window automatically invalidate stale entries.

### Bias Correction

GFS and ERA5 are different models with systematic biases. Before comparing a GFS forecast feature vector against ERA5 library vectors, the system computes per-feature mean bias from a 90-day overlap period and subtracts it. This prevents the analog ranking from being skewed by consistent model differences rather than genuine weather similarity.

## Tech Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, NumPy, xarray, cfgrib
- **Frontend:** TypeScript, Vite, Apache ECharts (vanilla — no framework)
- **Database:** PostgreSQL 16
- **Infrastructure:** Docker Compose (local dev), Railway (production)

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- A [Copernicus CDS account](https://cds.climate.copernicus.eu/) and API key (required for ERA5 data; optional if using Open-Meteo fallback)

## Getting Started

### 1. Clone and configure

```bash
git clone https://github.com/Marremeister/Weather_bachelor.git
cd Weather_bachelor
cp .env.example .env
```

Edit `.env` to add your CDS API key if you have one:

```
CDSAPI_KEY=your-key-here
```

### 2. Start the development environment

```bash
docker-compose up
```

This starts three services:

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:5175 | Vite dev server with hot reload |
| Backend API | http://localhost:8001 | FastAPI with auto-reload |
| PostgreSQL | localhost:5433 | Database |

On first startup, the backend runs Alembic migrations and seeds the default LA/San Pedro location and KLAX weather station.

### 3. Build the feature library

The ERA5 feature library powers the analog matching. You can trigger a library build from the application UI, or the app will fall back to Open-Meteo for historical data if no library is available.

### 4. Run an analysis

Open http://localhost:5175 in a browser. Select a location and date, choose Historical or Forecast mode, and click Run Analysis.

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, routing, startup seeding
│   │   ├── config.py            # Pydantic settings from .env
│   │   ├── database.py          # SQLAlchemy engine & sessions
│   │   ├── models/              # ORM models
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   ├── routers/             # API endpoints
│   │   └── services/            # Business logic & data providers
│   ├── tests/                   # pytest tests
│   ├── alembic/                 # Database migrations
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── main.ts              # App entry point & orchestration
│   │   ├── api.ts               # Backend API client
│   │   ├── types.ts             # TypeScript interfaces
│   │   ├── charts.ts            # ECharts visualizations
│   │   ├── dashboard.ts         # UI panels, tables, gauges
│   │   └── export.ts            # PNG/CSV/JSON export
│   └── package.json
├── docker-compose.yml           # Local dev orchestration
├── Dockerfile                   # Production multi-stage build
└── .env.example                 # Environment variable template
```

## API

The backend exposes a REST API under `/api`. When the backend is running, interactive documentation is available at:

- **Swagger UI:** http://localhost:8001/docs
- **ReDoc:** http://localhost:8001/redoc

Key endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Service and database health check |
| `/api/locations` | GET | List configured locations |
| `/api/weather/fetch` | POST | Fetch weather data for a location/date |
| `/api/weather` | GET | Query stored weather records |
| `/api/analysis/run` | POST | Trigger an analog analysis |
| `/api/analysis/{id}` | GET | Retrieve analysis results |
| `/api/classification` | GET | Sea breeze classification for a date |
| `/api/library` | GET | Feature library status |
| `/api/observations/fetch` | POST | Fetch station observations |
| `/api/observations` | GET | Query stored observations |

## Visualizations

The frontend renders a suite of ECharts visualizations:

- **Wind overlay** — True wind speed (line) and direction (scatter) on dual axes
- **Temperature & pressure** — Dual-axis time series
- **Wind roses** — Morning vs afternoon polar distributions
- **Feature radar** — Spider chart comparing target day vs analog mean across 9 features
- **Wind speed increase bars** — Afternoon ramp-up comparison across analogs
- **Direction shift lollipop** — Veering/backing comparison
- **Seasonal heatmap** — Calendar grid colored by sea breeze intensity across years
- **Distance histogram** — Distribution of analog distances with top-N highlighted
- **Analog overlay** — Target day vs top-N analog hourly curves
- **Forecast composite** — Probabilistic TWS/TWD with percentile bands
- **Bias correction panel** — Per-feature bias statistics

All charts and data tables support export to PNG, CSV, and JSON.

## Testing

```bash
# Run all backend tests
pytest backend/tests/

# Run a specific test file
pytest backend/tests/test_analog_service.py

# Run a specific test with verbose output
pytest backend/tests/test_analog_service.py::test_function_name -v
```

## Production Deployment

The production build uses a single multi-stage Docker image. Stage 1 builds the Vite frontend, stage 2 installs the Python backend, copies the built frontend into `static/`, runs Alembic migrations, and starts uvicorn. FastAPI serves the API at `/api/*` and the SPA at all other routes from a single container.

### Railway

The app is configured for deployment on [Railway](https://railway.app):

1. Link the GitHub repository — Railway auto-detects the root Dockerfile
2. Add a PostgreSQL plugin (auto-injects `DATABASE_URL`)
3. Set environment variables: `APP_ENV=production`, `CDSAPI_KEY`, and optionally `ALLOWED_ORIGINS`
4. Push to deploy

See [RAILWAY.md](RAILWAY.md) for detailed setup instructions.

### Local production testing

```bash
docker compose --profile prod up --build postgres app
# App available at http://localhost:8000
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@postgres:5432/seabreeze` | PostgreSQL connection string |
| `APP_ENV` | `development` | `development` or `production` |
| `ALLOWED_ORIGINS` | `http://localhost:5173,...` | CORS allowed origins (comma-separated) |
| `CDSAPI_URL` | `https://cds.climate.copernicus.eu/api` | Copernicus CDS API endpoint |
| `CDSAPI_KEY` | *(empty)* | CDS API key for ERA5 downloads |
| `ERA5_START_YEAR` | `2015` | First year of ERA5 library |
| `ERA5_END_YEAR` | `2024` | Last year of ERA5 library |
| `ERA5_MONTHS` | `05,06,07,08,09` | Months to include (May–Sep) |
| `WEATHER_CACHE_DIR` | `../data/cache` | Filesystem cache for API responses |
| `DEFAULT_LATITUDE` | `33.708965` | Default location latitude (San Pedro) |
| `DEFAULT_LONGITUDE` | `-118.268343` | Default location longitude |
| `DEFAULT_TIMEZONE` | `America/Los_Angeles` | Default location timezone |

See [.env.example](.env.example) for the full list.

## Roadmap

Stages 1–4 of the upgrade plan are complete. Remaining work:

- **Stage 5 — Weather station observations:** Fetch real observed wind data from IEM ASOS stations to validate forecasts against what actually happened. Basic station infrastructure is in place; validation metrics (MAE, onset time error, peak speed error) are next.
- **Stage 5.5 — Interactive hindcast validation:** Pick any past date, run the GFS-based forecast pipeline, and compare the composite prediction against actual ERA5 afternoon data with error metrics.
- **Stage 6 — Batch validation:** Run hindcast across all test days (May–Sep 2023–2024) to produce the thesis's core accuracy tables. Includes temporal-split and leave-one-out evaluation methods, gate sensitivity analysis, and source-stratified metrics.
- **Stage 7 — ML calibration:** Train logistic regression / gradient boosted trees on top of analog features to improve sea breeze probability and forecast accuracy. Optional enhancement layer — the analog method continues to work without it.
- **Stage 8 — Live forecast mode:** Automated daily forecast trigger, live station data polling, real-time forecast-vs-observation comparison, and forecast history browsing.

See [THESIS_DATA_SOURCE_UPGRADE_PLAN.md](THESIS_DATA_SOURCE_UPGRADE_PLAN.md) for full details on each stage.
