import {
  fetchClassification,
  fetchHealth,
  fetchLocations,
  getAnalysisRun,
  getBiasReport,
  getLibraryStatus,
  getWeatherRecords,
  listAnalysisRuns,
  runAnalysis,
} from "./api";
import { renderWindOverlayChart, renderTempPressureChart, renderDualWindRose, renderBiasChart } from "./charts";
import {
  renderSummaryPanel,
  renderHourlyTable,
  renderAnalogTable,
  renderQualityIndicators,
  renderBiasTable,
} from "./dashboard";
import {
  downloadWeatherCsv,
  downloadAnalogsCsv,
  downloadAnalysisJson,
  downloadWindOverlayChart,
  downloadTempPressureChart,
  downloadMorningWindRoseChart,
  downloadAfternoonWindRoseChart,
  downloadBiasChart,
} from "./export";
import type { AnalysisRunDetail, Location, SeaBreezeClassification, WeatherRecord } from "./types";
import "./styles.css";

// --- DOM refs ---
const healthIndicator = document.getElementById("health-indicator")!;
const locationSelect = document.getElementById("location-select") as HTMLSelectElement;
const targetDateInput = document.getElementById("target-date") as HTMLInputElement;
const histStartInput = document.getElementById("hist-start") as HTMLInputElement;
const histEndInput = document.getElementById("hist-end") as HTMLInputElement;
const topNInput = document.getElementById("top-n") as HTMLInputElement;
const analysisForm = document.getElementById("analysis-form") as HTMLFormElement;
const runBtn = document.getElementById("run-btn") as HTMLButtonElement;
const analysisError = document.getElementById("analysis-error")!;

const summarySection = document.getElementById("summary-section")!;
const summaryPanel = document.getElementById("summary-panel")!;
const chartsSection = document.getElementById("charts-section")!;
const windOverlayEl = document.getElementById("wind-overlay-chart")!;
const tempPressureEl = document.getElementById("temp-pressure-chart")!;
const hourlySection = document.getElementById("hourly-section")!;
const hourlyTable = document.getElementById("hourly-table")!;
const analogSection = document.getElementById("analog-section")!;
const analogTable = document.getElementById("analog-table")!;

// Wind rose
const windroseSection = document.getElementById("windrose-section")!;
const morningWindroseEl = document.getElementById("morning-windrose-chart")!;
const afternoonWindroseEl = document.getElementById("afternoon-windrose-chart")!;

// Bias / Quality
const biasQualitySection = document.getElementById("bias-quality-section")!;
const qualityIndicators = document.getElementById("quality-indicators")!;
const biasChartWrapper = document.getElementById("bias-chart-wrapper")!;
const biasChartEl = document.getElementById("bias-chart")!;
const biasTableEl = document.getElementById("bias-table")!;
const biasNoData = document.getElementById("bias-no-data")!;
const exportBiasPngBtn = document.getElementById("export-bias-png-btn") as HTMLButtonElement;

// Export buttons
const exportJsonBtn = document.getElementById("export-json-btn") as HTMLButtonElement;
const exportWindPngBtn = document.getElementById("export-wind-png-btn") as HTMLButtonElement;
const exportTempPressPngBtn = document.getElementById("export-temp-press-png-btn") as HTMLButtonElement;
const exportWeatherCsvBtn = document.getElementById("export-weather-csv-btn") as HTMLButtonElement;
const exportAnalogsCsvBtn = document.getElementById("export-analogs-csv-btn") as HTMLButtonElement;
const exportMorningWrPngBtn = document.getElementById("export-morning-wr-png-btn") as HTMLButtonElement;
const exportAfternoonWrPngBtn = document.getElementById("export-afternoon-wr-png-btn") as HTMLButtonElement;

// History
const historyList = document.getElementById("history-list")!;
const refreshHistoryBtn = document.getElementById("refresh-history-btn") as HTMLButtonElement;

// Legacy
const healthStatusEl = document.getElementById("health-status")!;
const locationsEl = document.getElementById("locations")!;
const classifyBtn = document.getElementById("classify-btn")!;
const classifyDateInput = document.getElementById("classify-date") as HTMLInputElement;
const classificationResultEl = document.getElementById("classification-result")!;

// --- Store ---
let locations: Location[] = [];
let currentRunId: number | null = null;
let currentTargetDate = "";
let currentMode: "historical" | "forecast" = "historical";

// --- Init ---

