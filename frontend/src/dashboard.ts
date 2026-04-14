import type { AnalogResult, AnalysisRunDetail, BiasCorrection, LibraryStatusResponse, WeatherRecord } from "./types";

export function renderSummaryPanel(
  container: HTMLElement,
  run: AnalysisRunDetail,
): void {
  const statusClass = run.status === "completed" ? "completed" : run.status === "failed" ? "failed" : "running";

  let duration = "—";
  if (run.started_at && run.finished_at) {
    const ms = new Date(run.finished_at).getTime() - new Date(run.started_at).getTime();
    duration = ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
  }

  const mode = run.mode ?? "historical";
  const modeLabel = mode === "forecast" ? "Forecast" : "Historical";
  const dataSource = mode === "forecast"
    ? `Forecast: ${run.forecast_source ?? "open_meteo"} / Historical: ${run.historical_source ?? "open_meteo"}`
    : run.historical_source ?? "open_meteo";

  container.innerHTML = `
    <div class="summary-grid">
      <div class="summary-item">
        <span class="label">Status</span>
        <span class="value"><span class="status-badge ${statusClass}">${run.status}</span></span>
      </div>
      <div class="summary-item">
        <span class="label">Mode</span>
        <span class="value"><span class="status-badge ${mode}">${modeLabel}</span></span>
      </div>
      <div class="summary-item">
        <span class="label">Target Date</span>
        <span class="value">${run.target_date}</span>
      </div>
      <div class="summary-item">
        <span class="label">Historical Range</span>
        <span class="value">${run.historical_start_date ?? "—"} to ${run.historical_end_date ?? "—"}</span>
      </div>
      <div class="summary-item">
        <span class="label">Data Source</span>
        <span class="value">${escapeHtml(dataSource)}</span>
      </div>
      <div class="summary-item">
        <span class="label">Analog Days</span>
        <span class="value">${run.analogs.length}</span>
      </div>
      <div class="summary-item">
        <span class="label">Duration</span>
        <span class="value">${duration}</span>
      </div>
    </div>
    ${run.summary ? `<p style="margin-top: 0.75rem; color: #495057;">${escapeHtml(run.summary)}</p>` : ""}
  `;

  // Show model run info as a dedicated item for forecast mode
  if (mode === "forecast" && run.summary && run.summary.startsWith("GFS model run:")) {
    const grid = container.querySelector(".summary-grid");
    if (grid) {
      const item = document.createElement("div");
      item.className = "summary-item";
      item.innerHTML = `
        <span class="label">Model Run</span>
        <span class="value">${escapeHtml(run.summary.replace("GFS model run: ", ""))}</span>
      `;
      grid.appendChild(item);
    }
  }
}

export function renderHourlyTable(
  container: HTMLElement,
  records: WeatherRecord[],
): void {
  if (records.length === 0) {
    container.innerHTML = `
      <thead><tr><th colspan="6">No weather data available</th></tr></thead>
    `;
    return;
  }

  const sourceLabel = records[0]?.source ? `Source: ${records[0].source}` : "";

  const headerRow = `
    <thead>
      ${sourceLabel ? `<tr><th colspan="6" style="text-align:left;font-weight:400;font-size:0.82rem;color:#868e96;padding-bottom:0.4rem;border-bottom:none;">${escapeHtml(sourceLabel)}</th></tr>` : ""}
      <tr>
        <th>Time</th>
        <th class="num">Wind Speed (m/s)</th>
        <th class="num">Wind Dir (°)</th>
        <th class="num">Temp (°C)</th>
        <th class="num">Pressure (hPa)</th>
        <th class="num">Cloud Cover (%)</th>
      </tr>
    </thead>
  `;

  const bodyRows = records
    .map((r) => {
      const time = new Date(r.valid_time_local).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      });
      return `
        <tr>
          <td>${time}</td>
          <td class="num">${fmt(r.true_wind_speed, 1)}</td>
          <td class="num">${fmt(r.true_wind_direction, 0)}</td>
          <td class="num">${fmt(r.temperature, 1)}</td>
          <td class="num">${fmt(r.pressure, 1)}</td>
          <td class="num">${fmt(r.cloud_cover, 0)}</td>
        </tr>
      `;
    })
    .join("");

  container.innerHTML = `${headerRow}<tbody>${bodyRows}</tbody>`;
}

export function renderAnalogTable(
  container: HTMLElement,
  analogs: AnalogResult[],
): void {
  if (analogs.length === 0) {
    container.innerHTML = `
      <thead><tr><th colspan="5">No analog days found</th></tr></thead>
    `;
    return;
  }

  const headerRow = `
    <thead>
      <tr>
        <th class="num">Rank</th>
        <th>Date</th>
        <th class="num">Similarity</th>
        <th class="num">Distance</th>
        <th>Summary</th>
      </tr>
    </thead>
  `;

  const bodyRows = analogs
    .map((a) => {
      const similarity =
        a.similarity_score != null
          ? `${(a.similarity_score * 100).toFixed(1)}%`
          : "—";
      const distance =
        a.distance != null ? a.distance.toFixed(3) : "—";
      return `
        <tr>
          <td class="num">${a.rank}</td>
          <td>${a.analog_date}</td>
          <td class="num">${similarity}</td>
          <td class="num">${distance}</td>
          <td>${a.summary ? escapeHtml(a.summary) : "—"}</td>
        </tr>
      `;
    })
    .join("");

  container.innerHTML = `${headerRow}<tbody>${bodyRows}</tbody>`;
}

