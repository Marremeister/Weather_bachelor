import {
  fetchClassification,
  fetchHealth,
  fetchLocations,
  fetchObservations,
  fetchStations,
  getAnalogHourly,
  getAnalysisRun,
  getBiasReport,
  getDistanceDistribution,
  getForecastComposite,
  getLibraryStatus,
  getObservations,
  getSeaBreezePanel,
  getSeasonalHeatmap,
  getValidationMetrics,
  getValidationRunResult,
  getValidationRunStatus,
  getWeatherRecords,
  listAnalysisRuns,
  listBatchValidationRuns,
  runAnalysis,
  triggerBatchValidation,
  triggerLibraryBuild,
} from "./api";
import { renderWindOverlayChart, renderTempPressureChart, renderDualWindRose, renderBiasChart, renderAnalogOverlayChart, renderWindSpeedIncreaseChart, renderFeatureRadarChart, renderDirectionShiftChart, renderSeasonalHeatmapChart, renderDistanceHistogramChart, renderForecastChart, disposeForecastChart, renderValidationTimeSeriesChart, renderValidationHistogramChart, renderValidationMonthlyChart, disposeValidationCharts, renderValDetailForecastChart, disposeValDetailChart, resizeChartById } from "./charts";
import { TabController } from "./tabs";
import { ExportMenu } from "./export-menu";
import {
  renderSummaryPanel,
  renderHourlyTable,
  renderAnalogTable,
  renderQualityIndicators,
  renderBiasTable,
  renderSeaBreezeGauges,
  renderAnalogProbability,
  renderForecastGateBadge,
  renderForecastTable,
  renderValidationMetrics,
  renderBatchClassificationMetrics,
  renderBatchContinuousMetrics,
  renderGateSensitivityTable,
  renderSourceStratificationTable,
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
  downloadAnalogOverlayChart,
  downloadSpeedIncreaseChart,
  downloadFeatureRadarChart,
  downloadDirectionShiftChart,
  downloadSeasonalHeatmapChart,
  downloadDistanceHistogramChart,
  downloadForecastChart,
  downloadForecastCsv,
} from "./export";
import type { AnalogHourlyResponse, AnalysisRunDetail, ForecastCompositeData, Location, ObservationRecord, SeaBreezeClassification, SeaBreezePanelData, SeasonalHeatmapData, ValidationRunResult, WeatherRecord, WeatherStation } from "./types";
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
const windStationSelect = document.getElementById("wind-station-select") as HTMLSelectElement;
const windOverlayEl = document.getElementById("wind-overlay-chart")!;
const tempPressureEl = document.getElementById("temp-pressure-chart")!;
const hourlySection = document.getElementById("hourly-section")!;
const hourlyTable = document.getElementById("hourly-table")!;
const analogSection = document.getElementById("analog-section")!;
const analogTable = document.getElementById("analog-table")!;

// Sea Breeze Panel
const seaBreezeSection = document.getElementById("sea-breeze-section")!;
const sbGaugesPanel = document.getElementById("sb-gauges-panel")!;
const sbProbabilityPanel = document.getElementById("sb-probability-panel")!;

// Analog Overlay
const analogOverlaySection = document.getElementById("analog-overlay-section")!;
const analogOverlayChartEl = document.getElementById("analog-overlay-chart")!;
const speedIncreaseChartEl = document.getElementById("speed-increase-chart")!;
const analogMetricToggle = document.getElementById("analog-metric-toggle")!;
const exportAnalogOverlayPngBtn = document.getElementById("export-analog-overlay-png-btn") as HTMLButtonElement;
const exportSpeedIncreasePngBtn = document.getElementById("export-speed-increase-png-btn") as HTMLButtonElement;

// Feature Radar & Direction Shift
const featureRadarSection = document.getElementById("feature-radar-section")!;
const featureRadarChartEl = document.getElementById("feature-radar-chart")!;
const directionShiftChartEl = document.getElementById("direction-shift-chart")!;
const exportFeatureRadarPngBtn = document.getElementById("export-feature-radar-png-btn") as HTMLButtonElement;
const exportDirectionShiftPngBtn = document.getElementById("export-direction-shift-png-btn") as HTMLButtonElement;

// Phase 6: Seasonal Heatmap & Distance Distribution
const seasonalHeatmapSection = document.getElementById("seasonal-heatmap-section")!;
const seasonalHeatmapChartEl = document.getElementById("seasonal-heatmap-chart")!;
const heatmapColorToggle = document.getElementById("heatmap-color-toggle")!;
const exportSeasonalHeatmapPngBtn = document.getElementById("export-seasonal-heatmap-png-btn") as HTMLButtonElement;
const distanceDistributionSection = document.getElementById("distance-distribution-section")!;
const distanceHistogramChartEl = document.getElementById("distance-histogram-chart")!;
const exportDistanceHistogramPngBtn = document.getElementById("export-distance-histogram-png-btn") as HTMLButtonElement;

