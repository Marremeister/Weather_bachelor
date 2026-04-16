# Sea Breeze Analog — Backend Deep Dive

This is a FastAPI backend for a bachelor thesis project that forecasts sea breeze events by finding historical days ("analogs") that look meteorologically similar to a target day, then using what actually happened on those past days as a probabilistic forecast for the target day.

---

## 1. 30‑Second Overview

```
Browser ── HTTP ──► FastAPI routers ──► Services (business logic)
                                          │
                                          ├─► SQLAlchemy models ──► PostgreSQL
                                          ├─► Weather providers ──► Open‑Meteo / GFS / ERA5 / IEM
                                          └─► Filesystem cache (JSON + GRIB2 files)
```

The backend has four main jobs:

1. **Ingest weather data** from multiple sources (historical reanalysis + forecasts + station obs), normalize it, and cache it.
2. **Extract daily features** (morning mean wind, afternoon max, onshore fraction, direction shift, etc.) from hourly records.
3. **Rank analogs** — given a target day, compute a weighted L2 distance in feature space to every day in a precomputed library, return the top‑N nearest neighbors.
4. **Build a probabilistic forecast composite** from those analog days and optionally validate it against actuals.

---

## 2. Directory Layout

```
backend/
├── app/
│   ├── main.py            ← FastAPI app + router registration
│   ├── config.py          ← env-driven settings (Pydantic)
│   ├── database.py        ← SQLAlchemy engine, Session, Base
│   ├── models/            ← ORM tables (10 files)
│   ├── schemas/           ← Pydantic request/response DTOs (6 files)
│   ├── routers/           ← HTTP endpoints (7 files)
│   └── services/          ← Business logic (~14 files, most of the code lives here)
├── alembic/versions/      ← DB migrations (001–008)
└── tests/
```

The rule of thumb: **routers do I/O validation only, services do the work, models describe tables, schemas describe the wire format.**

---

## 3. Infrastructure Layer

### `main.py`
Creates the `FastAPI` app, installs CORS, and mounts seven routers under `/api/*`:
`locations`, `weather`, `analysis`, `classification`, `library`, `observations`, `validation`.
On startup it seeds a default Location (LA/San Pedro) and a default WeatherStation (KLAX). In production it also serves the built frontend as static files with SPA fallback.

### `config.py`
A `pydantic_settings.BaseSettings` class reading `.env`. Important knobs:
- `database_url` — Postgres connection
- `weather_cache_dir`, `grib_cache_dir` — filesystem cache roots
- `era5_*`, `gfs_*` — year ranges, model cycle hours, publish lag, analysis window hours (e.g. local 08–16)
- `cdsapi_url`, `cdsapi_key` — Copernicus Data Store API creds
- `bias_overlap_days` — days used to calibrate forecast‑vs‑historical biases

### `database.py`
Standard SQLAlchemy setup: engine, `SessionLocal`, `Base`, and a `get_db()` FastAPI dependency that yields a session and closes it.

---

## 4. Data Model (`app/models/`)

Each file defines one SQLAlchemy ORM class mapping to one Postgres table.

| Model | Purpose |
|---|---|
| `Location` | Named point (lat, lon, timezone). Everything is scoped per location. |
| `WeatherStation` | Surface station metadata (e.g. KLAX) for ASOS observations. |
| `WeatherRecord` | Hourly wind/temp/pressure/cloud at a location from a given `source` and `valid_time_utc`. Also records `model_run_time` / `forecast_hour` / `model_name` for forecasts. Unique on `(location_id, source, valid_time_utc)`. |
| `Observation` | Hourly METAR-style readings at a WeatherStation. Unique on `(station_id, observation_time_utc)`. |
| `DailyFeature` | Precomputed per-day feature vector stored as JSONB plus a `feature_config_hash` so caches invalidate when the analysis window changes. |
| `LibraryBuildJob` | Tracks progress of the background job that fills `DailyFeature`. |
| `AnalysisRun` | One user-triggered analog analysis (target date, mode, top‑N). Also stores the resulting `forecast_composite` JSON. |
| `AnalogResult` | A row per neighbor day linked to an `AnalysisRun` (rank, distance, features). |
| `SourceBiasCorrection` | Per-feature (mean, std) difference between a forecast source and a historical reference, used to debias future forecasts. |
| `ValidationRun` | Batch hindcast evaluation — stores aggregate metrics, per-gate sensitivity, per-source stratification, and per-day results as JSON. |

