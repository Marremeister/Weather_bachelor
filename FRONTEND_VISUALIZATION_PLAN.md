# Frontend Visualization Improvement Plan

## Overview

This document outlines new graphs, overlays, and informational panels to add to the frontend. The backend already computes most of the underlying data — the work is primarily frontend charting and minor API adjustments.

---

## Phase 1 — TWS/TWD Overlay & Temperature/Pressure Chart

### 1.1 TWS + TWD Dual-Axis Overlay

Replace or supplement the two separate wind charts with a single dual-axis chart:

- **Left Y-axis:** True Wind Speed (m/s), rendered as a line with smooth interpolation.
- **Right Y-axis:** True Wind Direction (0–360°, N/E/S/W labels), rendered as scatter points.
- **X-axis:** Time (hourly).
- Tooltip shows both values at each hour.
- The classic sea breeze signature — a direction shift coinciding with a speed ramp-up — becomes immediately visible.

### 1.2 Temperature + Pressure Chart

Temperature and pressure are already fetched and shown in the hourly table but have no chart.

- **Left Y-axis:** Temperature (°C), line chart.
- **Right Y-axis:** Pressure (hPa), line chart.
- **X-axis:** Time (hourly), aligned with the wind chart above.
- Rising temperature + falling pressure often precedes thermal sea breezes, giving synoptic context.

**Backend changes:** None. All data already returned by the weather API.

---

## Phase 2 — Sea Breeze Classification & Probability Panel

### 2.1 Sea Breeze Indicator Gauges

Three visual gauges (progress bars or radial indicators) showing the three classification indicators for the target day:

| Indicator | Value | Threshold |
|-----------|-------|-----------|
| Speed increase | `afternoon_max - morning_mean` | ≥ 1.5 m/s |
| Direction shift | `abs(morning_dir - afternoon_dir)` | ≥ 25° |
| Onshore fraction | fraction of afternoon hours with onshore wind | ≥ 0.5 |

Plus an overall classification badge: **High** (3/3), **Medium** (2/3), **Low** (0–1/3).

### 2.2 Sea Breeze Probability from Analogs

Among the top-N analog days, compute how many were classified as "High" sea breeze days.

- Display as a prominent number: e.g. *"7 / 10 analogs (70%) had a strong sea breeze"*.
- Optionally show a small donut chart breaking down High / Medium / Low among the analogs.

**Backend changes:** The classification logic exists but needs an endpoint (or extension of the analysis response) that returns the per-analog classification and the target day's feature values / indicator results.

---

## Phase 3 — Target Day vs Analog Overlay

### 3.1 Target vs Top-N Analog Hourly Curves

A chart overlaying the hourly TWS curve for the target date with the curves from the top 1–3 analog days:

- Target day as a bold/solid line.
- Analog days as thinner or dashed lines, color-coded by rank.
- Toggle to switch between TWS and TWD.
- Visually confirms whether the analog match is actually good or superficial.

### 3.2 Wind Speed Increase Comparison Bar Chart

A horizontal bar chart showing `wind_speed_increase` (afternoon max − morning mean) for:

- The target day (highlighted).
- Each of the top-N analog days, sorted by rank.

Quickly shows whether the analogs predict a big afternoon ramp-up.

**Backend changes:** Need an endpoint (or expanded response) that returns hourly weather data for each analog day, not just the summary. The `raw_payload` or a dedicated fetch can supply this.

---

## Phase 4 — Feature Radar & Direction Shift

### 4.1 Feature Radar / Spider Chart

Plot the 9 daily features on a normalized radar chart:

- One polygon for the target day.
- One polygon for the mean of the top-N analogs.
- Shape similarity = good analog match.
- Features: morning mean speed, morning direction, reference speed, reference direction, afternoon max, afternoon direction, speed increase, direction shift, onshore fraction.

Directions are decomposed into sin/cos internally, but for display map them back to intuitive values.

### 4.2 Direction Shift Lollipop Chart

A horizontal lollipop chart showing `wind_direction_shift` for the target day vs each analog day:

- Positive shift = veering (clockwise).
- Negative shift = backing (counter-clockwise).
- A vertical zero line in the center.
- Color intensity by magnitude.

**Backend changes:** The daily feature values need to be exposed in the API response (they are computed but not all are returned to the frontend today).

---

## Phase 5 — Morning vs Afternoon Wind Rose

### 5.1 Dual Wind Rose

Two small polar/radar plots side-by-side:

- **Left:** Morning window (08:00–10:00) wind speed and direction.
- **Right:** Afternoon window (11:00–16:00) wind speed and direction.

Each plot shows directional sectors (N, NE, E, … ) with bars whose length represents mean wind speed from that direction. The rotation and lengthening between morning and afternoon directly visualises the sea breeze onset.

**Backend changes:** The hourly data is already available. The frontend needs to bin directions into sectors and compute per-sector averages for each window.

---

## Phase 6 — Seasonal Heatmap & Analog Distribution

### 6.1 Seasonal Calendar Heatmap

A calendar heatmap covering the sea breeze season (May–September) across all library years (2015–2024):

- Each cell = one day.
- Color = `wind_speed_increase` magnitude (or sea breeze classification: green/yellow/red).
- Highlights which periods historically produce the strongest sea breezes.
- The target date and top-N analog dates can be marked with borders or icons.

### 6.2 Analog Distance Distribution Histogram

A histogram of similarity scores for all historical days in the library:

- X-axis: similarity score (0–1) or distance.
- Y-axis: count of days.
- The top-N analogs highlighted as colored bars or vertical lines.
- Shows whether the analogs are genuinely close matches or just the best of a bad bunch.

**Backend changes:** The library endpoint needs to return all daily distances (or at least a summary distribution), not just the top-N. A new lightweight endpoint returning the full distance array would work.

---

## Phase 7 — Source Bias & Data Quality Panel

### 7.1 Source Bias Visualization

A grouped bar chart or table showing bias correction statistics per feature:

- **X-axis:** Feature name (morning speed, direction shift, etc.).
- **Y-axis:** Mean bias (with error bars for ±1 std).
- Grouped by source pair (e.g. GFS vs ERA5, Open-Meteo vs ERA5).
- Helps the user understand how much to trust the forecast source.

### 7.2 Data Freshness & Quality Indicators

Small status badges or icons showing:

- When the forecast model run was initialized (already in summary text, but make it prominent).
- Hours since last data update.
- Number of missing hours in the target day's data.
- Library coverage: how many historical days are available vs expected.

**Backend changes:** The bias report endpoint (`/api/library/bias-report`) already exists. Data freshness info is available from existing fields (`model_run_time`, `hours_available`).

---

## Phase Summary

| Phase | Contents | New Charts | Backend Work |
|-------|----------|------------|--------------|
| 1 | TWS/TWD overlay, temp/pressure chart | 2 | None |
| 2 | Sea breeze gauges, analog probability | 2 | Minor API extension |
| 3 | Target vs analog curves, speed increase bars | 2 | New endpoint for analog hourly data |
| 4 | Feature radar chart, direction shift lollipop | 2 | Expose feature values in API |
| 5 | Dual wind rose (morning/afternoon) | 1 | None (frontend binning) |
| 6 | Seasonal heatmap, distance histogram | 2 | New endpoint for full distance array |
| 7 | Bias panel, data quality indicators | 2 | None (endpoints exist) |
