import type { AnalogResult, AnalysisRunDetail, BiasCorrection, LibraryStatusResponse, SeaBreezePanelData, WeatherRecord } from "./types";
import { renderAnalogDonutChart } from "./charts";

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

// --- Sea Breeze Gauges ---

export function renderSeaBreezeGauges(
  container: HTMLElement,
  data: SeaBreezePanelData,
): void {
  if (!data.target) {
    container.innerHTML = `<p style="color:#868e96;font-size:0.9rem;">Insufficient weather data to classify the target day.</p>`;
    return;
  }

  const f = data.target.features;
  const t = data.thresholds;
  const cls = data.target.classification;

  const absShift = Math.abs(f.wind_direction_shift ?? 0);

  const gauges = [
    {
      label: "Speed Increase",
      value: f.wind_speed_increase,
      gaugeValue: f.wind_speed_increase ?? 0,
      max: Math.max(t.minimum_speed_increase_mps * 2, (f.wind_speed_increase ?? 0) * 1.3, 5),
      threshold: t.minimum_speed_increase_mps,
      unit: "m/s",
      met: cls.indicators.speed_increase ?? false,
    },
    {
      label: "Direction Shift",
      value: f.wind_direction_shift,
      gaugeValue: absShift,
      max: Math.max(t.minimum_direction_shift_degrees * 2, absShift * 1.3, 90),
      threshold: t.minimum_direction_shift_degrees,
      unit: "°",
      met: cls.indicators.direction_shift ?? false,
    },
    {
      label: "Onshore Fraction",
      value: f.onshore_fraction,
      gaugeValue: f.onshore_fraction ?? 0,
      max: 1,
      threshold: t.minimum_onshore_fraction,
      unit: "",
      met: cls.indicators.onshore_fraction ?? false,
    },
  ];

  const gaugeHtml = gauges
    .map((g) => {
      const pct = Math.min((g.gaugeValue / g.max) * 100, 100);
      const threshPct = Math.min((g.threshold / g.max) * 100, 100);
      const color = g.met ? "#2b8a3e" : "#c92a2a";
      const raw = g.value ?? 0;
      const displayVal = g.unit === "" ? `${(raw * 100).toFixed(0)}%` : `${raw.toFixed(1)} ${g.unit}`;
      return `
        <div class="sb-gauge">
          <div class="sb-gauge-label">
            <span>${g.label}</span>
            <span>${displayVal}</span>
          </div>
          <div class="sb-gauge-bar-track">
            <div class="sb-gauge-bar-fill" style="width:${pct}%;background:${color}"></div>
            <div class="sb-gauge-threshold" style="left:${threshPct}%" title="Threshold: ${g.unit === '' ? `${(g.threshold * 100).toFixed(0)}%` : `${g.threshold} ${g.unit}`}"></div>
          </div>
        </div>
      `;
    })
    .join("");

  const levelClass = `level-${cls.classification}`;
  container.innerHTML = `
    <div class="sb-gauges-panel">
      ${gaugeHtml}
      <div>
        <span class="sb-classification-badge ${levelClass}">${cls.classification} sea breeze</span>
        <span style="margin-left:0.5rem;font-size:0.85rem;color:#868e96;">Score: ${(cls.score * 100).toFixed(0)}%</span>
      </div>
    </div>
  `;
}

// --- Analog Probability ---

export function renderAnalogProbability(
  container: HTMLElement,
  data: SeaBreezePanelData,
): void {
  const { analog_high_count, analog_total } = data;
  const pct = analog_total > 0 ? Math.round((analog_high_count / analog_total) * 100) : 0;

  container.innerHTML = `
    <div class="sb-probability-panel">
      <div>
        <div class="sb-prob-number">${analog_high_count}/${analog_total} analogs (${pct}%)</div>
        <div class="sb-prob-subtitle">had a strong sea breeze</div>
      </div>
      <div id="sb-donut-chart" class="sb-donut-container"></div>
    </div>
  `;

  const donutEl = container.querySelector("#sb-donut-chart") as HTMLElement;
  if (donutEl) {
    renderAnalogDonutChart(
      donutEl,
      data.analog_high_count,
      data.analog_medium_count,
      data.analog_low_count,
    );
  }
}

function fmt(value: number | null, decimals: number): string {
  return value != null ? value.toFixed(decimals) : "—";
}

function escapeHtml(text: string): string {
  const el = document.createElement("span");
  el.textContent = text;
  return el.innerHTML;
}
