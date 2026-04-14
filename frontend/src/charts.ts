import { use, init, type ECharts } from "echarts/core";
import { LineChart, ScatterChart, BarChart, CustomChart } from "echarts/charts";
import {
  GridComponent,
  TitleComponent,
  TooltipComponent,
  DataZoomComponent,
  LegendComponent,
  PolarComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { WeatherRecord, BiasCorrection } from "./types";

use([
  LineChart,
  ScatterChart,
  BarChart,
  CustomChart,
  GridComponent,
  TitleComponent,
  TooltipComponent,
  DataZoomComponent,
  LegendComponent,
  PolarComponent,
  CanvasRenderer,
]);

let windOverlayChart: ECharts | null = null;
let tempPressureChart: ECharts | null = null;
let morningWindRoseChart: ECharts | null = null;
let afternoonWindRoseChart: ECharts | null = null;
let biasChart: ECharts | null = null;

export function renderWindOverlayChart(
  container: HTMLElement,
  records: WeatherRecord[],
  source?: string,
): void {
  if (windOverlayChart) {
    windOverlayChart.dispose();
  }
  windOverlayChart = init(container);

  const times = records.map((r) => {
    const d = new Date(r.valid_time_local);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  });
  const speeds = records.map((r) => r.true_wind_speed);
  const directions = records.map((r) => r.true_wind_direction);

  windOverlayChart.setOption({
    title: source
      ? {
          text: `Source: ${source}`,
          textStyle: { fontSize: 11, fontWeight: "normal", color: "#868e96" },
          left: "center",
          top: 0,
        }
      : undefined,
    tooltip: {
      trigger: "axis",
      formatter(params: unknown) {
        const items = params as Array<{
          axisValueLabel: string;
          seriesName: string;
          value: number | null;
          color: string;
        }>;
        if (!items.length) return "";
        let html = items[0].axisValueLabel;
        for (const item of items) {
          const val =
            item.value != null
              ? item.seriesName === "TWS"
                ? `${item.value.toFixed(1)} m/s`
                : `${item.value}°`
              : "N/A";
          html += `<br/><span style="color:${item.color}">●</span> ${item.seriesName}: ${val}`;
        }
        return html;
      },
    },
    legend: { top: source ? 18 : 0, left: "center" },
    grid: { left: 50, right: 65, top: source ? 50 : 30, bottom: 50 },
    xAxis: {
      type: "category",
      data: times,
      axisLabel: { rotate: 45, fontSize: 11 },
    },
    yAxis: [
      {
        type: "value",
        name: "m/s",
        nameLocation: "middle",
        nameGap: 35,
      },
      {
        type: "value",
        name: "Direction",
        min: 0,
        max: 360,
        interval: 90,
        axisLabel: {
          formatter(value: number) {
            const labels: Record<number, string> = {
              0: "N",
              90: "E",
              180: "S",
              270: "W",
              360: "N",
            };
            return labels[value] ?? `${value}°`;
          },
        },
      },
    ],
    dataZoom: [{ type: "inside" }],
    series: [
      {
        name: "TWS",
        type: "line",
        yAxisIndex: 0,
        data: speeds,
        smooth: true,
        symbol: "circle",
        symbolSize: 4,
        lineStyle: { color: "#228be6", width: 2 },
        itemStyle: { color: "#228be6" },
      },
      {
        name: "TWD",
        type: "scatter",
        yAxisIndex: 1,
        data: directions,
        symbolSize: 6,
        itemStyle: { color: "#e67700" },
      },
    ],
  });
}

export function renderTempPressureChart(
  container: HTMLElement,
  records: WeatherRecord[],
  source?: string,
): void {
  if (tempPressureChart) {
    tempPressureChart.dispose();
  }
  tempPressureChart = init(container);

  const times = records.map((r) => {
    const d = new Date(r.valid_time_local);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  });
  const temps = records.map((r) => r.temperature);
  const pressures = records.map((r) => r.pressure);

  // Compute tight range for pressure axis so small variations are visible
  const validPressures = pressures.filter((p): p is number => p != null);
  let pMin: number | undefined;
  let pMax: number | undefined;
  if (validPressures.length > 0) {
    const dataMin = Math.min(...validPressures);
    const dataMax = Math.max(...validPressures);
    const pad = Math.max((dataMax - dataMin) * 0.5, 2);
    pMin = Math.floor(dataMin - pad);
    pMax = Math.ceil(dataMax + pad);
  }

  tempPressureChart.setOption({
    title: source
      ? {
          text: `Source: ${source}`,
          textStyle: { fontSize: 11, fontWeight: "normal", color: "#868e96" },
          left: "center",
          top: 0,
        }
      : undefined,
    tooltip: {
      trigger: "axis",
      formatter(params: unknown) {
        const items = params as Array<{
          axisValueLabel: string;
          seriesName: string;
          value: number | null;
          color: string;
        }>;
        if (!items.length) return "";
        let html = items[0].axisValueLabel;
        for (const item of items) {
          const val =
            item.value != null
              ? item.seriesName === "Temperature"
                ? `${item.value.toFixed(1)} °C`
                : `${item.value.toFixed(1)} hPa`
              : "N/A";
          html += `<br/><span style="color:${item.color}">●</span> ${item.seriesName}: ${val}`;
        }
        return html;
      },
    },
    legend: { top: source ? 18 : 0, left: "center" },
    grid: { left: 50, right: 65, top: source ? 50 : 30, bottom: 50 },
    xAxis: {
      type: "category",
      data: times,
      axisLabel: { rotate: 45, fontSize: 11 },
    },
    yAxis: [
      {
        type: "value",
        name: "°C",
        nameLocation: "middle",
        nameGap: 35,
      },
      {
        type: "value",
        name: "hPa",
        nameLocation: "middle",
        nameGap: 45,
        min: pMin,
        max: pMax,
      },
    ],
    dataZoom: [{ type: "inside" }],
    series: [
      {
        name: "Temperature",
        type: "line",
        yAxisIndex: 0,
        data: temps,
        smooth: true,
        symbol: "circle",
        symbolSize: 4,
        lineStyle: { color: "#e03131", width: 2 },
        itemStyle: { color: "#e03131" },
      },
      {
        name: "Pressure",
        type: "line",
        yAxisIndex: 1,
        data: pressures,
        smooth: true,
        symbol: "circle",
        symbolSize: 4,
        lineStyle: { color: "#7048e8", width: 2 },
        itemStyle: { color: "#7048e8" },
      },
    ],
  });
}

export function getWindOverlayChart(): ECharts | null {
  return windOverlayChart;
}

export function getTempPressureChart(): ECharts | null {
  return tempPressureChart;
}

// --- Wind Rose ---

const SECTOR_LABELS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"] as const;

interface SectorData {
  labels: readonly string[];
  values: number[];
}

function binWindBySector(
  records: WeatherRecord[],
  startHour: number,
  endHour: number,
): SectorData {
  const sums = new Float64Array(8);
  const counts = new Uint32Array(8);

  for (const r of records) {
    const hour = new Date(r.valid_time_local).getHours();
    if (hour < startHour || hour >= endHour) continue;
    if (r.true_wind_speed == null || r.true_wind_direction == null) continue;

    const idx = Math.floor(((r.true_wind_direction + 22.5) % 360) / 45);
    sums[idx] += r.true_wind_speed;
    counts[idx] += 1;
  }

  const values = Array.from(sums, (s, i) => (counts[i] > 0 ? s / counts[i] : 0));
  return { labels: SECTOR_LABELS, values };
}

function setWindRoseOption(
  chart: ECharts,
  data: SectorData,
  title: string,
  source?: string,
  maxOverride?: number,
): void {
  const maxVal = maxOverride ?? Math.max(...data.values, 1);

  chart.setOption({
    title: {
      text: title,
      subtext: source ? `Source: ${source}` : "",
      subtextStyle: { fontSize: 11, color: "#868e96" },
      left: "center",
      top: 0,
    },
    tooltip: {
      trigger: "item",
      formatter(params: unknown) {
        const p = params as { name: string; value: number };
        return `${p.name}: ${p.value.toFixed(1)} m/s`;
      },
    },
    polar: { radius: "65%" },
    angleAxis: {
      type: "category",
      data: [...data.labels],
      startAngle: 90,
      clockwise: true,
      axisTick: { show: false },
      axisLabel: { fontSize: 12, fontWeight: "bold" },
    },
    radiusAxis: {
      min: 0,
      max: Math.ceil(maxVal * 10) / 10,
      splitNumber: 4,
      axisLabel: { fontSize: 10, formatter: "{value}" },
      splitLine: { lineStyle: { type: "dashed", color: "#dee2e6" } },
    },
    series: [
      {
        type: "bar",
        coordinateSystem: "polar",
        data: data.values,
        itemStyle: { color: "#228be6" },
        barWidth: "60%",
      },
    ],
  });
}

export function renderDualWindRose(
  morningContainer: HTMLElement,
  afternoonContainer: HTMLElement,
  records: WeatherRecord[],
  source?: string,
): void {
  if (morningWindRoseChart) morningWindRoseChart.dispose();
  if (afternoonWindRoseChart) afternoonWindRoseChart.dispose();

  morningWindRoseChart = init(morningContainer);
  afternoonWindRoseChart = init(afternoonContainer);

  const morningData = binWindBySector(records, 8, 10);
  const afternoonData = binWindBySector(records, 11, 16);

  const sharedMax = Math.max(...morningData.values, ...afternoonData.values, 1);

  setWindRoseOption(morningWindRoseChart, morningData, "Morning (08–10)", source, sharedMax);
  setWindRoseOption(afternoonWindRoseChart, afternoonData, "Afternoon (11–16)", source, sharedMax);
}

export function getMorningWindRoseChart(): ECharts | null {
  return morningWindRoseChart;
}

export function getAfternoonWindRoseChart(): ECharts | null {
  return afternoonWindRoseChart;
}

// --- Bias Chart ---

const FEATURE_LABELS: Record<string, string> = {
  morning_wind_speed: "Morn. Speed",
  afternoon_wind_speed: "Aft. Speed",
  morning_wind_direction: "Morn. Dir",
  afternoon_wind_direction: "Aft. Dir",
  direction_shift: "Dir. Shift",
  speed_increase: "Spd. Increase",
  temperature_morning: "Morn. Temp",
  temperature_afternoon: "Aft. Temp",
  pressure_morning: "Morn. Press",
};

const PAIR_COLORS = ["#228be6", "#e67700", "#2b8a3e", "#7048e8", "#e03131"];

export function renderBiasChart(
  container: HTMLElement,
  corrections: BiasCorrection[],
): void {
  if (biasChart) biasChart.dispose();
  biasChart = init(container);

  // Group by source pair
  const pairMap = new Map<string, BiasCorrection[]>();
  for (const c of corrections) {
    const key = `${c.forecast_source} vs ${c.historical_source}`;
    const arr = pairMap.get(key);
    if (arr) arr.push(c);
    else pairMap.set(key, [c]);
  }

  // Collect all feature names preserving order
  const featureSet = new Set<string>();
  for (const c of corrections) featureSet.add(c.feature_name);
  const features = [...featureSet];
  const featureLabels = features.map((f) => FEATURE_LABELS[f] ?? f);

  const pairs = [...pairMap.keys()];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const series: any[] = [];

  pairs.forEach((pair, pi) => {
    const corrs = pairMap.get(pair)!;
    const color = PAIR_COLORS[pi % PAIR_COLORS.length];

    // Build lookup by feature
    const byFeature = new Map<string, BiasCorrection>();
    for (const c of corrs) byFeature.set(c.feature_name, c);

    // Bar series for mean bias
    const barData = features.map((f) => {
      const c = byFeature.get(f);
      return c ? c.bias_mean : null;
    });

    series.push({
      name: pair,
      type: "bar",
      data: barData,
      itemStyle: { color },
      barGap: "10%",
    });

    // Custom series for error bars (mean ± std)
    const errorData = features.map((f, idx) => {
      const c = byFeature.get(f);
      if (!c) return null;
      return [idx, c.bias_mean - c.bias_std, c.bias_mean + c.bias_std];
    });

    series.push({
      name: `${pair} (±std)`,
      type: "custom",
      data: errorData,
      itemStyle: { color },
      renderItem(
        params: { coordSys: { x: number; y: number; width: number; height: number } },
        api: {
          value: (dim: number) => number;
          coord: (val: [number, number]) => [number, number];
          style: () => Record<string, unknown>;
        },
      ) {
        const xVal = api.value(0);
        const low = api.value(1);
        const high = api.value(2);
        const highCoord = api.coord([xVal, high]);
        const lowCoord = api.coord([xVal, low]);
        const capW = 6;
        return {
          type: "group",
          children: [
            {
              type: "line",
              shape: { x1: highCoord[0], y1: highCoord[1], x2: lowCoord[0], y2: lowCoord[1] },
              style: { stroke: color, lineWidth: 1.5 },
            },
            {
              type: "line",
              shape: { x1: highCoord[0] - capW, y1: highCoord[1], x2: highCoord[0] + capW, y2: highCoord[1] },
              style: { stroke: color, lineWidth: 1.5 },
            },
            {
              type: "line",
              shape: { x1: lowCoord[0] - capW, y1: lowCoord[1], x2: lowCoord[0] + capW, y2: lowCoord[1] },
              style: { stroke: color, lineWidth: 1.5 },
            },
          ],
        };
      },
      z: 10,
    });
  });

  biasChart.setOption({
    tooltip: {
      trigger: "axis",
      formatter(params: unknown) {
        const items = params as Array<{
          axisValueLabel: string;
          seriesName: string;
          value: number | number[] | null;
          color: string;
          seriesType: string;
        }>;
        if (!items.length) return "";
        let html = items[0].axisValueLabel;
        for (const item of items) {
          if (item.seriesType === "custom") continue;
          const val = item.value != null ? (item.value as number).toFixed(3) : "N/A";
          html += `<br/><span style="color:${item.color}">●</span> ${item.seriesName}: ${val}`;
        }
        return html;
      },
    },
    legend: {
      top: 0,
      left: "center",
      data: pairs,
    },
    grid: { left: 50, right: 20, top: 40, bottom: 70 },
    xAxis: {
      type: "category",
      data: featureLabels,
      axisLabel: { rotate: 35, fontSize: 11 },
    },
    yAxis: {
      type: "value",
      name: "Bias",
      nameLocation: "middle",
      nameGap: 35,
    },
    series,
  });
}

export function getBiasChart(): ECharts | null {
  return biasChart;
}

function handleResize() {
  windOverlayChart?.resize();
  tempPressureChart?.resize();
  morningWindRoseChart?.resize();
  afternoonWindRoseChart?.resize();
  biasChart?.resize();
}

window.addEventListener("resize", handleResize);
