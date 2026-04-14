import { fetchHealth } from "./api";
import "./styles.css";

const statusEl = document.getElementById("health-status")!;

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

renderHealth();