// Forecast Composite
const forecastCompositeSection = document.getElementById("forecast-composite-section")!;
const forecastGateBadge = document.getElementById("forecast-gate-badge")!;
const forecastChartEl = document.getElementById("forecast-chart")!;
const forecastTableEl = document.getElementById("forecast-table")!;
const forecastTracesToggle = document.getElementById("forecast-traces-toggle") as HTMLInputElement;
const exportForecastPngBtn = document.getElementById("export-forecast-png-btn") as HTMLButtonElement;

// Validation / Observations
const validationSection = document.getElementById("validation-section")!;
const stationSelect = document.getElementById("station-select") as HTMLSelectElement;
const validationMetricsEl = document.getElementById("validation-metrics")!;

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

// Export buttons (PNG only — CSV/JSON moved to export dropdown)
const exportWindPngBtn = document.getElementById("export-wind-png-btn") as HTMLButtonElement;
const exportTempPressPngBtn = document.getElementById("export-temp-press-png-btn") as HTMLButtonElement;
const exportMorningWrPngBtn = document.getElementById("export-morning-wr-png-btn") as HTMLButtonElement;
const exportAfternoonWrPngBtn = document.getElementById("export-afternoon-wr-png-btn") as HTMLButtonElement;

// History
const historyList = document.getElementById("history-list")!;
const refreshHistoryBtn = document.getElementById("refresh-history-btn") as HTMLButtonElement;

// Feature Library
const buildLibraryBtn = document.getElementById("build-library-btn") as HTMLButtonElement;
const libraryStatusMsg = document.getElementById("library-status-msg")!;

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
let currentStations: WeatherStation[] = [];
let currentObservations: ObservationRecord[] = [];
let currentWeatherRecords: WeatherRecord[] = [];
let currentChartSource: string | undefined;
let currentAnalogHourly: AnalogHourlyResponse | null = null;
let currentAnalogMetric: "tws" | "twd" = "tws";
let currentHeatmapData: SeasonalHeatmapData | null = null;
let currentHeatmapColorMode: "speed" | "classification" = "speed";
let currentForecastData: ForecastCompositeData | null = null;
let currentForecastTraces: AnalogHourlyResponse | null = null;
let forecastTracesVisible = false;

// --- Tab Controller ---

const PANEL_CHART_IDS: Record<string, string[]> = {
  results: ["forecast-chart"],
  analysis: [
    "analog-overlay-chart", "speed-increase-chart",
    "feature-radar-chart", "direction-shift-chart",
    "seasonal-heatmap-chart", "distance-histogram-chart",
  ],
  data: [
    "wind-overlay-chart", "temp-pressure-chart",
    "morning-windrose-chart", "afternoon-windrose-chart",
    "bias-chart",
  ],
  validation: [
    "val-timeseries-chart", "val-histogram-chart", "val-monthly-chart",
  ],
};

function handleTabSwitch(tabId: string) {
  const chartIds = PANEL_CHART_IDS[tabId];
  if (chartIds) {
    // Small delay to let the panel become visible before resizing
    requestAnimationFrame(() => {
      for (const id of chartIds) {
        resizeChartById(id);
      }
    });
  }
}

const tabController = new TabController("results-tabs", [
  { id: "results", label: "Results", panelId: "panel-results" },
  { id: "analysis", label: "Analysis", panelId: "panel-analysis" },
  { id: "data", label: "Data", panelId: "panel-data" },
  { id: "validation", label: "Validation", panelId: "panel-validation" },
], { onSwitch: handleTabSwitch });

// --- Export Dropdown ---

const exportMenu = new ExportMenu("export-menu-btn", "export-menu", [
  { id: "json", label: "Analysis JSON", group: "data", handler: () => { if (currentRunId != null) downloadAnalysisJson(currentRunId, currentTargetDate); } },
  { id: "weather-csv", label: "Weather CSV", group: "data", handler: () => { if (currentRunId != null) downloadWeatherCsv(currentRunId, currentTargetDate); } },
  { id: "analogs-csv", label: "Analogs CSV", group: "data", handler: () => { if (currentRunId != null) downloadAnalogsCsv(currentRunId, currentTargetDate); } },
  { id: "forecast-csv", label: "Forecast CSV", group: "data", handler: () => { if (currentRunId != null) downloadForecastCsv(currentRunId, currentTargetDate); }, enabled: () => currentMode === "forecast" && currentForecastData != null && (currentForecastData.hours?.length ?? 0) > 0 },
  { id: "val-csv", label: "Validation CSV", group: "data", handler: () => { if (currentValRunId != null) window.open(`/api/validation/${currentValRunId}/export/csv`, "_blank"); }, enabled: () => currentValRunId != null && !valResults.hidden },
]);

// Suppress unused-variable lint for exportMenu
void exportMenu;

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

async function initStations() {
  try {
    currentStations = await fetchStations();
    if (currentStations.length > 0) {
      const options = currentStations
        .map((s) => `<option value="${s.id}">${s.station_code} — ${s.name}</option>`)
        .join("");
      stationSelect.innerHTML = `<option value="">Select station...</option>` + options;
      windStationSelect.innerHTML = `<option value="">Overlay station...</option>` + options;
    }
  } catch {
    // Stations are optional; don't block boot
  }
}

