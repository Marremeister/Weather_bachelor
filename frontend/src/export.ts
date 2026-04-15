import {
  getWindOverlayChart,
  getTempPressureChart,
  getMorningWindRoseChart,
  getAfternoonWindRoseChart,
  getBiasChart,
  getAnalogOverlayChart,
  getSpeedIncreaseChart,
  getFeatureRadarChart,
  getDirectionShiftChart,
  getSeasonalHeatmapChart,
  getDistanceHistogramChart,
  getForecastChart,
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

export function downloadFeatureRadarChart(targetDate: string): void {
  const chart = getFeatureRadarChart();
  if (!chart) return;
  const url = chart.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#fff" });
  triggerDownload(url, `feature_radar_${targetDate}.png`);
}

export function downloadDirectionShiftChart(targetDate: string): void {
  const chart = getDirectionShiftChart();
  if (!chart) return;
  const url = chart.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#fff" });
  triggerDownload(url, `direction_shift_${targetDate}.png`);
}

export function downloadSeasonalHeatmapChart(targetDate: string): void {
  const chart = getSeasonalHeatmapChart();
  if (!chart) return;
  const url = chart.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#fff" });
  triggerDownload(url, `seasonal_heatmap_${targetDate}.png`);
}

export function downloadDistanceHistogramChart(targetDate: string): void {
  const chart = getDistanceHistogramChart();
  if (!chart) return;
  const url = chart.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#fff" });
  triggerDownload(url, `distance_histogram_${targetDate}.png`);
}

export function downloadForecastChart(targetDate: string): void {
  const chart = getForecastChart();
  if (!chart) return;
  const url = chart.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#fff" });
  triggerDownload(url, `forecast_composite_${targetDate}.png`);
}

export function downloadForecastCsv(runId: number, targetDate: string): void {
  triggerDownload(
    `/api/analysis/${runId}/export/forecast-csv`,
    `forecast_${targetDate}.csv`,
  );
}
