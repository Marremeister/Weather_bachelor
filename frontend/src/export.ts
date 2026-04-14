import { getWindOverlayChart, getTempPressureChart } from "./charts";

function triggerDownload(url: string, filename: string): void {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

export function downloadWeatherCsv(runId: number, targetDate: string): void {
  triggerDownload(
    `/api/analysis/${runId}/export/weather-csv`,
    `weather_${targetDate}.csv`,
  );
}

export function downloadAnalogsCsv(runId: number, targetDate: string): void {
  triggerDownload(
    `/api/analysis/${runId}/export/analogs-csv`,
    `analogs_${targetDate}.csv`,
  );
}

export function downloadAnalysisJson(runId: number, targetDate: string): void {
  triggerDownload(
    `/api/analysis/${runId}/export/json`,
    `analysis_${targetDate}.json`,
  );
}

export function downloadWindOverlayChart(targetDate: string): void {
  const chart = getWindOverlayChart();
  if (!chart) return;
  const url = chart.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#fff" });
  triggerDownload(url, `wind_overlay_${targetDate}.png`);
}

export function downloadTempPressureChart(targetDate: string): void {
  const chart = getTempPressureChart();
  if (!chart) return;
  const url = chart.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#fff" });
  triggerDownload(url, `temp_pressure_${targetDate}.png`);
}
