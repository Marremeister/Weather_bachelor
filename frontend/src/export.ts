import { getSpeedChart, getDirectionChart } from "./charts";

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

export function downloadWindSpeedChart(targetDate: string): void {
  const chart = getSpeedChart();
  if (!chart) return;
  const url = chart.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#fff" });
  triggerDownload(url, `wind_speed_${targetDate}.png`);
}

export function downloadWindDirectionChart(targetDate: string): void {
  const chart = getDirectionChart();
  if (!chart) return;
  const url = chart.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#fff" });
  triggerDownload(url, `wind_direction_${targetDate}.png`);
}
