import type { AnalogResult, AnalysisRunDetail, BiasCorrection, ForecastCompositeData, LibraryStatusResponse, SeaBreezePanelData, ValidationMetrics, WeatherRecord } from "./types";
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

// --- Forecast Composite ---

export function renderForecastGateBadge(
  container: HTMLElement,
  data: ForecastCompositeData,
): void {
  const gate = data.gate_result;
  const colorMap: Record<string, string> = {
    high: "#2b8a3e",
    medium: "#e67700",
    low: "#c92a2a",
    insufficient_data: "#868e96",
  };
  const color = colorMap[gate] ?? "#868e96";

  if (gate === "insufficient_data") {
    container.innerHTML = `
      <div style="padding:0.75rem;border-radius:0.5rem;background:#f8f9fa;border:1px solid #dee2e6;margin-bottom:1rem;">
        <span style="display:inline-block;padding:0.2rem 0.6rem;border-radius:0.25rem;background:${color};color:#fff;font-weight:600;font-size:0.85rem;">Insufficient data</span>
        <span style="margin-left:0.5rem;color:#495057;font-size:0.9rem;">Not enough forecast data to classify sea breeze probability.</span>
      </div>
    `;
  } else if (gate === "low") {
    container.innerHTML = `
      <div style="padding:0.75rem;border-radius:0.5rem;background:#fff5f5;border:1px solid #ffc9c9;margin-bottom:1rem;">
        <span style="display:inline-block;padding:0.2rem 0.6rem;border-radius:0.25rem;background:${color};color:#fff;font-weight:600;font-size:0.85rem;">Low sea breeze probability</span>
        <span style="margin-left:0.5rem;color:#495057;font-size:0.9rem;">No forecast composite produced.</span>
      </div>
    `;
  } else {
    container.innerHTML = `
      <div style="margin-bottom:0.75rem;">
        <span style="display:inline-block;padding:0.2rem 0.6rem;border-radius:0.25rem;background:${color};color:#fff;font-weight:600;font-size:0.85rem;">${gate} sea breeze probability</span>
        <span style="margin-left:0.5rem;color:#868e96;font-size:0.85rem;">Forecast composite from analog days</span>
      </div>
    `;
  }
}

export function renderForecastTable(
  container: HTMLElement,
  data: ForecastCompositeData,
): void {
  if (!data.hours || data.hours.length === 0) {
    container.innerHTML = "";
    return;
  }

  const headerRow = `
    <thead>
      <tr>
        <th>Hour</th>
        <th class="num">Median TWS (m/s)</th>
        <th class="num">IQR (m/s)</th>
        <th class="num">90% Range (m/s)</th>
        <th class="num">Mean TWD</th>
        <th class="num">Spread</th>
        <th class="num">Analogs</th>
      </tr>
    </thead>
  `;

  const bodyRows = data.hours
    .map((h) => {
      const iqr = h.p25_tws != null && h.p75_tws != null
        ? `${h.p25_tws.toFixed(1)}\u2013${h.p75_tws.toFixed(1)}`
        : "\u2014";
      const range90 = h.p10_tws != null && h.p90_tws != null
        ? `${h.p10_tws.toFixed(1)}\u2013${h.p90_tws.toFixed(1)}`
        : "\u2014";
      const twd = h.circular_mean_twd != null ? `${h.circular_mean_twd.toFixed(0)}\u00b0` : "\u2014";
      const spread = h.twd_circular_std != null ? `\u00b1${h.twd_circular_std.toFixed(0)}\u00b0` : "\u2014";
      return `
        <tr>
          <td>${String(h.hour_local).padStart(2, "0")}:00</td>
          <td class="num">${h.median_tws != null ? h.median_tws.toFixed(1) : "\u2014"}</td>
          <td class="num">${iqr}</td>
          <td class="num">${range90}</td>
          <td class="num">${twd}</td>
          <td class="num">${spread}</td>
          <td class="num">${h.analog_count}</td>
        </tr>
      `;
    })
    .join("");

  container.innerHTML = `${headerRow}<tbody>${bodyRows}</tbody>`;
}

export function renderValidationMetrics(
  container: HTMLElement,
  metrics: ValidationMetrics,
): void {
  function badge(value: number | null, thresholds: [number, number], unit: string): string {
    if (value == null) return `<span class="quality-badge neutral">N/A</span>`;
    const cls = value <= thresholds[0] ? "good" : value <= thresholds[1] ? "warning" : "bad";
    return `<span class="quality-badge ${cls}">${value.toFixed(1)} ${unit}</span>`;
  }

  const items: string[] = [];

  items.push(`
    <div class="summary-item">
      <span class="label">TWS MAE (11\u201316h)</span>
      <span class="value">${badge(metrics.tws_mae, [1, 2], "m/s")}</span>
    </div>
  `);

  items.push(`
    <div class="summary-item">
      <span class="label">TWD Circular MAE</span>
      <span class="value">${badge(metrics.twd_circular_mae, [30, 60], "\u00b0")}</span>
    </div>
  `);

  items.push(`
    <div class="summary-item">
      <span class="label">Peak Speed</span>
      <span class="value">${metrics.peak_speed_forecast != null ? metrics.peak_speed_forecast.toFixed(1) : "\u2014"} vs ${metrics.peak_speed_observed != null ? metrics.peak_speed_observed.toFixed(1) : "\u2014"} m/s${metrics.peak_speed_error != null ? ` (\u0394${metrics.peak_speed_error.toFixed(1)})` : ""}</span>
    </div>
  `);

  items.push(`
    <div class="summary-item">
      <span class="label">Onset Hour</span>
      <span class="value">${metrics.onset_hour_forecast != null ? `${String(metrics.onset_hour_forecast).padStart(2, "0")}:00` : "\u2014"} vs ${metrics.onset_hour_observed != null ? `${String(metrics.onset_hour_observed).padStart(2, "0")}:00` : "\u2014"}${metrics.onset_error_hours != null ? ` (\u0394${metrics.onset_error_hours}h)` : ""}</span>
    </div>
  `);

  items.push(`
    <div class="summary-item">
      <span class="label">Matched Hours</span>
      <span class="value">${metrics.matched_hours} of ${metrics.total_forecast_hours} forecast / ${metrics.total_observation_hours} observed</span>
    </div>
  `);

  container.innerHTML = items.join("");
}

function fmt(value: number | null, decimals: number): string {
  return value != null ? value.toFixed(decimals) : "\u2014";
}

function escapeHtml(text: string): string {
  const el = document.createElement("span");
  el.textContent = text;
  return el.innerHTML;
}