async function loadObservationOverlay() {
  const stationId = Number(stationSelect.value);
  if (!stationId || !currentRunId || !currentTargetDate || !currentForecastData) {
    currentObservations = [];
    validationMetricsEl.innerHTML = "";
    // Re-render chart without observations
    if (currentForecastData) {
      const traces = forecastTracesVisible ? currentForecastTraces?.analogs : undefined;
      renderForecastChart(forecastChartEl, currentForecastData, traces, forecastTracesVisible);
    }
    return;
  }

  try {
    // Fetch + cache observations
    await fetchObservations(stationId, currentTargetDate, currentTargetDate);
    currentObservations = await getObservations(stationId, currentTargetDate, currentTargetDate);

    // Re-render chart with observation overlay
    const traces = forecastTracesVisible ? currentForecastTraces?.analogs : undefined;
    renderForecastChart(forecastChartEl, currentForecastData, traces, forecastTracesVisible, currentObservations);

    // Load validation metrics
    const metrics = await getValidationMetrics(currentRunId, stationId);
    renderValidationMetrics(validationMetricsEl, metrics);
  } catch {
    currentObservations = [];
    validationMetricsEl.innerHTML = `<p style="color:#868e96;font-size:0.85rem;">Could not load observations or validation metrics.</p>`;
  }
}

stationSelect.addEventListener("change", () => {
  loadObservationOverlay();
});

async function loadWindObservationOverlay() {
  const stationId = Number(windStationSelect.value);
  if (!stationId || !currentTargetDate || currentWeatherRecords.length === 0) {
    // Re-render without observations
    if (currentWeatherRecords.length > 0) {
      renderWindOverlayChart(windOverlayEl, currentWeatherRecords, currentChartSource);
    }
    return;
  }

  try {
    await fetchObservations(stationId, currentTargetDate, currentTargetDate);
    const obs = await getObservations(stationId, currentTargetDate, currentTargetDate);
    renderWindOverlayChart(windOverlayEl, currentWeatherRecords, currentChartSource, obs);
  } catch {
    renderWindOverlayChart(windOverlayEl, currentWeatherRecords, currentChartSource);
  }
}

windStationSelect.addEventListener("change", () => {
  loadWindObservationOverlay();
});

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

    // Show tab bar and switch to Results tab
    tabController.show();
    tabController.switchTo("results");

    renderSummaryPanel(summaryPanel, analysisRun);
    summarySection.hidden = false;

    const histSource = chartSource ?? weatherRecords[0]?.source;
    currentWeatherRecords = weatherRecords;
    currentChartSource = histSource;
    if (weatherRecords.length > 0) {
      chartsSection.hidden = false;
      renderWindOverlayChart(windOverlayEl, weatherRecords, histSource);
      renderTempPressureChart(tempPressureEl, weatherRecords, histSource);

      windroseSection.hidden = false;
      renderDualWindRose(morningWindroseEl, afternoonWindroseEl, weatherRecords, histSource);

      if (windStationSelect.value) loadWindObservationOverlay();
    }

    renderHourlyTable(hourlyTable, weatherRecords);
    hourlySection.hidden = false;

    renderAnalogTable(analogTable, analysisRun.analogs);
    analogSection.hidden = false;

    renderBiasQualityPanel(locationId, analysisRun, weatherRecords);

    const analogDates = analysisRun.analogs.map((a) => a.analog_date);
    const librarySource = analysisRun.historical_source ?? "era5";

    getSeaBreezePanel(runId).then((panelData) => {
      renderSeaBreezeGauges(sbGaugesPanel, panelData);
      renderAnalogProbability(sbProbabilityPanel, panelData);
      seaBreezeSection.hidden = false;
      renderAnalogOverlayPanel(runId, panelData);
    }).catch(() => { seaBreezeSection.hidden = true; analogOverlaySection.hidden = true; featureRadarSection.hidden = true; });

    // Forecast composite (non-blocking)
    renderForecastPanel(runId, mode).catch(() => { forecastCompositeSection.hidden = true; });

    // Phase 6 panels (non-blocking)
    renderPhase6Panels(runId, locationId, targetDate, analogDates, librarySource).catch(() => {
      seasonalHeatmapSection.hidden = true;
      distanceDistributionSection.hidden = true;
    });
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

// --- Feature Library ---

let libraryPollTimer: number | null = null;

function formatLibraryStatus(s: Awaited<ReturnType<typeof getLibraryStatus>> | null): string {
  if (!s || !s.status || s.status === "no_build") {
    return "No library built yet for this location. Click Build Library to start.";
  }
  const done = s.completed_chunks ?? 0;
  const total = s.total_chunks ?? 0;
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  const src = s.source ? ` (${s.source})` : "";
  if (s.status === "building" || s.status === "pending") {
    return `Building${src}… ${done}/${total} chunks (${pct}%).`;
  }
  if (s.status === "completed") {
    return `Library ready${src}: ${done}/${total} chunks (${pct}%).`;
  }
  if (s.status === "failed") {
    return `Build failed${src}: ${s.error_message ?? "unknown error"}.`;
  }
  return `Status: ${s.status}${src} — ${done}/${total} chunks.`;
}

