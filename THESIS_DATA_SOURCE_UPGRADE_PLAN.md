# Sea Breeze Analog Forecasting Upgrade Plan

## Purpose

This plan upgrades the working sea breeze analysis app into an **operational analog forecasting system**.

The initial webapp (phases 1-9) proves the core workflow:

- FastAPI backend with PostgreSQL
- Open-Meteo weather provider with caching
- daily feature engineering with circular wind math
- analog matching via standardized Euclidean distance
- rules-based sea breeze classification
- interactive TWD/TWS charts and export

This upgrade plan changes the app from a backward-looking historical analysis tool into a **forward-looking forecast system**. The primary use case becomes:

> Given a future day (e.g., tomorrow), use GFS forecast data to find similar historical days in the ERA5 archive, determine whether a sea breeze is likely, and if so, produce a TWD and TWS forecast for the 11:00-16:00 sailing window.

## Target Workflow

This matches the client's intended pipeline:

```text
1. Fetch GFS forecast for the target day (tomorrow)
2. Extract GFS features (morning wind, temperature, pressure, etc.)
3. Compare against historical ERA5 days
4. Select most similar analog days
5. Calculate sea breeze probability
   - Low  -> eliminate case, no forecast produced
   - High -> continue
6. Build forecast from analog ERA5 days' 11:00-16:00 wind data
7. Compare forecast against weather station observations (when available)
8. Evaluate accuracy and improve with ML
9. Produce final TWD/TWS forecast for 11:00-16:00
```

## Guiding Principles

- Do not break the existing app. The current Open-Meteo historical analysis mode must keep working.
- Add a separate **forecast mode** alongside the existing analysis mode.
- Add data sources behind the existing `WeatherProvider` interface.
- Keep the frontend, database schema, and charts mostly stable; extend rather than replace.
- Each stage should leave the app runnable and deployable.

## What Already Exists

These components from phases 1-9 are reusable:

- `WeatherProvider` abstract base class (`weather_provider.py`)
- `OpenMeteoProvider` for development and fallback (`open_meteo_provider.py`)
- `FeatureService` with configurable analysis windows and circular math (`feature_service.py`)
- `AnalogService` with standardized Euclidean distance matching (`analog_service.py`)
- `ClassificationService` with rules-based sea breeze detection (`classification_service.py`)
- `WeatherService` with 3-tier caching: PostgreSQL, filesystem, API (`weather_service.py`)
- Database models: `Location`, `WeatherRecord`, `AnalysisRun`, `AnalogResult`
- Frontend: ECharts wind plots, analog tables, export functionality
- Docker Compose with PostgreSQL, backend, frontend

## Stage 1: Source Metadata And Forecast Mode Skeleton ✅ COMPLETED

> **Scope note:** This stage is intentionally minimal scaffolding. It adds no new data sources. Its purpose is to prepare database schema and API contracts for Stages 2-4.

### Purpose

Prepare the app for multiple data sources and add the concept of a forecast run that targets a future day.

### Implementation Tasks

- Add explicit `source` labels throughout the backend API responses, frontend charts, and exports.
- Add a `mode` field to `AnalysisRun`: `"historical"` (current behavior) or `"forecast"` (new).
- Add a `forecast_source` and `historical_source` field to `AnalysisRun` to record which provider was used for each role.
- Update the analysis request schema to accept `mode`, `forecast_source`, and `historical_source`.
- In forecast mode, the `target_date` can be a future date. The backend should not reject future dates.
- Add frontend mode selector: radio buttons ("Historical Analysis" / "Sea Breeze Forecast") at top of analysis form.
  - Historical mode: past dates only, user-configurable historical range (unchanged behavior).
  - Forecast mode: future dates allowed, historical range auto-set to library range (read-only), source labels shown as read-only.
  - `currentMode` variable in `main.ts` drives conditional rendering.
- Keep the existing historical analysis working unchanged when mode is `"historical"` or omitted.

### Acceptance Checks

- Existing historical analysis works exactly as before.
- A forecast-mode run can be created (even if it falls back to Open-Meteo for now).
- All outputs label their data source.
- The `AnalysisRun` record stores which mode and sources were used.
- A forecast-mode run stores `mode='forecast'`, `forecast_source='open_meteo'` (placeholder), `historical_source='open_meteo'` in the database. The frontend toggle is visible.

## Stage 2: GFS Forecast Provider ✅ COMPLETED

### Purpose

Add a provider that fetches GFS forecast data for future days. This is the **input** to the analog matching: it describes what tomorrow's weather is expected to look like.

### Role In The Method

GFS data represents the forecast situation. The app extracts morning features from the GFS forecast (wind speed, wind direction, temperature, pressure) and uses those features to search for similar historical days.

### Data Source Options

Option A (recommended — matches the existing notebook):

- GFS 0.25° GRIB2 files from NCAR RDA THREDDS (`https://thredds.rda.ucar.edu/thredds/fileServer/files/g/d084001/{year}/{yyyymmdd}/gfs.0p25.{yyyymmdd}{cycle}.f{fhour}.grib2`). Parse with cfgrib/xarray, extract nearest grid point. The notebook (`SeaBreeze_v5_point_analog.ipynb`) already implements this pipeline with robust multi-level GRIB variable scoring.

Option B (simpler fallback):

- Open-Meteo Forecast API (`https://api.open-meteo.com/v1/forecast`) with `&models=gfs_seamless`. Returns JSON — no GRIB handling. Useful for rapid prototyping or if RDA is temporarily unavailable.

The provider interface is the same either way. Start with Option A to match the validated notebook pipeline; fall back to Option B if needed.

### Data Needed

Minimum hourly or 3-hourly forecast fields:

- wind speed at 10 m (or U/V components to derive it)
- wind direction at 10 m (or U/V components)
- temperature at 2 m
- mean sea level pressure, if available
- cloud cover, if available