async function initHealth() {
  try {
    const data = await fetchHealth();
    healthIndicator.textContent = data.status === "healthy" ? "API healthy" : `API ${data.status}`;
    healthIndicator.className = `health-indicator ${data.status === "healthy" ? "healthy" : "error"}`;

    // Legacy detailed view
    const cssClass = data.status === "healthy" ? "status-healthy" : "status-degraded";
    healthStatusEl.innerHTML = `
      <div class="status-row">
        <span class="status-label">API</span>
        <span class="${cssClass}">${data.status}</span>
      </div>
      <div class="status-row">
        <span class="status-label">Database</span>
        <span class="${cssClass}">${data.database}</span>
      </div>
      <div class="status-row">
        <span class="status-label">Environment</span>
        <span>${data.environment}</span>
      </div>
    `;
  } catch {
    healthIndicator.textContent = "API unreachable";
    healthIndicator.className = "health-indicator error";
    healthStatusEl.innerHTML = `<p class="status-error">Could not reach backend.</p>`;
  }
}

async function initLocations() {
  try {
    locations = await fetchLocations();

    // Populate dropdown
    if (locations.length === 0) {
      locationSelect.innerHTML = `<option value="">No locations found</option>`;
    } else {
      locationSelect.innerHTML = locations
        .map((loc) => `<option value="${loc.id}">${loc.name}</option>`)
        .join("");
    }

    // Legacy card view
    if (locations.length === 0) {
      locationsEl.innerHTML = `<p>No locations found.</p>`;
    } else {
      locationsEl.innerHTML = locations
        .map(
          (loc) => `
        <div class="location-card">
          <div class="location-name">${loc.name}</div>
          <div class="location-detail">
            <span class="location-label">Coordinates</span>
            <span>${loc.latitude.toFixed(4)}, ${loc.longitude.toFixed(4)}</span>
          </div>
          <div class="location-detail">
            <span class="location-label">Timezone</span>
            <span>${loc.timezone}</span>
          </div>
        </div>
      `,
        )
        .join("");
    }
  } catch {
    locationSelect.innerHTML = `<option value="">Failed to load</option>`;
    locationsEl.innerHTML = `<p class="status-error">Could not load locations.</p>`;
  }
}

function setDefaultDates() {
  const today = new Date();
  targetDateInput.value = today.toISOString().slice(0, 10);

  // Sea breeze season defaults: May 1 five years ago to Sep 30 last year
  const endYear = today.getFullYear() - 1;
  const startYear = endYear - 4;
  histStartInput.value = `${startYear}-05-01`;
  histEndInput.value = `${endYear}-09-30`;
}

// --- Mode toggle ---

const modeSelector = document.getElementById("mode-selector")!;
const modeInfoEl = document.createElement("div");
modeInfoEl.className = "mode-info";
modeSelector.appendChild(modeInfoEl);

function applyMode(mode: "historical" | "forecast") {
  currentMode = mode;
  const radio = modeSelector.querySelector<HTMLInputElement>(`input[value="${mode}"]`);
  if (radio) radio.checked = true;

  if (mode === "forecast") {
    // Allow future dates
    targetDateInput.removeAttribute("max");
    // Lock historical range to library defaults
    histStartInput.value = "2015-05-01";
    histEndInput.value = "2024-09-30";
    histStartInput.readOnly = true;
    histEndInput.readOnly = true;
    modeInfoEl.textContent = "Using ERA5 reanalysis library for historical matching";
  } else {
    // Restrict to today
    targetDateInput.max = new Date().toISOString().slice(0, 10);
    histStartInput.readOnly = false;
    histEndInput.readOnly = false;
    modeInfoEl.textContent = "";
  }
}

modeSelector.addEventListener("change", (e) => {
  const target = e.target as HTMLInputElement;
  if (target.name === "mode") {
    applyMode(target.value as "historical" | "forecast");
  }
});

// --- History ---

async function loadHistory() {
  try {
    const runs = await listAnalysisRuns();
    if (runs.length === 0) {
      historyList.innerHTML = `<p class="history-empty">No previous runs found.</p>`;
      return;
    }
    historyList.innerHTML = runs
      .map(
        (run) => `
        <div class="history-item" data-run-id="${run.id}" data-location-id="${run.location_id}" data-target-date="${run.target_date}" data-hist-start="${run.historical_start_date ?? ""}" data-hist-end="${run.historical_end_date ?? ""}" data-top-n="${run.top_n ?? 10}" data-mode="${run.mode ?? "historical"}">
          <span class="hi-date">${run.target_date}</span>
          <span class="hi-meta">${run.status} &middot; ${run.historical_start_date ?? "?"} to ${run.historical_end_date ?? "?"}</span>
        </div>
      `,
      )
      .join("");
  } catch {
    historyList.innerHTML = `<p class="history-empty">Failed to load history.</p>`;
  }
}

