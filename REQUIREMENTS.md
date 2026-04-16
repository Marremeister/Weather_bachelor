# Requirements Specification — Sea Breeze Analog

Bachelor thesis project. This document captures the functional and non-functional requirements the system is built to satisfy, along with the constraints under which it operates and the criteria used to judge whether each requirement is met.

---

## 1. Purpose and Scope

### 1.1 Purpose
Provide a reproducible, web-based tool for analyzing and forecasting afternoon sea breeze events along a coastal location using the **analog forecasting method** — identifying historical days with similar morning meteorology and using their observed afternoon wind behavior as a probabilistic forecast for the target day.

### 1.2 Scope (in)
- Historical analog analysis for any date within the ERA5 library range (May–Sep, 2015–2024).
- Sea breeze forecast for near-future dates using GFS morning conditions and ERA5 analogs.
- Sea breeze classification (high / medium / low / none) based on three independent indicators.
- Probabilistic forecast composites (percentile bands + circular direction statistics) over the 11:00–16:00 local window.
- Batch hindcast validation producing aggregate skill metrics, gate sensitivity, and source stratification.
- Observation-based validation against IEM ASOS station data.
- Data export (PNG, CSV, JSON) for every visualization.

### 1.3 Scope (out)
- Sub-hourly resolution (everything is hourly).
- Areas other than the configured coastal point (default: Los Angeles / San Pedro, KLAX).
- Non-sea-breeze meteorological phenomena (frontal passages, Santa Ana events, precipitation forecasting).
- Mobile-first UI (desktop browsers are the primary target).
- Multi-tenant user accounts / authentication (single-user thesis deployment).

### 1.4 Stakeholders
| Role | Interest |
|---|---|
| Thesis author | Primary developer and researcher. |
| Thesis supervisor | Reviews methodology and validation results. |
| External users | Sailors, coastal meteorology students, regatta organizers exploring the tool. |

---

## 2. Functional Requirements

Each requirement has an ID (`FR-x`), a priority (M = Must, S = Should, C = Could), and acceptance criteria (AC).

### 2.1 Data Ingestion
- **FR-1 (M) — Historical ingestion from ERA5.** Fetch hourly single-level ERA5 data (wind u/v, temperature, pressure, cloud cover) via the Copernicus CDS API.
  - AC: Given valid CDS credentials and a date within the ERA5 range, the system stores ≥90% of expected hourly rows in `weather_records` under `source="era5"`.
- **FR-2 (M) — Forecast ingestion from GFS.** Fetch GFS GRIB2 forecasts from NCAR RDA THREDDS, selecting the latest cycle respecting the publish lag.
  - AC: `source="gfs"` rows carry non-null `model_run_time`, `forecast_hour`, and `model_name`.
- **FR-3 (M) — Open-Meteo fallback.** When CDS or NCAR RDA is unavailable, transparently fall back to Open-Meteo's equivalent endpoints (`models=era5` or `models=gfs_seamless`).
  - AC: Fetch succeeds and records are upserted even when the primary source is unreachable, with provenance recorded in `source`.
- **FR-4 (M) — Station observations from IEM ASOS.** Fetch hourly METAR-style wind/temperature/pressure observations for the configured weather station.
  - AC: Observations are normalized to m/s and °C and stored unique per `(station_id, observation_time_utc)`.
- **FR-5 (S) — Three-tier caching.** For every fetch, check database → filesystem JSON/GRIB cache → remote API, in that order.
  - AC: A repeat fetch over a fully cached window performs zero network calls and returns with `cached=True`.

### 2.2 Feature Extraction
- **FR-6 (M) — Daily feature vector.** Compute for each day: morning mean wind speed, morning mean wind direction (circular), reference-hour values, afternoon max, speed increase, direction shift (circular), onshore fraction, and a derived composite.
  - AC: Feature output is deterministic given the same hourly input and `AnalysisWindow`.
- **FR-7 (M) — Configurable analysis window.** Morning/afternoon hour ranges, onshore sector bounds, and per-group feature weights are user-configurable.
  - AC: Changing the window invalidates prior `DailyFeature` rows via `feature_config_hash` mismatch without manual intervention.
- **FR-8 (M) — Precomputed feature library.** Background job extracts and persists features for the full ERA5 season range (May–Sep, 2015–2024).
  - AC: `LibraryBuildJob` reports progress (`completed_days` / `total_days`) and terminates with `status="completed"` on success.