---

## 5. Wire Schemas (`app/schemas/`)

Pydantic models that define exactly what the API accepts and returns.

- **`location.py`** — trivial CRUD DTOs.
- **`weather.py`** — request/response for `/weather/fetch`.
- **`observation.py`** — `StationResponse`, `ObservationFetchRequest/Response`, `ObservationResponse`, and `ValidationMetricsResponse` (TWS MAE, circular TWD MAE, peak speed error, onset hour error).
- **`features.py`** — `AnalysisWindow` (configurable morning/afternoon hours, onshore sector bounds, per‑group feature weights), `DailyFeatures`, `SeaBreezeClassification`, plus response DTOs for classification / seasonal heatmap / distance histogram panels.
- **`analog.py`** — `AnalysisRequest`, `AnalogCandidate`, `AnalysisRunResponse`, the rich `AnalysisRunDetailResponse`, and `ForecastCompositeHour` (median/p10/p25/p75/p90 TWS + circular mean/std + 75th arc radius for direction).
- **`validation.py`** — `ValidationRunRequest` (method ∈ `temporal_split`/`leave_one_out`, buffer days, top‑N, optional date windows, optional source overrides). `AggregateMetrics` carries TP/FP/TN/FN, precision/recall/F1, TWS MAE/RMSE, circular TWD MAE, peak/onset errors, and a `skill_score`. `GateSensitivityEntry` sweeps the classification threshold (≥1, ≥2, ≥3). `SourceStratificationEntry` breaks metrics down by forecast source. `ValidationDayResult` is one row per test day. `ValidationRunStatusResponse` / `ValidationRunResponse` / `ValidationRunSummary` are the detail/progress/list views.

---

## 6. Provider Abstraction (`services/*_provider.py`)

Weather data enters the system through pluggable providers. Two small abstract interfaces let the rest of the app stay source‑agnostic.

### `weather_provider.py`
Defines:
- `HourlyRecord` dataclass — normalized hourly row (UTC + local time, TWS, TWD, temp, pressure, cloud, and optional forecast provenance).
- `FetchResult` dataclass — `records` + `raw_payload` (saved to filesystem cache).
- `WeatherProvider` ABC with a `source_name` property and `fetch(lat, lon, start_date, end_date, timezone) -> FetchResult`.

Concrete implementations:

| Provider | Role |
|---|---|
| `OpenMeteoProvider` | Historical archive via Open‑Meteo (free fallback for ERA5). |
| `OpenMeteoForecastProvider` | Live forecast via Open‑Meteo. |
| `Era5Provider` | Copernicus CDS API — downloads GRIB2 per year, falls back to `OpenMeteo models=era5` if CDS is unavailable. |
| `GfsForecastProvider` | Downloads GFS GRIB2 straight from NCAR RDA THREDDS, picks the latest cycle respecting `gfs_publish_lag_hours`, and extracts the forecast hours that hit the local 08–16 analysis window. |
| `GfsOpenMeteoProvider` | Fallback GFS via Open‑Meteo (`models=gfs_seamless`). |

### `gfs_grib_utils.py`
Shared helpers for parsing GRIB2 files with cfgrib/xarray: `TARGET_SPECS` describes which GRIB variables map to which `HourlyRecord` fields; `_score_da_for_target` + `_open_target_da` try multiple cfgrib filter sets because GRIB files are heterogeneous; `select_point_dataarray` does nearest‑point extraction; wind math converts U/V to meteorological speed/direction; a magic-number check rejects HTML error pages masquerading as GRIB.

### `observation_provider.py` + `iem_asos_provider.py`
Same pattern for ground-station data. `IemAsosProvider` hits the Iowa Environmental Mesonet CSV API, converts knots → m/s and °F → °C at the provider boundary, and returns `HourlyObservation` rows.

---

## 7. Caching Strategy

Every weather source uses **three tiers**:

1. **Database** (Postgres `weather_records` / `observations`). `weather_service._count_records_in_range()` (or `_count_existing()` for obs) asks: "do we already have ≥90% of the expected hourly rows for this window?" If yes → return early. GFS also checks staleness via `_gfs_cache_is_fresh()` on the most recent `model_run_time`.
2. **Filesystem JSON** (`weather_cache_dir`) keyed by `(source, lat, lon, start, end)`. If DB is empty but a JSON payload exists, `parse_open_meteo_response` rehydrates `HourlyRecord`s without touching the network.
3. **API call** through the provider. Results are written to filesystem cache *and* upserted into the DB.

Upserts use PostgreSQL `INSERT ... ON CONFLICT`: forecasts use `DO UPDATE` (newer `model_run_time` wins), historical reanalysis uses `DO NOTHING`. Batch size is capped at 4,000 rows per statement to stay under the 65k bind-param limit.

---

## 8. Core Business Logic (`app/services/`)

### `feature_service.py`
`compute_daily_features(records, window)` slices one day's hourly records into a morning window and an afternoon window, computes:
- morning mean TWS and mean TWD (circular)
- afternoon max TWS
- reference-hour TWS/TWD
- direction shift (circular) morning → afternoon
- onshore fraction over the afternoon window using the configured onshore sector
- a derived "sea-breeze-likelihood" composite

`compute_feature_config_hash(window)` produces a deterministic hash used as a cache key in `DailyFeature.feature_config_hash`, so changing the `AnalysisWindow` invalidates the library automatically.

### `classification_service.py`
Three boolean "gates":
- **Speed gate** — afternoon_max − morning_mean ≥ threshold (default 1.5 m/s)
- **Direction gate** — circular shift ≥ threshold (default 25°)
- **Onshore gate** — onshore fraction ≥ threshold (default 0.5)

`count_true ∈ {0,1,2,3}` maps to `none / low / medium / high`. This is both the classifier output for single days and the "truth label" used in validation.

### `analog_service.py`
`rank_analogs(target_features, library, weights)`:
1. Compute mean/std of each feature across the library → z-score normalize.
2. Apply per-group weights (morning / reference / afternoon / derived).
3. Compute weighted L2 distance between target and every library day.
4. Return the top‑N smallest-distance days as `AnalogCandidate`s.

Temporal exclusion (for validation) filters out `(month, day)` pairs within `buffer_days` of the target.

### `forecast_service.py`
`build_composite(analog_days_hourly_records)` aggregates the top‑N analogs' hourly records into per‑hour statistics over `FORECAST_HOURS = 11..16`:
- p10/p25/p50(median)/p75/p90 of TWS
- circular mean + circular std of TWD
- 75th‑percentile arc radius (direction spread)

This is the probabilistic forecast the user ultimately sees.

### `bias_service.py`
`calibrate_bias(forecast_source, historical_source, overlap_days)` fetches both sources over an overlapping past window (clamped to the ERA5 season), computes per-feature `(mean, std)` of `forecast − historical` differences, and upserts a `SourceBiasCorrection`. Live-only providers are rejected for the historical role.

### `weather_service.py`
Orchestrates fetch-with-caching, provider registry (`get_provider(source_name)`), and the 3-tier logic described in §7. Exposes `fetch_weather(...)` that the routers call.

### `observation_service.py`
Analogous to `weather_service` but for METAR/ASOS stations. Also contains `compute_validation_metrics(...)` which pairs forecast-composite hours with observations by local hour and returns `ValidationMetrics`: TWS MAE/max, circular TWD MAE/max, peak speed comparison, and onset‑hour detection (first hour with onshore sector 180–260° and speed > 3 m/s). This is used by the drill-down "compare one day vs observations" panel.

### `library_service.py`
Background task `build_feature_library(...)`: iterates chunks of the ERA5 season, calls `fetch_weather` for each chunk, groups hourly records by date, runs `compute_daily_features`, and upserts `DailyFeature` rows tagged with `feature_config_hash`. Progress is streamed through `LibraryBuildJob` (status, processed/total days, error message).

### `validation_service.py`
Background task `run_batch_validation(...)` powering the `/validation/run` endpoint:
- `_build_exclusion_set(test_date, buffer_days)` — yields `(month, day)` tuples within ±buffer across all years, plus the test date itself, to prevent leakage.
- `_run_hindcast_for_day(date)` — uses ERA5 as *both* "forecast features" and "actual outcome" (a true hindcast). Ranks analogs from the filtered library, builds the composite, computes classification gate result, and computes continuous errors (TWS MAE/RMSE, circular TWD MAE, peak-speed error + bias, onset error) on sea-breeze days only.
- `_compute_climatology_baseline()` — single bulk query + in-memory grouping, used to compute the skill score.
- `_compute_gate_sensitivity()` — sweeps the classifier threshold at `≥1`, `≥2`, `≥3` and reports precision/recall/F1 plus conditional TWS MAE/RMSE per gate level.
- `_compute_source_stratification()` — groups per-day results by the forecast source actually used.

