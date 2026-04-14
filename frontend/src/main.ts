import { fetchHealth, fetchLocations } from "./api";
import "./styles.css";

const statusEl = document.getElementById("health-status")!;
const locationsEl = document.getElementById("locations")!;

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

renderHealth();
renderLocations();
