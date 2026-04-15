import {
  getWindOverlayChart,
  getTempPressureChart,
  getMorningWindRoseChart,
  getAfternoonWindRoseChart,
  getBiasChart,
  getAnalogOverlayChart,
  getSpeedIncreaseChart,
} from "./charts";

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

export function downloadMorningWindRoseChart(targetDate: string): void {
  const chart = getMorningWindRoseChart();
  if (!chart) return;
  const url = chart.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#fff" });
  triggerDownload(url, `morning_windrose_${targetDate}.png`);
}

export function downloadAfternoonWindRoseChart(targetDate: string): void {
  const chart = getAfternoonWindRoseChart();
  if (!chart) return;
  const url = chart.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#fff" });
  triggerDownload(url, `afternoon_windrose_${targetDate}.png`);
}

export function downloadBiasChart(targetDate: string): void {
  const chart = getBiasChart();
  if (!chart) return;
  const url = chart.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#fff" });
  triggerDownload(url, `bias_chart_${targetDate}.png`);
}

export function downloadAnalogOverlayChart(targetDate: string): void {
  const chart = getAnalogOverlayChart();
  if (!chart) return;
  const url = chart.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#fff" });
  triggerDownload(url, `analog_overlay_${targetDate}.png`);
}

export function downloadSpeedIncreaseChart(targetDate: string): void {
  const chart = getSpeedIncreaseChart();
  if (!chart) return;
  const url = chart.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#fff" });
  triggerDownload(url, `speed_increase_${targetDate}.png`);
}