### 2.3 Analog Ranking
- **FR-9 (M) — Z-score normalization.** Standardize each library feature by its mean and standard deviation before distance computation.
  - AC: Per-feature normalization statistics are derived from the actively used library slice (not hardcoded).
- **FR-10 (M) — Weighted L2 distance.** Apply per-group weights (morning / reference / afternoon / derived) when computing distance.
  - AC: Changing a group weight measurably reorders the returned top-N.
- **FR-11 (M) — Top-N retrieval.** Return the N closest analog days (default 20, configurable 1–50).
  - AC: Results are sorted ascending by distance; ties broken deterministically.
- **FR-12 (S) — Temporal exclusion.** When ranking for validation, exclude `(month, day)` tuples within ±`buffer_days` of the target and the target day itself.
  - AC: No analog in the returned set falls within the exclusion window.

### 2.4 Classification and Forecast Composite
- **FR-13 (M) — Three-gate classifier.** Speed increase ≥ 1.5 m/s, direction shift ≥ 25°, onshore fraction ≥ 0.5. Count true → none/low/medium/high.
  - AC: Thresholds are constants referenced in one place; changing them changes only the classifier output.
- **FR-14 (M) — Probabilistic composite.** For hours 11–16, emit p10/p25/p50/p75/p90 TWS plus circular mean, circular std, and 75th arc radius for TWD, aggregated across the top-N analog afternoons.
  - AC: Percentile ordering holds (`p10 ≤ p25 ≤ median ≤ p75 ≤ p90`) for every output hour.
- **FR-15 (S) — Bias correction.** For a forecast source, compute per-feature (mean, std) of `forecast − historical` over a configurable overlap window; subtract mean before ranking.
  - AC: Stored in `SourceBiasCorrection` and applied transparently during ranking.

### 2.5 Validation
- **FR-16 (M) — Batch hindcast.** For a user-defined test window, run the full pipeline day-by-day, using ERA5 as both input and ground truth.
  - AC: Produces `aggregate_metrics`, `gate_sensitivity` (≥1, ≥2, ≥3), `source_stratification`, and `per_day_results` on `ValidationRun`.
- **FR-17 (M) — Two evaluation methods.** Support `temporal_split` (train window ≠ test window) and `leave_one_out` (each day uses all others).
  - AC: Method is selectable via the API payload and drives library filtering.
- **FR-18 (M) — Classification + continuous metrics.** Compute TP/FP/TN/FN + precision/recall/F1 + TWS MAE/RMSE + circular TWD MAE + peak speed error/bias + onset error (on sea breeze days).
  - AC: Metrics are reproducible across runs given the same inputs and configuration.
- **FR-19 (S) — Climatology skill score.** Benchmark MAE against a climatology baseline of daily afternoon means and report `skill_score = 1 − MAE_model / MAE_climatology`.
  - AC: Skill score is bounded above by 1.0 and is negative if the model is worse than climatology.
- **FR-20 (S) — Observation overlay.** For a single day, pair the forecast composite with ASOS observations by local hour and report TWS MAE/max, circular TWD MAE, peak speed error, and onset hour error.
  - AC: Returned only for days where both the composite and observations exist.

### 2.6 User Interface
- **FR-21 (M) — Date + mode selection.** User selects a location, target date, and mode (Historical / Forecast / Validation).
  - AC: Invalid date/mode combinations are rejected client-side with a clear message.
- **FR-22 (M) — Visualizations.** Wind overlay, temperature/pressure, wind roses, feature radar, speed increase bars, direction-shift lollipop, seasonal heatmap, distance histogram, analog overlay, forecast composite, bias panel, validation detail.
  - AC: Every chart renders without error for representative inputs and matches the underlying data.
- **FR-23 (M) — Export.** Every chart and table is exportable to PNG and/or CSV/JSON.
  - AC: Export produces a non-empty, well-formed file.
- **FR-24 (S) — Progress reporting.** Long-running jobs (library build, validation) expose progress via polling endpoints.
  - AC: UI shows `completed / total` and updates without page reload.

---

## 3. Non-Functional Requirements

### 3.1 Performance
- **NFR-1** — A warm analysis run (library built, target day cached) returns in < 2 s on a developer laptop.
- **NFR-2** — Weather fetches avoid network round-trips when cached data covers ≥ 90% of the expected hourly rows.
- **NFR-3** — Upserts batch rows at ≤ 4,000 per statement to respect PostgreSQL's 65,535 bind-parameter limit.