// --- Quality Indicators ---

export function renderQualityIndicators(
  container: HTMLElement,
  run: AnalysisRunDetail,
  records: WeatherRecord[],
  libraryStatus: LibraryStatusResponse | null,
): void {
  const items: string[] = [];
  const mode = run.mode ?? "historical";

  // Model Init Time (forecast only)
  const modelRunTime = records.find((r) => r.model_run_time)?.model_run_time ?? null;
  if (mode === "forecast" && modelRunTime) {
    const d = new Date(modelRunTime);
    const label = d.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
    items.push(`
      <div class="summary-item">
        <span class="label">Model Init</span>
        <span class="value"><span class="quality-badge neutral">${escapeHtml(label)}</span></span>
      </div>
    `);
  }

  // Data Freshness
  const refTime = mode === "forecast" && modelRunTime
    ? new Date(modelRunTime)
    : run.finished_at
      ? new Date(run.finished_at)
      : null;
  if (refTime) {
    const hoursAgo = Math.round((Date.now() - refTime.getTime()) / 3_600_000);
    const badgeClass = hoursAgo <= 6 ? "good" : hoursAgo <= 12 ? "warning" : "bad";
    items.push(`
      <div class="summary-item">
        <span class="label">Data Freshness</span>
        <span class="value"><span class="quality-badge ${badgeClass}">${hoursAgo}h ago</span></span>
      </div>
    `);
  }

  // Hourly Coverage
  const source = records[0]?.source ?? run.forecast_source ?? run.historical_source ?? "open_meteo";
  const expected = source === "gfs" ? 9 : 24;
  const actual = records.length;
  const missing = Math.max(0, expected - actual);
  const coverageClass = missing === 0 ? "good" : missing <= 3 ? "warning" : "bad";
  items.push(`
    <div class="summary-item">
      <span class="label">Hourly Coverage</span>
      <span class="value"><span class="quality-badge ${coverageClass}">${actual}/${expected} hours${missing > 0 ? ` (${missing} missing)` : ""}</span></span>
    </div>
  `);

  // Library Coverage
  if (libraryStatus && libraryStatus.status !== "no_build" && libraryStatus.total_chunks != null) {
    const completed = libraryStatus.completed_chunks ?? 0;
    const total = libraryStatus.total_chunks;
    const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
    const libClass = pct >= 100 ? "good" : pct >= 50 ? "warning" : "bad";
    items.push(`
      <div class="summary-item">
        <span class="label">Library Coverage</span>
        <span class="value"><span class="quality-badge ${libClass}">${completed}/${total} chunks (${pct}%)</span></span>
      </div>
    `);
  } else {
    items.push(`
      <div class="summary-item">
        <span class="label">Library Coverage</span>
        <span class="value"><span class="quality-badge neutral">No library built</span></span>
      </div>
    `);
  }

  container.innerHTML = items.join("");
}

// --- Bias Table ---

const BIAS_FEATURE_LABELS: Record<string, string> = {
  morning_wind_speed: "Morning Wind Speed",
  afternoon_wind_speed: "Afternoon Wind Speed",
  morning_wind_direction: "Morning Wind Direction",
  afternoon_wind_direction: "Afternoon Wind Direction",
  direction_shift: "Direction Shift",
  speed_increase: "Speed Increase",
  temperature_morning: "Morning Temperature",
  temperature_afternoon: "Afternoon Temperature",
  pressure_morning: "Morning Pressure",
};

export function renderBiasTable(
  container: HTMLElement,
  corrections: BiasCorrection[],
): void {
  if (corrections.length === 0) {
    container.innerHTML = `<thead><tr><th colspan="6">No bias corrections available</th></tr></thead>`;
    return;
  }

  const headerRow = `
    <thead>
      <tr>
        <th>Feature</th>
        <th>Source Pair</th>
        <th class="num">Mean Bias</th>
        <th class="num">&plusmn; Std</th>
        <th class="num">Samples</th>
        <th>Calibration Period</th>
      </tr>
    </thead>
  `;

  const bodyRows = corrections
    .map((c) => {
      const featureLabel = BIAS_FEATURE_LABELS[c.feature_name] ?? c.feature_name;
      const pair = `${escapeHtml(c.forecast_source)} vs ${escapeHtml(c.historical_source)}`;
      return `
        <tr>
          <td>${escapeHtml(featureLabel)}</td>
          <td>${pair}</td>
          <td class="num">${c.bias_mean.toFixed(3)}</td>
          <td class="num">${c.bias_std.toFixed(3)}</td>
          <td class="num">${c.sample_count}</td>
          <td>${escapeHtml(c.calibration_start)} to ${escapeHtml(c.calibration_end)}</td>
        </tr>
      `;
    })
    .join("");

  container.innerHTML = `${headerRow}<tbody>${bodyRows}</tbody>`;
}

function fmt(value: number | null, decimals: number): string {
  return value != null ? value.toFixed(decimals) : "—";
}

function escapeHtml(text: string): string {
  const el = document.createElement("span");
  el.textContent = text;
  return el.innerHTML;
}