**Unit normalization:** ERA5 returns pressure in Pa (~101325) and temperature in K. GFS GRIB messages may use Pa or hPa for pressure depending on the level type. The notebook's `TARGET_SPECS` plausibility checks assume Pa (valid range 70000–110000). Normalize all providers to consistent units (Pa for pressure, K for temperature, m/s for wind) before storing in `weather_records`. Convert to °C only in derived features (`site_t2m_C = t2m - 273.15`). GFS longitude uses 0–360° convention; convert to -180–180° using the notebook's `convert_lon_360_to_180()` before point extraction.

### Forecast Hour Selection

The GFS 00Z run is the primary cycle. The analog match hour is 09:00 local time in Los Angeles (UTC-7 in summer = 16:00 UTC). The notebook downloads forecast hours f015 and f018, which give valid times at 15:00 UTC and 18:00 UTC — corresponding to 08:00 and 11:00 local time. This brackets the 09:00 match hour.

To get data at the match hour, interpolate linearly between the two bracketing forecast steps, or use the nearest available step (f015 → 08:00 local, 1 hour before match). The choice should be configurable via `GFS_FORECAST_HOURS` (default: `["015", "018"]`) and `ANALOG_MATCH_LOCAL_HOUR` (default: `9`).

For locations in different time zones, the forecast hours would need to shift accordingly. Document this mapping in the provider.

Metadata to preserve — extend `HourlyRecord` with three optional fields defaulting to `None`:

- `model_run_time: datetime | None` — the initialization time of the model run (e.g., 2024-07-15T00:00Z)
- `forecast_hour: int | None` — hours since model run time (e.g., 24 for a +24h forecast)
- `model_name: str | None` — model identifier (e.g., "gfs", "icon", "era5")

### Download Bounding Box