historyList.addEventListener("click", async (e) => {
  const item = (e.target as HTMLElement).closest(".history-item") as HTMLElement | null;
  if (!item) return;

  const runId = Number(item.dataset.runId);
  const locationId = Number(item.dataset.locationId);
  const targetDate = item.dataset.targetDate!;
  const histStart = item.dataset.histStart!;
  const histEnd = item.dataset.histEnd!;
  const topN = item.dataset.topN!;
  const mode = (item.dataset.mode ?? "historical") as "historical" | "forecast";

  // Restore form fields
  applyMode(mode);
  locationSelect.value = String(locationId);
  targetDateInput.value = targetDate;
  if (histStart) histStartInput.value = histStart;
  if (histEnd) histEndInput.value = histEnd;
  topNInput.value = topN;

  runBtn.disabled = true;
  runBtn.innerHTML = `<span class="loading-spinner"></span>Loading…`;

  try {
    const analysisRun = await getAnalysisRun(runId);
    const chartSource = analysisRun.forecast_source ?? analysisRun.historical_source ?? undefined;
    const weatherRecords = await getWeatherRecords(locationId, targetDate, targetDate, chartSource);

    currentRunId = runId;
    currentTargetDate = targetDate;

    renderSummaryPanel(summaryPanel, analysisRun);
    summarySection.hidden = false;

    const histSource = chartSource ?? weatherRecords[0]?.source;
    if (weatherRecords.length > 0) {
      chartsSection.hidden = false;
      renderWindOverlayChart(windOverlayEl, weatherRecords, histSource);
      renderTempPressureChart(tempPressureEl, weatherRecords, histSource);

      windroseSection.hidden = false;
      renderDualWindRose(morningWindroseEl, afternoonWindroseEl, weatherRecords, histSource);
    }

    renderHourlyTable(hourlyTable, weatherRecords);
    hourlySection.hidden = false;

    renderAnalogTable(analogTable, analysisRun.analogs);
    analogSection.hidden = false;

    renderBiasQualityPanel(locationId, analysisRun, weatherRecords);
  } catch (err) {
    showError(err instanceof Error ? err.message : "Failed to load run.");
  } finally {
    runBtn.disabled = false;
    runBtn.textContent = "Run Analysis";
  }
});

refreshHistoryBtn.addEventListener("click", () => {
  loadHistory();
});

// --- Analysis ---

analysisForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  analysisError.hidden = true;

  const locationId = Number(locationSelect.value);
  if (!locationId) {
    showError("Please select a location.");
    return;
  }

  runBtn.disabled = true;
  runBtn.innerHTML = `<span class="loading-spinner"></span>Running…`;

  try {
    // Run analysis first — it fetches/caches target-day weather data
    const analysisRun = await runAnalysis({
      location_id: locationId,
      target_date: targetDateInput.value,
      historical_start_date: histStartInput.value,
      historical_end_date: histEndInput.value,
      top_n: Number(topNInput.value),
      mode: currentMode,
      forecast_source: currentMode === "forecast" ? "gfs" : undefined,
      historical_source: currentMode === "forecast" ? "era5" : undefined,
    });
    const chartSource = analysisRun.forecast_source ?? analysisRun.historical_source ?? undefined;
    const weatherRecords = await getWeatherRecords(
      locationId, targetDateInput.value, targetDateInput.value, chartSource,
    );

    currentRunId = analysisRun.id;
    currentTargetDate = targetDateInput.value;

    // Summary
    renderSummaryPanel(summaryPanel, analysisRun);
    summarySection.hidden = false;

    // Charts
    const source = chartSource ?? weatherRecords[0]?.source;
    if (weatherRecords.length > 0) {
      chartsSection.hidden = false;
      renderWindOverlayChart(windOverlayEl, weatherRecords, source);
      renderTempPressureChart(tempPressureEl, weatherRecords, source);

      windroseSection.hidden = false;
      renderDualWindRose(morningWindroseEl, afternoonWindroseEl, weatherRecords, source);
    }

    // Hourly table
    renderHourlyTable(hourlyTable, weatherRecords);
    hourlySection.hidden = false;

    // Analog table
    renderAnalogTable(analogTable, analysisRun.analogs);
    analogSection.hidden = false;

    // Bias / Quality panel
    renderBiasQualityPanel(locationId, analysisRun, weatherRecords);

    // Refresh history to include this new run
    loadHistory();
  } catch (err) {
    showError(err instanceof Error ? err.message : "Analysis failed.");
  } finally {
    runBtn.disabled = false;
    runBtn.textContent = "Run Analysis";
  }
});