### 3.2 Reliability
- **NFR-4** — Primary data source failures fall back to secondary sources without user intervention (ERA5 → Open-Meteo; GFS GRIB → Open-Meteo GFS).
- **NFR-5** — Background jobs persist state so a crash leaves `LibraryBuildJob` / `ValidationRun` in a non-ambiguous status with an error message.
- **NFR-6** — GRIB downloads validated by magic-number check to reject HTML error pages served as GRIB.

### 3.3 Reproducibility
- **NFR-7** — Feature computation is pure and deterministic given `(hourly_records, AnalysisWindow)`.
- **NFR-8** — Library caches are keyed by `feature_config_hash`, so configuration changes cannot silently reuse stale features.
- **NFR-9** — Alembic migrations are the single source of truth for the schema; every change ships a migration.

### 3.4 Maintainability
- **NFR-10** — Routers contain only I/O and validation; all business logic lives in `app/services/`.
- **NFR-11** — New weather sources plug in as subclasses of `WeatherProvider` without touching service code.
- **NFR-12** — All dependencies declared in `backend/pyproject.toml` (primary) and `backend/requirements.txt` (convenience).

### 3.5 Security and Privacy
- **NFR-13** — Secrets (CDS API key, database URL) are loaded from `.env`; no secret is committed to Git.
- **NFR-14** — CORS origins are configurable via `ALLOWED_ORIGINS`.
- **NFR-15** — The app stores no personal user data.

### 3.6 Portability
- **NFR-16** — `docker-compose up` starts the full stack on any machine with Docker, without additional setup beyond a `.env` file.
- **NFR-17** — A single multi-stage `Dockerfile` produces a deployable image for Railway.

---

## 4. Data Requirements

| Item | Requirement |
|---|---|
| Historical range | 2015-05-01 through 2024-09-30 (ERA5 season window). |
| Temporal resolution | 1 hour. |
| Spatial resolution | Nearest grid point to the configured location. |
| Units | SI (m/s, °C, hPa, degrees true). Conversions happen at provider boundaries. |
| Timezone | Records store both UTC and location-local timestamps. |
| Retention | No hard expiry; caches may be cleared manually. |

---

## 5. External Interfaces

| Interface | Purpose | Constraint |
|---|---|---|
| Copernicus CDS API | ERA5 download | Requires user-supplied API key; rate-limited. |
| NCAR RDA THREDDS | GFS GRIB2 download | Public but rate-limited; may return HTML errors. |
| Open-Meteo | Fallback for ERA5 and GFS | Public, no key required; daily rate limits. |
| IEM ASOS | Station observation CSV | Public, no key required. |
| PostgreSQL 16 | Primary datastore | Connection via `DATABASE_URL`. |
| Browser (desktop) | UI | Chromium-based browsers officially supported. |

---

## 6. Constraints and Assumptions

- Python 3.12 or newer on the backend.
- PostgreSQL 16 for JSONB + `ON CONFLICT` semantics.
- The deployment target is a single container (Railway) — no horizontal scaling or worker pools.
- `cfgrib` / `eccodes` GRIB support assumes libeccodes is installed in the runtime image.
- Users with no Copernicus account can still operate the app using Open-Meteo fallbacks, at reduced data quality.

---

## 7. Acceptance Criteria (Summary)

The project is considered successfully delivered when:

1. A developer can clone the repo, fill in `.env`, run `docker-compose up`, and reach the UI at `http://localhost:5175` with a seeded default location.
2. The feature library can be built end-to-end for the full ERA5 range from the UI.
3. Historical analysis and forecast modes both produce analog rankings and composite forecasts consistent with the thesis notebook (`SeaBreeze_v5_point_analog.ipynb`) baseline.
4. A batch validation over a representative test window completes without errors and produces metric tables matching the thesis report's figures.
5. The full test suite (`pytest backend/tests/`) passes.
6. Export works for every chart and table.
7. The production Docker image builds and runs on Railway with `DATABASE_URL`, `CDSAPI_KEY`, and `APP_ENV=production` supplied.

---

## 8. Traceability

Each requirement ID in this document corresponds to one or more modules in the codebase. For an architectural mapping, see [BACKEND_ARCHITECTURE.md](BACKEND_ARCHITECTURE.md). For stage-by-stage delivery plans, see [THESIS_DATA_SOURCE_UPGRADE_PLAN.md](THESIS_DATA_SOURCE_UPGRADE_PLAN.md) and [WEBAPP_IMPLEMENTATION_PLAN.md](WEBAPP_IMPLEMENTATION_PLAN.md).