GRIB files from RDA contain the full global grid. No subsetting is needed at download time — the file is downloaded as-is, then the nearest grid point is extracted in Python. For ERA5 via CDS API, the request includes an `area` parameter to limit the download. Derive it from the `Location` coordinates with a small buffer: `[lat + 0.40, lon - 0.40, lat - 0.40, lon + 0.40]` (matching the notebook's `POINT_BUFFER_DEG = 0.40`). This keeps the GRIB file small while ensuring the nearest grid cell is included. Store `POINT_BUFFER_DEG` as a config constant.

### Grid-to-Point Interpolation

For Option A (GRIB), extract the nearest grid point using `xarray.DataArray.sel(lat=..., lon=..., method='nearest')`, matching the notebook's `select_point_dataarray()` approach. At 0.25° resolution the nearest point is at most ~14 km away. Near coastlines, verify the nearest grid cell is not predominantly over land by checking the GFS land-sea mask field. For Option B (Open-Meteo), interpolation is handled server-side.

### Implementation Tasks

- Add `GfsForecastProvider` implementing `WeatherProvider`.
- For Option A: download GFS GRIB2 files from NCAR RDA THREDDS, open with cfgrib/xarray, use robust multi-level variable scoring (port from notebook's `TARGET_SPECS` + `_open_target_da()`), extract nearest grid point, convert U/V to speed/direction.
- For Option B (fallback): call Open-Meteo forecast API with `&models=gfs_seamless`.
- Add filesystem cache for raw forecast responses.
- Store normalized hourly records in PostgreSQL with `source = "gfs"` or `source = "gfs_open_meteo"`.
- Alembic migration adding `model_run_time` (DateTime, nullable), `forecast_hour` (Integer, nullable), `model_name` (String, nullable) to `weather_records` table. Update `_upsert_records` in `weather_service.py` to persist these fields.
- Register the new provider in `WeatherService` so it can be selected by source name.
- Update the forecast-mode analysis flow: when `mode = "forecast"`, fetch target-day data from the GFS provider instead of the archive provider.
- Add frontend display of model run info when viewing a forecast-mode analysis.

### Acceptance Checks

- The app can fetch GFS forecast data for tomorrow for the LA location.
- Repeated requests use cached data.
- GFS wind speed and direction appear in the dashboard charts.
- A forecast-mode analysis run uses GFS for the target day.
- The analysis output states which GFS model run was used.

## Stage 3: ERA5 Historical Analog Library ✅ COMPLETED

### Purpose

Add a reanalysis-based historical dataset to serve as the analog pool. When the app looks for "similar historical days," it searches this library.

### Role In The Method

ERA5 provides consistent, hourly historical atmospheric data. Each historical day gets a feature vector (morning wind, temperature, pressure, etc.). The GFS forecast features for the target day are compared against these historical feature vectors to find the best analog matches.

### Data Source Options

Option A (recommended — matches the existing notebook):

- ECMWF CDS API (`cdsapi` Python client) for raw ERA5 single-level reanalysis data as GRIB. Requires a CDS account and `CDSAPI_KEY` environment variable. Parse with cfgrib/xarray, extract nearest grid point. The notebook (`SeaBreeze_v5_point_analog.ipynb`) already implements this via `download_era5_year()` + `open_era5()`.

Option B (simpler fallback):

- Open-Meteo Historical API with `&models=era5` parameter. Returns JSON — no CDS registration or GRIB handling. Useful if CDS API is unavailable or for faster iteration.

Start with Option A to match the validated notebook pipeline; fall back to Option B if needed.

### Data Needed

Hourly historical fields per day:

- wind speed at 10 m
- wind direction at 10 m
- temperature at 2 m
- mean sea level pressure
- cloud cover, optional
- boundary layer height, optional

### Grid-to-Point Interpolation

Same as Stage 2: for Option A (CDS GRIB), extract the nearest grid point using `xarray.DataArray.sel(method='nearest')`, matching the notebook's approach. ERA5 is on a 0.25° grid, so the nearest point is at most ~14 km away. Near coastlines, verify the nearest grid cell is not predominantly over land by checking the ERA5 land-sea mask. For Option B (Open-Meteo), interpolation is handled server-side.

### Historical Scope

Start with a manageable range for Los Angeles:

```text
May through September, 2015-2024
```

This gives roughly 1,500 candidate days. Can be expanded later.

### Bulk Fetch Strategy

Fetching ~1,500 days of ERA5 data requires batching, rate limiting, and resume capability:

- Fetch year-by-year via CDS API (matching the notebook's `download_era5_year()` pattern): one request per year covering all target months/days/hours. This produces ~10 GRIB files (one per year, 2015-2024).
- Each downloaded GRIB file is cached on the filesystem. If the file already exists and is non-empty, skip the download (the notebook already does this check).
- CDS API queues requests server-side; no client-side rate limiting needed, but requests may take minutes. Add a timeout and retry with exponential backoff.
- Track progress in `library_build_jobs` table: `(id, location_id, source, total_chunks, completed_chunks, status, error_message, started_at, finished_at)`.
- `GET /api/library/status` reads from this table to report build progress.

### Precomputed Feature Library

To avoid recalculating features on every forecast run:

- Add a `daily_features` table or cache that stores the computed feature vector for each historical day/location/source combination.
- Add a backend command or endpoint to build/rebuild the feature library for a location and date range.
- The analog matching service should read from this precomputed library rather than recomputing from hourly records every time.
- Each row includes `feature_config_hash` (String(16)), computed as SHA-256 of serialized `AnalysisWindow` config + sorted feature name list, truncated to 16 hex chars. Analog matching filters by hash, so stale rows from a changed config are automatically ignored.

### Analog Feature Vector

The exact feature columns used for analog matching (matching the notebook's `ANALOG_FEATURE_COLUMNS`). The analog match hour defaults to 09:00 local time (configurable via `ANALOG_MATCH_LOCAL_HOUR`).

Per-day features extracted at the match hour:

| # | Feature name | Description | Source field |
|---|---|---|---|
| 1 | `site_u10_10` | U-component of 10 m wind at match hour | `u10` |
| 2 | `site_v10_10` | V-component of 10 m wind at match hour | `v10` |
| 3 | `site_t2m_C_10` | 2 m temperature (°C) at match hour | `t2m` - 273.15 |
| 4 | `site_wind_speed_10` | Wind speed at match hour | `sqrt(u10² + v10²)` |
| 5 | `site_wind_dir_sin_10` | Sin of wind direction at match hour | `sin(wind_dir)` |
| 6 | `site_wind_dir_cos_10` | Cos of wind direction at match hour | `cos(wind_dir)` |
| 7 | `site_wind_speed_diff1_10` | 1-hour wind speed change at match hour | `speed[h] - speed[h-1]` |
| 8 | `site_t2m_C_diff1_10` | 1-hour temperature change at match hour | `temp[h] - temp[h-1]` |
| 9 | `site_wind_dir_diff1_10` | 1-hour circular direction change at match hour | `circular_diff(dir[h], dir[h-1])` |
| 10 | `morning_temp_mean` | Mean temperature 08:00–match hour | mean of `t2m_C` over morning |
| 11 | `morning_wind_speed_mean` | Mean wind speed 08:00–match hour | mean of `wind_speed` over morning |

All 11 features are computed identically for GFS (target day) and ERA5 (library days). Diff features (7-9) require at least one earlier hour of data. If `FeatureService` adds or removes features in the future, the `feature_config_hash` mechanism ensures stale rows are not used.

### Cross-Source Bias Calibration

GFS and ERA5 are different models with systematic biases. Comparing a GFS feature vector directly against ERA5 feature vectors introduces error into analog ranking. To correct this:

- Fetch GFS hindcast data for a 90-day overlap period from NCAR RDA (same THREDDS source as Stage 2, using past dates where ERA5 is also available).
- Compute per-feature mean bias: `bias_i = mean(GFS_feature_i - ERA5_feature_i)` over the overlap period.
- Store corrections in a new `source_bias_corrections` table: `(location_id, forecast_source, historical_source, feature_name, bias_mean, bias_std, calibration_start, calibration_end, sample_count, created_at)`.
- Add endpoint `GET /api/library/bias-report` returning per-feature bias statistics and calibration metadata.

### Implementation Tasks

- Add `Era5Provider` implementing `WeatherProvider`.
- For Option A: download ERA5 GRIB files via CDS API (port from notebook's `download_era5_year()`), open with cfgrib/xarray (port `open_era5()` + `open_grib_candidate_sets()`), extract nearest grid point, convert U/V to speed/direction.
- For Option B (fallback): call Open-Meteo archive API with `&models=era5`.
- Store normalized hourly records in PostgreSQL with `source = "era5"`.
- Add filesystem cache for raw GRIB files (skip download if file exists and is non-empty, matching the notebook pattern).
- Add `daily_features` table: `(location_id, source, date, features_json, feature_config_hash, created_at)`.
- Implement `compute_feature_config_hash()` in `feature_service.py`: SHA-256 of serialized `AnalysisWindow` config + sorted feature name list, truncated to 16 hex chars. Store with every row and filter by hash in analog matching.
- Add service method to build the feature library: iterate over all historical days, compute features, store.
- Add backend endpoint `POST /api/library/build` to trigger library construction.
- Add backend endpoint `GET /api/library/status` to check library completeness.
- Update `AnalogService` to accept a precomputed feature library for the historical pool.
- In forecast mode: target-day features come from GFS, historical features come from the ERA5 library.
- Fetch GFS hindcast overlap data (90 days) from NCAR RDA for past dates where ERA5 is also available.
- Compute per-feature bias statistics between GFS and ERA5 for the overlap period.
- Store bias corrections in `source_bias_corrections` table.
- Add `GET /api/library/bias-report` endpoint.

### Acceptance Checks

- The app can fetch ERA5 data for LA for a historical date range.
- The feature library can be built for May-September 2015-2024.
- Analog matching uses the precomputed ERA5 feature library.
- A forecast-mode run uses GFS for target day + ERA5 library for analogs.
- Historical data source is clearly labeled as ERA5 in all outputs.
- Bias statistics are computed for at least 60 overlapping days between GFS hindcast and ERA5.
- `GET /api/library/bias-report` returns per-feature bias mean, std, and sample count.
- A partially-completed library build resumes without re-fetching already-cached months.
- `GET /api/library/status` reports chunk-level progress from `library_build_jobs`.
- Changing `AnalysisWindow` config and rebuilding produces a new `feature_config_hash`; old rows are ignored by analog matching.

## Stage 4: Analog Forecast Composite ✅ COMPLETED

### Purpose

This is the core new capability. Instead of just ranking analog days, the app **builds a forecast** from the top analog days' actual 11:00-16:00 wind data.

### How It Works

1. The analog matching (Stage 2 + 3) produces the top-K most similar historical days (default K = 20, matching the notebook; configurable via `ANALOG_TOP_K`). Before standardization, subtract the stored bias vector from GFS features (from `source_bias_corrections`). If no calibration exists for a feature, log a warning and proceed without correction for that feature. Distance is standardized Euclidean: fit `StandardScaler` on the ERA5 library features, then transform both library and (bias-corrected) GFS features before computing L2 distance.
2. Sea breeze classification runs on the target day's GFS features.
   - If sea breeze probability is **low**: stop here. Report "no sea breeze expected" and do not produce a forecast.
   - If sea breeze probability is **medium or high**: continue.
3. For each top analog day, extract the hourly ERA5 TWD and TWS values for 11:00-16:00 local time.
4. Composite these curves into a forecast:
   - **Central forecast**: hour-by-hour median TWS and circular mean TWD across analogs.
   - **Spread/uncertainty**: hour-by-hour TWS percentile bands (25th-75th, 10th-90th); TWD circular standard deviation and 75th-percentile arc radius.
   - **Individual analog traces**: optionally show each analog day's curve for transparency.
5. Store the composite forecast alongside the analysis run.

### Sea Breeze Gate

The classification service already produces low/medium/high. In forecast mode:

- `low`: the analysis run completes with `summary = "Sea breeze probability low. No forecast produced."` No composite is generated.
- `medium` or `high`: proceed to composite. The summary includes the confidence level.

This prevents the system from producing misleading forecasts on non-sea-breeze days.

The gate uses existing `ClassificationService` thresholds: speed increase >= 1.5 m/s, |direction shift| >= 25 deg, onshore fraction >= 0.5. Gate fires at count_true >= 2 ('medium' or 'high'). Configurable via `SeaBreezeThresholds` in `features.py`.

**Note on notebook vs webapp classification:** The notebook (`SeaBreeze_v5_point_analog.ipynb`) uses a stricter 4-condition AND gate that also requires temperature rise >= 1.0 °C. The webapp's `ClassificationService` uses a 3-condition count scheme (no temperature). For the forecast gate, use the webapp's existing `ClassificationService` (3-condition, count_true >= 2), since that is what the rest of the app already produces. The Stage 6 gate sensitivity analysis will evaluate whether adding temperature as a 4th condition improves accuracy.

### Output Data

The forecast composite should produce, per hour from 11:00 to 16:00:

- median TWS (m/s)
- TWS 25th percentile
- TWS 75th percentile
- TWS 10th percentile
- TWS 90th percentile
- circular mean TWD (degrees)
- TWD circular standard deviation (degrees) and 75th-percentile arc radius
- number of analog days contributing

### Implementation Tasks

- Add `ForecastService` that takes analog results + historical hourly data and produces a composite.
- Reuse `circular_mean()` from `feature_service.py` for TWD central tendency.
- Add `circular_std()` function: compute mean resultant length R, then `sqrt(-2 * ln(R))` converted to degrees, capped at 180.
- Arc-radius spread: sort analog directions by circular distance from circular mean; the 75th-percentile rank value gives the spread.
- TWS uses standard `numpy.median` and `numpy.percentile` (linear, no circular treatment).
- Add the sea breeze gate: check classification before producing composite.
- Add `forecast_records` table or store composite data in a JSON field on `AnalysisRun`.
- Add backend endpoint `GET /api/analysis/{run_id}/forecast` returning the composite time series.
- Add frontend forecast chart — composite chart: TWS median line with filled 25th-75th band and dashed 10th-90th lines; circular mean TWD line with circular-std shading.
- Add `ForecastCompositeHour` and `ForecastComposite` types to `types.ts`.
- Add `renderForecastChart()` in `charts.ts`.
- Conditional rendering in `main.ts`: historical mode shows current charts, forecast mode shows composite charts + classification badge.
- Optionally add toggle to show individual analog traces on the chart.
- Add CSV/JSON export for the composite forecast.

### Acceptance Checks

- A forecast-mode run with high sea breeze probability produces a TWD/TWS composite for 11:00-16:00.
- A forecast-mode run with low sea breeze probability reports "no forecast" cleanly.
- The forecast chart shows median, percentile bands, and optionally individual analog traces.
- Composite data is exportable.
- The number of contributing analog days is visible.

## Stage 5: Weather Station Observations

### Purpose

Add real observed wind data so the forecast can be validated against what actually happened. This closes the loop: forecast yesterday, then check how accurate it was today.

### Role In The Method

Station observations are for **validation**, not for producing the forecast. They answer:

- Did the predicted sea breeze actually occur?
- How close was the predicted onset time?
- How accurate were the predicted TWS and TWD between 11:00 and 16:00?

In a future live-usage scenario, recent station observations (e.g., from this morning) could also be used to update confidence in the forecast, but this is a later enhancement.

### Data Source Options

- NOAA ISD/METAR station data (free, global coverage)
- MesoWest/Synoptic Data API (good coverage for US stations)
- Local buoy or sailing club station data if available
- Open-Meteo has some station data endpoints

### Data Needed

Hourly or sub-hourly observed fields:

- observation time
- observed wind speed
- observed wind direction
- station coordinates
- station identifier and name

Optional:

- gust speed
- temperature
- pressure

### Implementation Tasks

- Add `ObservationProvider` abstract base class.
- Implement first provider (NOAA ISD or MesoWest).
- Add `weather_stations` table: `(id, name, latitude, longitude, source, station_code)`.
- Add `observations` table: `(id, station_id, observation_time_utc, observation_time_local, wind_speed, wind_direction, gust_speed, temperature, pressure, raw_payload)`.
- Add endpoint `POST /api/observations/fetch` to pull station data for a date.
- Add endpoint `GET /api/observations` to query stored observations.
- Add frontend chart overlay: plot observed TWS/TWD alongside the forecast composite.
- Add basic validation metrics per analysis run:
  - MAE for wind speed in the 11-16 window
  - circular MAE for wind direction
  - sea breeze onset time difference (predicted vs observed)
  - peak wind speed difference

### Acceptance Checks

- The app can fetch and store observations from at least one station near LA.
- The dashboard shows observed wind alongside the forecast composite.
- Validation metrics are calculated and displayed.
- Observation source is stored and labeled.

## Stage 5.5: Interactive Hindcast Validation Mode

### Purpose

Add a **hindcast mode** that lets the user pick a past date, run the analog forecast pipeline using actual GFS forecast data from that morning, and compare the resulting analog-based forecast against what ERA5 recorded actually happened. This provides an interactive way to evaluate forecast skill on any historical day before running the full batch validation in Stage 6.

### Role In The Method

This is a single-day version of the batch validation (Stage 6), but interactive. It answers: "If I had run the forecast system on date X using the GFS morning data, how well would the analog composite have predicted the actual afternoon sea breeze?"

Using real GFS hindcast data (rather than ERA5 morning data as a stand-in) is more honest because it preserves the real GFS–ERA5 bias that would exist in an operational forecast.

### How It Works

1. User selects a **past date** (e.g., 2025-07-24) and picks "Hindcast" mode in the UI.
2. The backend fetches GFS forecast data for that date's morning window (the same hours used in forecast mode — currently weighted to 9–11 AM local features in the analog matching).
3. Analog matching runs using the GFS morning features against the ERA5 library (same as forecast mode).
4. The analog composite forecast is built from the top-K analog days' ERA5 afternoon data (11:00–16:00).
5. The backend also fetches the **actual ERA5 data** for the same afternoon window on the target date — this is the ground truth.
6. The frontend displays:
   - The analog composite forecast (median + percentile bands) overlaid with the actual ERA5 afternoon TWS/TWD curves.
   - Per-hour and aggregate error metrics (MAE for wind speed, circular MAE for direction).
   - Classification correctness: did the analogs predict a sea breeze, and did one actually occur?

### Target-Day Source Fallback

GFS archive data on NCAR RDA is generally available for recent years (2023+). If GFS data is unavailable for a given past date:
- Fall back to the Open-Meteo GFS seamless model (`gfs_open_meteo`), which has broader historical coverage.
- The run should record which source was actually used (`forecast_source` field).

### Frontend UI

- Add a third mode to the existing mode selector: **"Hindcast Validation"** alongside "Historical Analysis" and "Sea Breeze Forecast".
- In hindcast mode:
  - Target date is restricted to past dates where both GFS and ERA5 data are expected to be available.
  - Historical range is auto-set to the ERA5 library range (read-only), same as forecast mode.
- The results view shows the same forecast composite chart as forecast mode, but with an additional overlay of the actual ERA5 afternoon data and error metrics.

### Output Data

In addition to the standard forecast composite output (Stage 4), the hindcast produces:

- Actual ERA5 TWS and TWD for each hour in the 11:00–16:00 window.
- Per-hour error: `forecast_tws - actual_tws`, `circular_diff(forecast_twd, actual_twd)`.
- Aggregate metrics for the day:
  - MAE and RMSE for TWS over the forecast window.
  - Circular MAE for TWD over the forecast window.
  - Peak wind speed error: `max(forecast_tws) - max(actual_tws)`.
  - Classification match: predicted vs actual sea breeze classification.

### Implementation Tasks

- Add `mode = "hindcast"` as a third valid mode on `AnalysisRun`.
- Update the analysis flow: when `mode = "hindcast"`, fetch target-day morning data from GFS (with Open-Meteo GFS fallback), run analog matching against ERA5 library, build composite, then also fetch the actual ERA5 afternoon data for the same day.
- Add backend endpoint or extend `GET /api/analysis/{run_id}/forecast` to include `actual` ERA5 data and error metrics when the run mode is `"hindcast"`.
- Add `HindcastMetrics` schema: per-hour errors + aggregate MAE/RMSE/circular-MAE.
- Add frontend hindcast mode to the mode selector.
- Add frontend chart overlay: composite forecast vs actual ERA5 afternoon curves.
- Add frontend metrics display: MAE, RMSE, circular MAE, peak error, classification match.
- Store hindcast results alongside the analysis run for later retrieval from history.

### Acceptance Checks

- A user can select a past date in hindcast mode and see the GFS-based forecast composite overlaid with actual ERA5 data.
- Error metrics (MAE, RMSE, circular MAE) are displayed.
- The run stores which GFS source was used (NCAR RDA or Open-Meteo fallback).
- Hindcast runs appear in the history list and can be reloaded.
- If GFS data is unavailable, the system falls back to Open-Meteo GFS seamless and reports the source.

## Stage 6: Batch Validation And Method Evaluation

### Purpose

Evaluate the forecast method systematically across many historical days. This produces the thesis's core results: how well does the analog method actually predict sea breeze TWD and TWS?

### How It Works

Run the forecast method on past days where we already know what happened. This is the batch version of the interactive hindcast (Stage 5.5), using real GFS forecast data wherever available.

1. **Primary method — Temporal split with GFS hindcast:**
   - Library = May-Sep 2015-2022 (~1,220 days), test = May-Sep 2023-2024 (~306 days).
   - For each test day, fetch actual GFS forecast data for the morning window. If GFS archive data is unavailable for a given day, fall back to that day's ERA5 morning data as a stand-in.
   - Exclude library days within +/-7 calendar days of the test day's month-day in any year (to avoid near-duplicate weather patterns).
   - Run analog matching against the remaining library. Produce the composite forecast for 11:00-16:00.
   - Compare against that day's actual ERA5 afternoon data (ground truth).
   - Record which source was used for each test day (GFS vs ERA5-fallback) so results can be stratified.
2. **Secondary method — Leave-one-out** (for thesis appendix):
   - Full 2015-2024 dataset. For each day, exclude that day and all days within +/-7 calendar days of its month-day in any year.
   - Same evaluation procedure as above (GFS hindcast with ERA5 fallback).
   - Report results in thesis appendix for comparison.
3. Aggregate metrics across all test days for each method.
4. Optionally stratify results by source (GFS-only days vs ERA5-fallback days) to quantify the impact of using real forecast data vs reanalysis stand-in.

### Metrics

Classification metrics (sea breeze detection):

- true positives, false positives, true negatives, false negatives
- precision, recall, F1 score

Continuous metrics (forecast accuracy on sea breeze days):

- MAE and RMSE for wind speed
- circular MAE for wind direction
- onset time error
- peak wind speed error
- skill score vs climatology baseline
- gate sensitivity: coverage and conditional MAE/RMSE at each gate level (count_true >= 1, >= 2, >= 3)

Source stratification (new):

- Metrics broken down by target-day source (GFS vs ERA5-fallback) to measure the effect of real forecast bias on accuracy.

### Implementation Tasks

- Add `ValidationRun` model/table to store batch evaluation results.
- Add `validation_service.py` implementing both temporal-split and leave-one-out modes, selectable via `evaluation_method` parameter. Both modes use `exclusion_buffer_days: int = 7` to exclude near-duplicate days.
- For each test day, attempt to fetch GFS hindcast data; fall back to ERA5 morning data if GFS is unavailable. Record the source used per day.
- Reuse the same hindcast logic from Stage 5.5 (GFS fetch → analog match → composite → compare against ERA5 actual).
- Add endpoint `POST /api/validation/run` to trigger batch evaluation.
- Add endpoint `GET /api/validation/{run_id}` to retrieve results.
- Add validation results dashboard section with summary statistics.
- Add CSV export for per-day validation results (for thesis tables), including which source was used for each test day.
- Ensure the test day is excluded from its own analog pool to prevent data leakage.
- Gate sensitivity analysis: sweep gate at count_true >= 1, >= 2, >= 3 and report coverage-vs-accuracy table.
- Add source-stratified metrics: report accuracy separately for GFS-sourced and ERA5-fallback test days.

### Acceptance Checks

- A batch validation run can evaluate 50+ days.
- Per-day and aggregate metrics are stored and exportable.
- The evaluation excludes the test day from the analog library.
- Each test day records whether GFS or ERA5-fallback was used as the target-day source.
- Results can be stratified by source to show impact of real GFS bias.
- Results are suitable for thesis tables and figures.

## Stage 7: ML Calibration Layer

### Purpose

Add machine learning to improve the analog forecast. Only do this after Stages 1-6 are working and validated.

The ML model should **calibrate and improve** the analog method, not replace it.

### Possible ML Tasks

- Predict sea breeze probability more accurately than the rules-based classifier.
- Predict the expected afternoon max wind speed.
- Predict sea breeze onset time.
- Learn optimal analog feature weights (replacing equal-weight Euclidean distance).
- Refine the Stage 3 bias correction using ML (learn nonlinear or seasonal bias patterns beyond the static mean correction).

### Candidate Models

Start simple:

- logistic regression for classification
- random forest or gradient boosted trees for regression
- XGBoost or LightGBM if more power is needed

Avoid deep learning unless there is enough data and a clear benefit.

### Input Features For ML

The daily feature vector already computed by `FeatureService`, plus optionally:

- GFS-ERA5 morning bias for the target day (if both sources available)
- recent station observations (live wind data before the forecast window)
- synoptic-scale indicators (e.g., 500 hPa pattern category, if available)
- seasonal indicators (day of year, month)
- climatological baselines for the location

### Implementation Tasks

- Create reproducible training dataset from the precomputed feature library and validation results.
- Split train/test **temporally** (e.g., train on 2015-2022, test on 2023-2024). Never split randomly.
- Implement ML training pipeline in a backend service.
- Store model artifacts, version, and training parameters.
- Add model evaluation metrics (compare ML-calibrated vs raw analog).
- Add optional ML-adjusted output to the forecast dashboard (clearly labeled).
- The analog method must still work without ML. ML is an optional enhancement layer.

### Acceptance Checks

- ML model can be trained from stored data.
- ML-calibrated output is clearly labeled as such.
- Analog method works identically without ML enabled.
- Model evaluation shows whether ML actually improves over the baseline analog method.
- Training/evaluation is reproducible from stored parameters.

## Stage 8: Live Forecast Mode And Real-Time Station Data

### Purpose

This is the final operational stage. The app can be used in a real forecasting workflow:

1. Each morning, fetch the latest GFS forecast for the target location.
2. Automatically run the analog forecast pipeline.
3. Throughout the day, pull live station data and compare against the forecast.
4. At end of day, compute validation metrics.

### Implementation Tasks

- Add scheduled or on-demand forecast trigger (could be a cron job or manual button).
- Add live station data polling (if a station API supports recent observations).
- Add real-time forecast vs observation comparison view.
- Add notification or summary when sea breeze probability is high (optional).
- Add forecast history view: browse past forecasts and their validation scores.

### Acceptance Checks

- A user can trigger a forecast for tomorrow with one click.
- The forecast updates when new GFS runs become available.
- Live station data appears on the chart as the day progresses.
- End-of-day validation runs automatically or on demand.

## Recommended Implementation Order

```text
Stage 1: Source metadata + forecast mode skeleton          ✅ COMPLETED
Stage 2: GFS forecast provider (target-day input)          ✅ COMPLETED
Stage 3: ERA5 historical analog library (analog pool)      ✅ COMPLETED
Stage 4: Analog forecast composite (the core new output)   ✅ COMPLETED
Stage 5:   Weather station observations (validation data)
Stage 5.5: Interactive hindcast validation mode (GFS vs ERA5 comparison)
Stage 6:   Batch validation (thesis results, GFS hindcast with ERA5 fallback)
Stage 7:   ML calibration (improvement layer)
Stage 8:   Live forecast mode (operational usage)
```

Stages 1-4 are the critical path to a working forecast system (done).

Stage 5 adds station observations for real-world validation.

Stage 5.5 adds interactive hindcast mode — pick any past date, run GFS morning → analog forecast, compare against ERA5 reality. This builds and validates the hindcast pipeline that Stage 6 runs at scale.

Stage 6 runs the same hindcast pipeline across all test days in batch, producing the thesis's core accuracy tables.

Stages 7-8 are enhancements.

## Architecture Notes

### How The Three Modes Differ

| Aspect | Historical mode | Forecast mode | Hindcast mode |
|---|---|---|---|
| Target date | Past date | Future date (e.g., tomorrow) | Past date (where GFS + ERA5 exist) |
| Target-day data source | Open-Meteo archive or ERA5 | GFS forecast (GRIB from RDA) | GFS hindcast (with ERA5 fallback) |
| Historical pool source | Open-Meteo archive | ERA5 precomputed library | ERA5 precomputed library |
| Main output | Analog ranking + classification | TWD/TWS composite forecast for 11-16 | Composite forecast overlaid with actual ERA5 |
| Sea breeze gate | Classification shown as info | Classification gates forecast production | Classification gates forecast production |
| Validation | Not applicable | Compare against station observations | Compare against ERA5 actual afternoon data |
| Error metrics | Not applicable | Not applicable (until observations) | MAE, RMSE, circular MAE, peak error |

### New Database Objects

```text
daily_features
  id, location_id, source, date, features_json, feature_config_hash, created_at
  UNIQUE(location_id, source, date, feature_config_hash)

forecast_composites (or JSON field on analysis_runs)
  analysis_run_id, hour_local, median_tws, p25_tws, p75_tws,
  p10_tws, p90_tws, circular_mean_twd, twd_circular_std,
  twd_arc_radius_75, analog_count

library_build_jobs
  id, location_id, source, total_chunks, completed_chunks,
  status, error_message, started_at, finished_at

weather_stations
  id, name, latitude, longitude, source, station_code, created_at

observations
  id, station_id, observation_time_utc, observation_time_local,
  wind_speed, wind_direction, gust_speed, temperature, pressure,
  raw_payload, created_at

source_bias_corrections
  location_id, forecast_source, historical_source, feature_name,
  bias_mean, bias_std, calibration_start, calibration_end,
  sample_count, created_at

validation_runs
  id, location_id, test_start_date, test_end_date, method,
  evaluation_method, exclusion_buffer_days (default 7),
  train_start_date, train_end_date,
  aggregate_metrics_json, started_at, finished_at, status
```

### API Endpoint Contracts

New endpoints introduced across stages, with request/response shapes:

**Stage 1:**

```
POST /api/analysis
  Request:  { location_id: int, target_date: "YYYY-MM-DD",
              mode: "historical"|"forecast" (default "historical"),
              forecast_source: str|null, historical_source: str|null,
              historical_start_date: "YYYY-MM-DD", historical_end_date: "YYYY-MM-DD" }
  Response: { run_id: int, mode: str, status: str, ...existing fields }
```

**Stage 3:**

```
POST /api/library/build
  Request:  { location_id: int, source: "era5", start_date: "YYYY-MM-DD",
              end_date: "YYYY-MM-DD" }
  Response: { job_id: int, status: "queued", total_chunks: int }

GET /api/library/status?location_id={id}
  Response: { job_id: int, status: "in_progress"|"completed"|"failed",
              total_chunks: int, completed_chunks: int,
              error_message: str|null }

GET /api/library/bias-report?location_id={id}
  Response: { location_id: int, calibration_start: "YYYY-MM-DD",
              calibration_end: "YYYY-MM-DD", sample_count: int,
              features: [ { name: str, bias_mean: float, bias_std: float } ] }
```

**Stage 4:**

```
GET /api/analysis/{run_id}/forecast
  Response: { run_id: int, gate_result: "low"|"medium"|"high",
              forecast: [ { hour_local: int, median_tws: float,
              p25_tws: float, p75_tws: float, p10_tws: float, p90_tws: float,
              circular_mean_twd: float, twd_circular_std: float,
              twd_arc_radius_75: float, analog_count: int } ] | null,
              summary: str }
```

**Stage 5:**

```
POST /api/observations/fetch
  Request:  { station_id: int, date: "YYYY-MM-DD" }
  Response: { station_id: int, count: int, status: str }

GET /api/observations?station_id={id}&date={date}
  Response: { observations: [ { time_utc: str, time_local: str,
              wind_speed: float, wind_direction: float,
              gust_speed: float|null, temperature: float|null } ] }
```

**Stage 5.5:**

```
GET /api/analysis/{run_id}/hindcast
  Response: { run_id: int, gate_result: "low"|"medium"|"high",
              forecast: [ { hour_local: int, median_tws: float, ... } ] | null,
              actual: [ { hour_local: int, tws: float, twd: float } ],
              metrics: { mae_tws: float, rmse_tws: float,
              circular_mae_twd: float, peak_tws_error: float,
              classification_match: bool },
              forecast_source_used: str,
              summary: str }
```

**Stage 6:**

```
POST /api/validation/run
  Request:  { location_id: int, evaluation_method: "temporal_split"|"leave_one_out",
              exclusion_buffer_days: int (default 7),
              test_start_date: "YYYY-MM-DD"|null, test_end_date: "YYYY-MM-DD"|null }
  Response: { run_id: int, status: "queued" }

GET /api/validation/{run_id}
  Response: { run_id: int, status: str, evaluation_method: str,
              aggregate_metrics: { mae_speed: float, rmse_speed: float,
              circular_mae_dir: float, precision: float, recall: float,
              f1: float, skill_score: float,
              gate_sensitivity: [ { gate_level: int, coverage: float,
              conditional_mae: float, conditional_rmse: float } ] },
              per_day_results_url: str }
```

### Background Job Execution

Several operations are too slow for a synchronous HTTP request:

- **Library build** (Stage 3): downloading 10 years of ERA5 + computing features — minutes to hours.
- **Bias calibration** (Stage 3): downloading 90 days of GFS hindcast — minutes.
- **Validation run** (Stage 6): evaluating 300+ days — minutes.

Use FastAPI's `BackgroundTasks` for these. The `POST` endpoint writes a row to the jobs table with `status = "queued"`, kicks off the background task, and returns the job ID immediately. The background task updates `status` and `completed_chunks` as it progresses. The frontend polls `GET /api/library/status` or `GET /api/validation/{run_id}` until completion. No external task queue (Celery, Redis) is needed at this scale — a single-worker FastAPI process with `BackgroundTasks` is sufficient for a thesis prototype.

### Existing Components That Need Modification

- `HourlyRecord` dataclass: add optional `model_run_time`, `forecast_hour`, `model_name` fields.
- `WeatherRecord` model: add `model_run_time`, `forecast_hour`, `model_name` columns (nullable).
- `AnalysisRun` model: add `mode` (`"historical"`, `"forecast"`, or `"hindcast"`), `forecast_source`, `historical_source` fields.
- `AnalogService`: accept precomputed feature library instead of always recomputing.
- `ClassificationService`: no logic change, but result now gates forecast production.
- Frontend analysis form: add mode selector (Historical / Forecast / Hindcast), show forecast chart when in forecast mode, show forecast-vs-actual overlay in hindcast mode.
- Frontend charts: add composite forecast view with percentile bands; add hindcast overlay with actual ERA5 curves and error metrics.

## GRIB Dependencies And Docker

The GRIB-based pipeline requires `cfgrib`, `eccodes`, and `xarray`. These have non-trivial system dependencies:

- **`eccodes`** is the ECMWF C library for GRIB decoding. On Debian/Ubuntu: `apt-get install libeccodes-dev`. On macOS: `brew install eccodes`.
- **`cfgrib`** is the Python/xarray backend that wraps eccodes.
- In the **Dockerfile**, add `libeccodes-dev` to the `apt-get install` line, then `pip install cfgrib eccodes xarray`.
- Add `cdsapi` for ERA5 downloads and `requests` for RDA downloads (likely already present).
- Test GRIB reading in CI: add a small test GRIB file to the repo fixtures and verify `xr.open_dataset(..., engine='cfgrib')` works in the container.

### Disk Space For GRIB Files

Approximate sizes for the LA area (small bounding box ~0.8° × 0.8°):

- **GFS**: each forecast-hour GRIB2 file is ~1-5 MB. Two files per day × 365 days = ~2-4 GB/year.
- **ERA5**: one year of hourly single-level data for the small area is ~50-200 MB per GRIB file. Ten years = ~0.5-2 GB total.
- **Total on-disk cache**: expect ~3-6 GB for a full LA setup.

Add a `GRIB_CACHE_DIR` config setting (default: `./data/grib_cache/`). Do not commit GRIB files to git. Add `*.grib*` to `.gitignore`. For production, consider a mounted volume or object storage.

## Claude Code Execution Notes

Implement this plan only after phases 1-9 of the webapp implementation plan are complete.

For each stage:

- Keep the app runnable at all times.
- Do not remove the prototype Open-Meteo provider.
- Add tests for new data conversion and feature logic.
- Preserve cached data between runs.
- Document which data sources were used in all stored results.

Each stage should be implemented in a separate commit or small set of commits.

## Recommended First Prompt

```text
Implement Stage 1 from THESIS_DATA_SOURCE_UPGRADE_PLAN.md.

Add source metadata fields to AnalysisRun (mode, forecast_source, historical_source).
Update the analysis request schema to accept these fields with sensible defaults.
Add source labels to API responses, frontend charts, and exports.
Allow future dates as target_date when mode is "forecast".
Keep existing historical analysis working unchanged.

After implementation, run the backend tests, frontend build, and Docker Compose smoke check.
```