async function loadLibraryStatus(locationId?: number) {
  const locId = locationId ?? Number(locationSelect.value);
  if (!locId) {
    libraryStatusMsg.textContent = "Select a location to see library status.";
    return;
  }
  try {
    const status = await getLibraryStatus(locId);
    libraryStatusMsg.textContent = formatLibraryStatus(status);
    // Auto-poll while building
    if (status && (status.status === "building" || status.status === "pending")) {
      startLibraryPoll(locId);
    } else {
      stopLibraryPoll();
    }
  } catch {
    libraryStatusMsg.textContent = "Could not load library status.";
    stopLibraryPoll();
  }
}

function startLibraryPoll(locationId: number) {
  if (libraryPollTimer != null) return;
  libraryPollTimer = window.setInterval(() => {
    loadLibraryStatus(locationId);
  }, 5000);
}

function stopLibraryPoll() {
  if (libraryPollTimer != null) {
    window.clearInterval(libraryPollTimer);
    libraryPollTimer = null;
  }
}

buildLibraryBtn.addEventListener("click", async () => {
  const locationId = Number(locationSelect.value);
  if (!locationId) {
    libraryStatusMsg.textContent = "Select a location before building the library.";
    return;
  }
  buildLibraryBtn.disabled = true;
  const originalText = buildLibraryBtn.textContent ?? "Build Library";
  buildLibraryBtn.innerHTML = `<span class="loading-spinner"></span>Starting…`;
  try {
    await triggerLibraryBuild(locationId);
    libraryStatusMsg.textContent = "Build triggered — polling status…";
    await loadLibraryStatus(locationId);
  } catch (err) {
    libraryStatusMsg.textContent = err instanceof Error
      ? `Failed to trigger build: ${err.message}`
      : "Failed to trigger build.";
  } finally {
    buildLibraryBtn.disabled = false;
    buildLibraryBtn.textContent = originalText;
  }
});

