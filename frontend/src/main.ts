import {
  fetchClassification,
  fetchHealth,
  fetchLocations,
  getWeatherRecords,
  runAnalysis,
} from "./api";
import { renderWindSpeedChart, renderWindDirectionChart } from "./charts";
import {
  renderSummaryPanel,
  renderHourlyTable,
  renderAnalogTable,
} from "./dashboard";
import type { Location, SeaBreezeClassification } from "./types";
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
const speedChartEl = document.getElementById("wind-speed-chart")!;
const dirChartEl = document.getElementById("wind-direction-chart")!;
const hourlySection = document.getElementById("hourly-section")!;
const hourlyTable = document.getElementById("hourly-table")!;
const analogSection = document.getElementById("analog-section")!;
const analogTable = document.getElementById("analog-table")!;

// Legacy
const healthStatusEl = document.getElementById("health-status")!;
const locationsEl = document.getElementById("locations")!;
const classifyBtn = document.getElementById("classify-btn")!;
const classifyDateInput = document.getElementById("classify-date") as HTMLInputElement;
const classificationResultEl = document.getElementById("classification-result")!;

// --- Store ---
let locations: Location[] = [];

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
    const [analysisRun, weatherRecords] = await Promise.all([
      runAnalysis({
        location_id: locationId,
        target_date: targetDateInput.value,
        historical_start_date: histStartInput.value,
        historical_end_date: histEndInput.value,
        top_n: Number(topNInput.value),
      }),
      getWeatherRecords(locationId, targetDateInput.value, targetDateInput.value),
    ]);

    // Summary
    renderSummaryPanel(summaryPanel, analysisRun);
    summarySection.hidden = false;

    // Charts
    if (weatherRecords.length > 0) {
      chartsSection.hidden = false;
      renderWindSpeedChart(speedChartEl, weatherRecords);
      renderWindDirectionChart(dirChartEl, weatherRecords);
    }

    // Hourly table
    renderHourlyTable(hourlyTable, weatherRecords);
    hourlySection.hidden = false;

    // Analog table
    renderAnalogTable(analogTable, analysisRun.analogs);
    analogSection.hidden = false;
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
