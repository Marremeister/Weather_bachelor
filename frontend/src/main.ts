import { fetchClassification, fetchHealth, fetchLocations } from "./api";
import type { SeaBreezeClassification } from "./types";
import "./styles.css";

const statusEl = document.getElementById("health-status")!;
const locationsEl = document.getElementById("locations")!;
const classifyBtn = document.getElementById("classify-btn")!;
const classifyDateInput = document.getElementById("classify-date") as HTMLInputElement;
const classificationResultEl = document.getElementById("classification-result")!;

async function renderHealth() {
  try {
    const data = await fetchHealth();

    const cssClass =
      data.status === "healthy" ? "status-healthy" : "status-degraded";

    statusEl.innerHTML = `
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
    statusEl.innerHTML = `
      <p class="status-error">Could not reach backend.</p>
    `;
  }
}

async function renderLocations() {
  try {
    const locations = await fetchLocations();

    if (locations.length === 0) {
      locationsEl.innerHTML = `<p>No locations found.</p>`;
      return;
    }

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
  } catch {
    locationsEl.innerHTML = `
      <p class="status-error">Could not load locations.</p>
    `;
  }
}

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

renderHealth();
renderLocations();