Supports `temporal_split` (train on one window, test on another) and `leave_one_out` (each day uses all others as library). Results land in `ValidationRun.aggregate_metrics / gate_sensitivity / source_stratification / per_day_results`.

---

## 9. HTTP Surface (`app/routers/`)

All routers are mounted under `/api`.

| Router | Key endpoints | What they do |
|---|---|---|
| `locations.py` | CRUD under `/api/locations` | Manage analysis locations. |
| `weather.py` | `POST /api/weather/fetch` | Trigger `fetch_weather` for a `(location, source, date range)`. Returns counts + `cached` flag. |
| `library.py` | `POST /api/library/build`, `GET /api/library/status/{job_id}` | Kick off and monitor the background feature-library build. |
| `observations.py` | Station fetch + per-day validation metrics endpoints | Ingest ASOS rows and compute forecast-vs-obs metrics. |
| `analysis.py` | `POST /api/analysis/run`, `GET /api/analysis/{run_id}` | Run an analog analysis (historical or forecast mode) and read back the detail payload including `AnalogCandidate`s and `ForecastCompositeHour`s. |
| `classification.py` | Sea breeze panel, seasonal heatmap, distance distribution | Derived visualizations over the library. |
| `validation.py` | `POST /api/validation/run`, status/result endpoints | Launch the background batch validation and retrieve progress + final metrics. |

---

## 10. Background Task Lifecycle

Long jobs are dispatched via FastAPI's `BackgroundTasks`. The pattern is the same everywhere:

1. Router validates the request, creates a row (`LibraryBuildJob`, `ValidationRun`) with `status="pending"`, returns the row ID immediately.
2. Background task opens its own DB session, switches status to `running`, iterates, periodically commits progress (`completed_days`, etc.), and finally writes `finished_at`, `status="completed" | "error"`, and any `error_message`.
3. Frontend polls a `GET .../status/{id}` endpoint until completion, then fetches the full result.

---

## 11. End-to-End User Journey

Here's how a typical "analyze August 12, 2024" request flows through the system:

1. **Build library** (one-time per config): `POST /api/library/build` → `library_service.build_feature_library` loops ERA5 years, calls `weather_service.fetch_weather` (hits DB → filesystem → Copernicus CDS), groups by day, runs `feature_service.compute_daily_features`, upserts `DailyFeature` rows tagged with `feature_config_hash`.
2. **Optional bias calibration**: for a forecast source, `bias_service.calibrate_bias` fetches overlapping days from both forecast and ERA5, stores per-feature `(mean, std)` diffs in `SourceBiasCorrection`.
3. **Analysis run** (`POST /api/analysis/run`): router validates `AnalysisRequest`, `analog_service.run_analog_analysis` fetches the target day's weather (via `weather_service`), computes its features, loads the matching `DailyFeature` library rows, z-scores + weights, ranks top‑N neighbors, `forecast_service.build_composite` aggregates their hourly records into per-hour percentiles, and everything is persisted into `AnalysisRun` + `AnalogResult` + `forecast_composite` JSON.
4. **Classification panel**: `classification_service` reads the target day's features and computes gate booleans + count → `SeaBreezePanelResponse`.
5. **Optional observation overlay**: `observations.py` → `observation_service.compute_validation_metrics` pairs the composite with same-day ASOS obs and returns TWS MAE, circular TWD MAE, peak/onset errors for the drill-down UI.
6. **Optional batch validation**: `POST /api/validation/run` → `validation_service.run_batch_validation` hindcasts every day in the test window using ERA5-as-truth, computes classification metrics + continuous errors + gate sensitivity + source stratification + skill score against climatology, and persists everything on the `ValidationRun` row.

That's the backend in full: a pipeline of **providers → cache → features → analogs → composite → validation**, with each layer behind a clean abstraction so new data sources, new features, or new evaluation methods can be plugged in without rewriting the rest.