locationSelect.addEventListener("change", () => {
  stopLibraryPoll();
  loadLibraryStatus();
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

    // Show tab bar and switch to Results tab
    tabController.show();
    tabController.switchTo("results");

    // Summary
    renderSummaryPanel(summaryPanel, analysisRun);
    summarySection.hidden = false;

    // Charts
    const source = chartSource ?? weatherRecords[0]?.source;
    currentWeatherRecords = weatherRecords;
    currentChartSource = source;
    if (weatherRecords.length > 0) {
      chartsSection.hidden = false;
      renderWindOverlayChart(windOverlayEl, weatherRecords, source);
      renderTempPressureChart(tempPressureEl, weatherRecords, source);

      windroseSection.hidden = false;
      renderDualWindRose(morningWindroseEl, afternoonWindroseEl, weatherRecords, source);

      if (windStationSelect.value) loadWindObservationOverlay();
    }

    // Hourly table
    renderHourlyTable(hourlyTable, weatherRecords);
    hourlySection.hidden = false;

    // Analog table
    renderAnalogTable(analogTable, analysisRun.analogs);
    analogSection.hidden = false;

    // Bias / Quality panel
    renderBiasQualityPanel(locationId, analysisRun, weatherRecords);

    // Sea Breeze panel (non-blocking)
    getSeaBreezePanel(analysisRun.id).then((panelData) => {
      renderSeaBreezeGauges(sbGaugesPanel, panelData);
      renderAnalogProbability(sbProbabilityPanel, panelData);
      seaBreezeSection.hidden = false;
      renderAnalogOverlayPanel(analysisRun.id, panelData);
    }).catch(() => { seaBreezeSection.hidden = true; analogOverlaySection.hidden = true; featureRadarSection.hidden = true; });

    // Forecast composite (non-blocking)
    renderForecastPanel(analysisRun.id, currentMode).catch(() => { forecastCompositeSection.hidden = true; });

    // Phase 6 panels (non-blocking)
    const analogDates = analysisRun.analogs.map((a) => a.analog_date);
    const p6Source = analysisRun.historical_source ?? "era5";
    renderPhase6Panels(analysisRun.id, locationId, targetDateInput.value, analogDates, p6Source).catch(() => {
      seasonalHeatmapSection.hidden = true;
      distanceDistributionSection.hidden = true;
    });

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

exportWindPngBtn.addEventListener("click", () => {
  downloadWindOverlayChart(currentTargetDate);
});

exportTempPressPngBtn.addEventListener("click", () => {
  downloadTempPressureChart(currentTargetDate);
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

// --- Analog Overlay Panel ---

async function renderAnalogOverlayPanel(
  runId: number,
  panelData: SeaBreezePanelData,
): Promise<void> {
  try {
    const data = await getAnalogHourly(runId);
    currentAnalogHourly = data;
    currentAnalogMetric = "tws";

    // Reset toggle to TWS
    for (const btn of analogMetricToggle.querySelectorAll<HTMLButtonElement>(".toggle-btn")) {
      btn.classList.toggle("active", btn.dataset.metric === "tws");
    }

    renderAnalogOverlayChart(analogOverlayChartEl, data.target, data.analogs, "tws");
    renderWindSpeedIncreaseChart(speedIncreaseChartEl, panelData);
    analogOverlaySection.hidden = false;

    renderFeatureRadarChart(featureRadarChartEl, panelData);
    renderDirectionShiftChart(directionShiftChartEl, panelData);
    featureRadarSection.hidden = false;
  } catch {
    analogOverlaySection.hidden = true;
    featureRadarSection.hidden = true;
  }
}

// TWS / TWD toggle
analogMetricToggle.addEventListener("click", (e) => {
  const btn = (e.target as HTMLElement).closest(".toggle-btn") as HTMLButtonElement | null;
  if (!btn || !currentAnalogHourly) return;
  const metric = btn.dataset.metric as "tws" | "twd";
  if (metric === currentAnalogMetric) return;

  currentAnalogMetric = metric;
  for (const b of analogMetricToggle.querySelectorAll<HTMLButtonElement>(".toggle-btn")) {
    b.classList.toggle("active", b.dataset.metric === metric);
  }
  renderAnalogOverlayChart(analogOverlayChartEl, currentAnalogHourly.target, currentAnalogHourly.analogs, metric);
});

// Analog overlay export buttons
exportAnalogOverlayPngBtn.addEventListener("click", () => {
  downloadAnalogOverlayChart(currentTargetDate);
});

exportSpeedIncreasePngBtn.addEventListener("click", () => {
  downloadSpeedIncreaseChart(currentTargetDate);
});

// Feature Radar & Direction Shift export buttons
exportFeatureRadarPngBtn.addEventListener("click", () => {
  downloadFeatureRadarChart(currentTargetDate);
});

exportDirectionShiftPngBtn.addEventListener("click", () => {
  downloadDirectionShiftChart(currentTargetDate);
});

// --- Phase 6: Seasonal Heatmap & Distance Distribution ---

async function renderPhase6Panels(
  runId: number,
  locationId: number,
  targetDate: string,
  analogDates: string[],
  historicalSource: string,
): Promise<void> {
  // Fetch both endpoints in parallel, non-blocking
  const [heatmapResult, distResult] = await Promise.allSettled([
    getSeasonalHeatmap(locationId, historicalSource, targetDate, analogDates),
    getDistanceDistribution(runId),
  ]);

  if (heatmapResult.status === "fulfilled" && heatmapResult.value.days.length > 0) {
    currentHeatmapData = heatmapResult.value;
    currentHeatmapColorMode = "speed";
    // Reset toggle
    for (const btn of heatmapColorToggle.querySelectorAll<HTMLButtonElement>(".toggle-btn")) {
      btn.classList.toggle("active", btn.dataset.mode === "speed");
    }
    seasonalHeatmapSection.hidden = false;
    renderSeasonalHeatmapChart(seasonalHeatmapChartEl, currentHeatmapData, "speed");
  } else {
    seasonalHeatmapSection.hidden = true;
  }

  if (distResult.status === "fulfilled" && distResult.value.entries.length > 0) {
    distanceDistributionSection.hidden = false;
    renderDistanceHistogramChart(distanceHistogramChartEl, distResult.value);
  } else {
    distanceDistributionSection.hidden = true;
  }
}

// Heatmap color toggle
heatmapColorToggle.addEventListener("click", (e) => {
  const btn = (e.target as HTMLElement).closest(".toggle-btn") as HTMLButtonElement | null;
  if (!btn || !currentHeatmapData) return;
  const mode = btn.dataset.mode as "speed" | "classification";
  if (mode === currentHeatmapColorMode) return;

  currentHeatmapColorMode = mode;
  for (const b of heatmapColorToggle.querySelectorAll<HTMLButtonElement>(".toggle-btn")) {
    b.classList.toggle("active", b.dataset.mode === mode);
  }
  renderSeasonalHeatmapChart(seasonalHeatmapChartEl, currentHeatmapData, mode);
});

// Phase 6 export buttons
exportSeasonalHeatmapPngBtn.addEventListener("click", () => {
  downloadSeasonalHeatmapChart(currentTargetDate);
});

exportDistanceHistogramPngBtn.addEventListener("click", () => {
  downloadDistanceHistogramChart(currentTargetDate);
});

// --- Forecast Composite Panel ---

async function renderForecastPanel(
  runId: number,
  mode: string,
): Promise<void> {
  // Hide for historical mode
  if (mode !== "forecast") {
    forecastCompositeSection.hidden = true;
    validationSection.hidden = true;
    return;
  }

  try {
    const data = await getForecastComposite(runId);
    currentForecastData = data;
    forecastTracesVisible = false;
    forecastTracesToggle.checked = false;
    currentForecastTraces = null;
    currentObservations = [];
    validationMetricsEl.innerHTML = "";

    renderForecastGateBadge(forecastGateBadge, data);

    const hasHours = data.gate_result !== "low"
      && data.gate_result !== "insufficient_data"
      && data.hours && data.hours.length > 0;

    if (hasHours) {
      renderForecastChart(forecastChartEl, data);
      renderForecastTable(forecastTableEl, data);
      exportForecastPngBtn.hidden = false;
      forecastTracesToggle.parentElement!.hidden = false;
      // Only show validation for past dates where observations exist
      const targetInPast = new Date(currentTargetDate + "T23:59:59") < new Date();
      validationSection.hidden = !targetInPast;

      if (targetInPast && stationSelect.value) {
        loadObservationOverlay();
      }
    } else {
      disposeForecastChart();
      forecastChartEl.innerHTML = "";
      forecastTableEl.innerHTML = "";
      exportForecastPngBtn.hidden = true;
      forecastTracesToggle.parentElement!.hidden = true;
      validationSection.hidden = true;
    }

    forecastCompositeSection.hidden = false;
  } catch {
    forecastCompositeSection.hidden = true;
  }
}

// Forecast traces toggle
forecastTracesToggle.addEventListener("change", async () => {
  if (!currentForecastData || !currentRunId) return;

  forecastTracesVisible = forecastTracesToggle.checked;

  if (forecastTracesVisible && !currentForecastTraces) {
    try {
      currentForecastTraces = await getAnalogHourly(currentRunId);
    } catch {
      forecastTracesVisible = false;
      forecastTracesToggle.checked = false;
      return;
    }
  }

  const traces = forecastTracesVisible ? currentForecastTraces?.analogs : undefined;
  const obs = currentObservations.length > 0 ? currentObservations : undefined;
  renderForecastChart(forecastChartEl, currentForecastData, traces, forecastTracesVisible, obs);
});

// Forecast export button (PNG)
exportForecastPngBtn.addEventListener("click", () => {
  downloadForecastChart(currentTargetDate);
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

// --- Batch Validation ---

const valMethodSelect = document.getElementById("val-method") as HTMLSelectElement;
const valBufferInput = document.getElementById("val-buffer") as HTMLInputElement;
const valTopNInput = document.getElementById("val-topn") as HTMLInputElement;
const runValidationBtn = document.getElementById("run-validation-btn") as HTMLButtonElement;
const valProgress = document.getElementById("val-progress")!;
const valProgressLabel = document.getElementById("val-progress-label")!;
const valProgressCount = document.getElementById("val-progress-count")!;
const valProgressBar = document.getElementById("val-progress-bar")!;
const valError = document.getElementById("val-error")!;
const valResults = document.getElementById("val-results")!;
const valClassificationGrid = document.getElementById("val-classification-grid")!;
const valContinuousGrid = document.getElementById("val-continuous-grid")!;
const valGateTable = document.getElementById("val-gate-table")!;
const valSourceTable = document.getElementById("val-source-table")!;
const valTimeseriesChartEl = document.getElementById("val-timeseries-chart")!;
const valHistogramChartEl = document.getElementById("val-histogram-chart")!;
const valMonthlyChartEl = document.getElementById("val-monthly-chart")!;
const valHistoryList = document.getElementById("val-history-list")!;
const refreshValHistoryBtn = document.getElementById("refresh-val-history-btn") as HTMLButtonElement;

const valPerDayTable = document.getElementById("val-per-day-table")!;
const valDetailPanel = document.getElementById("val-detail-panel") as HTMLElement;
const valDetailTitle = document.getElementById("val-detail-title")!;
const valDetailClose = document.getElementById("val-detail-close") as HTMLButtonElement;
const valDetailMetrics = document.getElementById("val-detail-metrics")!;
const valDetailChartEl = document.getElementById("val-detail-chart")!;
const valDetailAnalogTable = document.getElementById("val-detail-analog-table")!;

let currentValRunId: number | null = null;
let currentValResult: ValidationRunResult | null = null;
let valPollTimer: ReturnType<typeof setInterval> | null = null;

async function loadValHistory() {
  const locId = Number(locationSelect.value);
  if (!locId) return;
  try {
    const runs = await listBatchValidationRuns(locId);
    if (runs.length === 0) {
      valHistoryList.innerHTML = `<p class="history-empty">No validation runs found.</p>`;
      return;
    }
    valHistoryList.innerHTML = runs
      .map((r) => {
        const statusCls = r.status === "completed" ? "completed" : r.status === "failed" ? "failed" : "running";
        const pct = r.total_days > 0 ? Math.round((r.completed_days / r.total_days) * 100) : 0;
        return `<div class="history-item" data-val-run-id="${r.id}" style="cursor:pointer;">
          <span class="status-badge ${statusCls}">${r.status}</span>
          <span>${r.evaluation_method}</span>
          <span>${r.completed_days}/${r.total_days} days (${pct}%)</span>
          <span style="color:#868e96;font-size:0.82rem;">${r.created_at ? new Date(r.created_at).toLocaleString() : ""}</span>
        </div>`;
      })
      .join("");

    valHistoryList.querySelectorAll("[data-val-run-id]").forEach((el) => {
      el.addEventListener("click", async () => {
        const runId = Number((el as HTMLElement).dataset.valRunId);
        await loadValResults(runId);
      });
    });
  } catch {
    valHistoryList.innerHTML = `<p class="history-empty">Failed to load validation runs.</p>`;
  }
}

function renderValPerDayTable(
  table: HTMLElement,
  perDayResults: Record<string, unknown>[],
) {
  const rows = perDayResults
    .filter((r) => r.tws_mae != null)
    .sort((a, b) => String(a.date).localeCompare(String(b.date)));

  if (rows.length === 0) {
    table.innerHTML = `<thead><tr><th colspan="7">No per-day results</th></tr></thead>`;
    return;
  }

  const header = `<thead><tr>
    <th>Date</th>
    <th>Gate</th>
    <th>Actual</th>
    <th class="num">TWS MAE</th>
    <th class="num">TWD MAE</th>
    <th class="num">Peak Error</th>
    <th>Action</th>
  </tr></thead>`;

  const body = rows
    .map((r) => {
      const date = String(r.date);
      const gate = r.gate_result ?? "—";
      const actual = r.actual_classification ?? "—";
      const twsMae = r.tws_mae != null ? Number(r.tws_mae).toFixed(2) : "—";
      const twdMae = r.twd_circular_mae != null ? Number(r.twd_circular_mae).toFixed(1) : "—";
      const peakErr = r.peak_speed_error != null ? Number(r.peak_speed_error).toFixed(2) : "—";
      return `<tr>
        <td>${date}</td>
        <td>${gate}</td>
        <td>${actual}</td>
        <td class="num">${twsMae}</td>
        <td class="num">${twdMae}</td>
        <td class="num">${peakErr}</td>
        <td><button class="btn-export" data-val-drill-date="${date}">View</button></td>
      </tr>`;
    })
    .join("");

  table.innerHTML = `${header}<tbody>${body}</tbody>`;

  table.addEventListener("click", (e) => {
    const btn = (e.target as HTMLElement).closest<HTMLElement>("[data-val-drill-date]");
    if (btn) {
      const date = btn.dataset.valDrillDate;
      if (date) drillDownToValDay(date);
    }
  });
}

async function drillDownToValDay(date: string) {
  if (!currentValResult) return;

  valDetailPanel.hidden = false;
  valDetailTitle.textContent = `Validation Detail: ${date}`;

  // Show per-day metrics from cached result
  const dayEntry = currentValResult.per_day_results?.find(
    (r) => String(r.date) === date,
  );

  if (dayEntry) {
    const gate = String(dayEntry.gate_result ?? "—");
    const actual = String(dayEntry.actual_classification ?? "—");
    const twsMae = dayEntry.tws_mae != null ? Number(dayEntry.tws_mae).toFixed(2) + " m/s" : "—";
    const twdMae = dayEntry.twd_circular_mae != null ? Number(dayEntry.twd_circular_mae).toFixed(1) + "\u00b0" : "—";
    const peakErr = dayEntry.peak_speed_error != null ? Number(dayEntry.peak_speed_error).toFixed(2) + " m/s" : "—";
    const onsetErr = dayEntry.onset_error_hours != null ? Number(dayEntry.onset_error_hours).toFixed(1) + " h" : "—";
    valDetailMetrics.innerHTML = `
      <div class="metric-box"><div class="metric-label">Gate Result</div><div class="metric-value">${gate}</div></div>
      <div class="metric-box"><div class="metric-label">Actual</div><div class="metric-value">${actual}</div></div>
      <div class="metric-box"><div class="metric-label">TWS MAE</div><div class="metric-value">${twsMae}</div></div>
      <div class="metric-box"><div class="metric-label">TWD MAE</div><div class="metric-value">${twdMae}</div></div>
      <div class="metric-box"><div class="metric-label">Peak Error</div><div class="metric-value">${peakErr}</div></div>
      <div class="metric-box"><div class="metric-label">Onset Error</div><div class="metric-value">${onsetErr}</div></div>
    `;
  } else {
    valDetailMetrics.innerHTML = "";
  }

  // Show loading state
  valDetailChartEl.innerHTML = `<p style="text-align:center;color:#868e96;padding:2rem;">Loading analysis...</p>`;
  valDetailAnalogTable.innerHTML = "";

  valDetailPanel.scrollIntoView({ behavior: "smooth", block: "start" });

  try {
    const histSource = currentValResult.historical_source ?? "era5";
    const request = {
      location_id: currentValResult.location_id,
      target_date: date,
      historical_start_date: currentValResult.library_start_date ?? "",
      historical_end_date: currentValResult.library_end_date ?? "",
      top_n: currentValResult.top_n,
      mode: "forecast",
      forecast_source: histSource,
      historical_source: histSource,
    };

    const analysisRun = await runAnalysis(request);
    const runId = analysisRun.id;

    // Fetch forecast composite and actual weather in parallel
    const [composite, actualRecords] = await Promise.all([
      getForecastComposite(runId),
      getWeatherRecords(currentValResult.location_id, date, date, histSource),
    ]);

    // Render the forecast chart with actual overlay
    valDetailChartEl.innerHTML = "";
    renderValDetailForecastChart(valDetailChartEl, composite, actualRecords);

    // Render analog table
    if (analysisRun.analogs && analysisRun.analogs.length > 0) {
      renderAnalogTable(valDetailAnalogTable, analysisRun.analogs);
    } else {
      valDetailAnalogTable.innerHTML = `<thead><tr><th>No analog days found</th></tr></thead>`;
    }
  } catch (err) {
    valDetailChartEl.innerHTML = `<p style="text-align:center;color:#e03131;padding:2rem;">Failed to load analysis: ${err instanceof Error ? err.message : "Unknown error"}</p>`;
  }
}

valDetailClose.onclick = () => {
  valDetailPanel.hidden = true;
  disposeValDetailChart();
};

function renderValResults(result: ValidationRunResult) {
  currentValResult = result;

  // Reset drill-down panel from previous run
  valDetailPanel.hidden = true;
  disposeValDetailChart();

  if (result.aggregate_metrics) {
    renderBatchClassificationMetrics(valClassificationGrid, result.aggregate_metrics);
    renderBatchContinuousMetrics(valContinuousGrid, result.aggregate_metrics);
  }
  if (result.gate_sensitivity) {
    renderGateSensitivityTable(valGateTable, result.gate_sensitivity);
  }
  if (result.source_stratification) {
    renderSourceStratificationTable(valSourceTable, result.source_stratification);
  }
  // Unhide before chart init so ECharts can measure container dimensions
  valResults.hidden = false;
  if (result.per_day_results && result.per_day_results.length > 0) {
    renderValidationTimeSeriesChart(valTimeseriesChartEl, result.per_day_results, drillDownToValDay);
    renderValidationHistogramChart(valHistogramChartEl, result.per_day_results);
    renderValidationMonthlyChart(valMonthlyChartEl, result.per_day_results);
    renderValPerDayTable(valPerDayTable, result.per_day_results);
  } else {
    disposeValidationCharts();
    valPerDayTable.innerHTML = "";
  }
}

async function loadValResults(runId: number) {
  currentValRunId = runId;
  try {
    const result = await getValidationRunResult(runId);
    if (result.status === "completed") {
      renderValResults(result);
      valProgress.hidden = true;
      valError.hidden = true;
    } else if (result.status === "failed") {
      valError.textContent = result.error_message || "Validation run failed.";
      valError.hidden = false;
      valProgress.hidden = true;
      valResults.hidden = true;
    } else {
      // Still running, start polling
      startValPolling(runId);
    }
  } catch {
    valError.textContent = "Failed to load validation results.";
    valError.hidden = false;
    valResults.hidden = true;
  }
}

function startValPolling(runId: number) {
  valProgress.hidden = false;
  valResults.hidden = true;
  valError.hidden = true;
  runValidationBtn.disabled = true;

  if (valPollTimer) clearInterval(valPollTimer);
  valPollTimer = setInterval(async () => {
    try {
      const status = await getValidationRunStatus(runId);
      const pct = status.total_days > 0 ? Math.round((status.completed_days / status.total_days) * 100) : 0;
      valProgressLabel.textContent = status.status === "running" ? "Running..." : status.status;
      valProgressCount.textContent = `${status.completed_days}/${status.total_days} days`;
      valProgressBar.style.width = `${pct}%`;

      if (status.status === "completed" || status.status === "failed") {
        if (valPollTimer) clearInterval(valPollTimer);
        valPollTimer = null;
        runValidationBtn.disabled = false;
        if (status.status === "completed") {
          await loadValResults(runId);
        } else {
          valError.textContent = status.error_message || "Validation run failed.";
          valError.hidden = false;
          valProgress.hidden = true;
        }
        loadValHistory();
      }
    } catch {
      if (valPollTimer) clearInterval(valPollTimer);
      valPollTimer = null;
      runValidationBtn.disabled = false;
    }
  }, 3000);
}

runValidationBtn.addEventListener("click", async () => {
  const locId = Number(locationSelect.value);
  if (!locId) return;

  const method = valMethodSelect.value;
  const buffer = Number(valBufferInput.value);
  const topN = Number(valTopNInput.value);

  runValidationBtn.disabled = true;
  valError.hidden = true;
  valResults.hidden = true;

  try {
    const resp = await triggerBatchValidation(locId, method, buffer, topN);
    currentValRunId = resp.run_id;
    startValPolling(resp.run_id);
  } catch (err) {
    valError.textContent = `Failed to start validation: ${err instanceof Error ? err.message : String(err)}`;
    valError.hidden = false;
    runValidationBtn.disabled = false;
  }
});

refreshValHistoryBtn.addEventListener("click", () => loadValHistory());

// --- Boot ---

initHealth();
initLocations().then(() => loadLibraryStatus());
initStations();
setDefaultDates();
loadHistory();
loadValHistory();