function showError(msg: string) {
  analysisError.textContent = msg;
  analysisError.hidden = false;
}

// --- Export handlers ---

exportJsonBtn.addEventListener("click", () => {
  if (currentRunId != null) downloadAnalysisJson(currentRunId, currentTargetDate);
});

exportWindPngBtn.addEventListener("click", () => {
  downloadWindOverlayChart(currentTargetDate);
});

exportTempPressPngBtn.addEventListener("click", () => {
  downloadTempPressureChart(currentTargetDate);
});

exportWeatherCsvBtn.addEventListener("click", () => {
  if (currentRunId != null) downloadWeatherCsv(currentRunId, currentTargetDate);
});

exportAnalogsCsvBtn.addEventListener("click", () => {
  if (currentRunId != null) downloadAnalogsCsv(currentRunId, currentTargetDate);
});

exportMorningWrPngBtn.addEventListener("click", () => {
  downloadMorningWindRoseChart(currentTargetDate);
});

exportAfternoonWrPngBtn.addEventListener("click", () => {
  downloadAfternoonWindRoseChart(currentTargetDate);
});

// --- Bias / Quality panel ---

async function renderBiasQualityPanel(
  locationId: number,
  run: AnalysisRunDetail,
  records: WeatherRecord[],
): Promise<void> {
  const [biasReport, libraryStatus] = await Promise.all([
    getBiasReport(locationId).catch(() => null),
    getLibraryStatus(locationId).catch(() => null),
  ]);

  renderQualityIndicators(qualityIndicators, run, records, libraryStatus);

  const corrections = biasReport?.corrections ?? [];
  if (corrections.length > 0) {
    biasChartWrapper.hidden = false;
    biasNoData.hidden = true;
    renderBiasChart(biasChartEl, corrections);
    renderBiasTable(biasTableEl, corrections);
  } else {
    biasChartWrapper.hidden = true;
    biasNoData.hidden = false;
  }

  biasQualitySection.hidden = false;
}

exportBiasPngBtn.addEventListener("click", () => {
  downloadBiasChart(currentTargetDate);
});

// --- Legacy classification ---

function indicatorLabel(key: string): string {
  const labels: Record<string, string> = {
    speed_increase: "Speed increase",
    direction_shift: "Direction shift",
    onshore_fraction: "Onshore fraction",
  };
  return labels[key] ?? key;
}

function renderClassification(data: SeaBreezeClassification) {
  const levelClass = `level-${data.classification}`;
  const indicatorRows = Object.entries(data.indicators)
    .map(
      ([key, met]) => `
      <div class="indicator-row">
        <span>${indicatorLabel(key)}</span>
        <span class="${met ? "indicator-met" : "indicator-not-met"}">${met ? "Met" : "Not met"}</span>
      </div>
    `,
    )
    .join("");

  classificationResultEl.innerHTML = `
    <div class="classification-card">
      <div class="classification-level ${levelClass}">${data.classification}</div>
      <div class="classification-score">Score: ${(data.score * 100).toFixed(0)}%</div>
      ${indicatorRows}
    </div>
  `;
}

classifyBtn.addEventListener("click", async () => {
  const dateValue = classifyDateInput.value;
  if (!dateValue) {
    classificationResultEl.innerHTML = `<p class="status-error">Please select a date.</p>`;
    return;
  }

  classificationResultEl.innerHTML = `<p>Classifying…</p>`;

  try {
    const data = await fetchClassification(1, dateValue);
    renderClassification(data);
  } catch {
    classificationResultEl.innerHTML = `<p class="status-error">Classification failed. Make sure weather data is fetched for this date.</p>`;
  }
});

// --- Boot ---

initHealth();
initLocations();
setDefaultDates();
loadHistory();
