import type { AnalogResult, AnalysisRunDetail, WeatherRecord } from "./types";

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

function fmt(value: number | null, decimals: number): string {
  return value != null ? value.toFixed(decimals) : "—";
}

function escapeHtml(text: string): string {
  const el = document.createElement("span");
  el.textContent = text;
  return el.innerHTML;
}
