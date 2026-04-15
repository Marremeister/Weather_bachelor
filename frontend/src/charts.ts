import { use, init, type ECharts } from "echarts/core";
import { LineChart, ScatterChart, BarChart, CustomChart, PieChart } from "echarts/charts";
import {
  GridComponent,
  TitleComponent,
  TooltipComponent,
  DataZoomComponent,
  LegendComponent,
  PolarComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { WeatherRecord, BiasCorrection, DayHourlyRecords, SeaBreezePanelData } from "./types";

use([
  LineChart,
  ScatterChart,
  BarChart,
  CustomChart,
  PieChart,
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
let analogDonutChart: ECharts | null = null;
let analogOverlayChart: ECharts | null = null;
let speedIncreaseChart: ECharts | null = null;

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
    if (hour < startHour || hour > endHour) continue;
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

// --- Analog Donut Chart ---

export function renderAnalogDonutChart(
  container: HTMLElement,
  high: number,
  medium: number,
  low: number,
): void {
  if (analogDonutChart) analogDonutChart.dispose();
  analogDonutChart = init(container);

  analogDonutChart.setOption({
    tooltip: {
      trigger: "item",
      formatter(params: unknown) {
        const p = params as { name: string; value: number; percent: number };
        return `${p.name}: ${p.value} (${p.percent.toFixed(0)}%)`;
      },
    },
    legend: {
      bottom: 0,
      left: "center",
      itemWidth: 12,
      itemHeight: 12,
      textStyle: { fontSize: 12 },
    },
    series: [
      {
        type: "pie",
        radius: ["45%", "70%"],
        center: ["50%", "45%"],
        avoidLabelOverlap: true,
        label: { show: false },
        data: [
          { value: high, name: "High", itemStyle: { color: "#2b8a3e" } },
          { value: medium, name: "Medium", itemStyle: { color: "#e67700" } },
          { value: low, name: "Low", itemStyle: { color: "#c92a2a" } },
        ].filter((d) => d.value > 0),
      },
    ],
  });
}

// --- Analog Overlay Chart ---

const ANALOG_COLORS = ["#e67700", "#2b8a3e", "#7048e8"];

export function renderAnalogOverlayChart(
  container: HTMLElement,
  target: DayHourlyRecords,
  analogs: DayHourlyRecords[],
  metric: "tws" | "twd",
): void {
  if (analogOverlayChart) analogOverlayChart.dispose();
  analogOverlayChart = init(container);

  // Build a shared time axis from the target's records (by hour)
  const timeLabels: string[] = [];
  const hourToIdx = new Map<number, number>();
  for (const r of target.records) {
    const d = new Date(r.valid_time_local);
    const h = d.getHours();
    if (!hourToIdx.has(h)) {
      hourToIdx.set(h, timeLabels.length);
      timeLabels.push(d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
    }
  }

  function extractByHour(records: WeatherRecord[]): (number | null)[] {
    const arr: (number | null)[] = new Array(timeLabels.length).fill(null);
    for (const r of records) {
      const h = new Date(r.valid_time_local).getHours();
      const idx = hourToIdx.get(h);
      if (idx !== undefined) {
        arr[idx] = metric === "tws" ? r.true_wind_speed : r.true_wind_direction;
      }
    }
    return arr;
  }

  const isTWS = metric === "tws";

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const series: any[] = [
    {
      name: `Target (${target.date})`,
      type: "line",
      data: extractByHour(target.records),
      smooth: true,
      symbol: "circle",
      symbolSize: 5,
      lineStyle: { color: "#228be6", width: 3 },
      itemStyle: { color: "#228be6" },
    },
  ];

  analogs.forEach((analog, i) => {
    const color = ANALOG_COLORS[i % ANALOG_COLORS.length];
    series.push({
      name: `#${analog.rank} (${analog.date})`,
      type: "line",
      data: extractByHour(analog.records),
      smooth: true,
      symbol: "circle",
      symbolSize: 3,
      lineStyle: { color, width: 1.5, type: "dashed" },
      itemStyle: { color },
    });
  });

  const yAxisConfig = isTWS
    ? { type: "value" as const, name: "m/s", nameLocation: "middle" as const, nameGap: 35 }
    : {
        type: "value" as const,
        name: "Direction",
        min: 0,
        max: 360,
        interval: 90,
        axisLabel: {
          formatter(value: number) {
            const labels: Record<number, string> = { 0: "N", 90: "E", 180: "S", 270: "W", 360: "N" };
            return labels[value] ?? `${value}°`;
          },
        },
      };

  analogOverlayChart.setOption({
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
              ? isTWS
                ? `${item.value.toFixed(1)} m/s`
                : `${item.value}°`
              : "N/A";
          html += `<br/><span style="color:${item.color}">●</span> ${item.seriesName}: ${val}`;
        }
        return html;
      },
    },
    legend: { top: 0, left: "center" },
    grid: { left: 50, right: 20, top: 35, bottom: 50 },
    xAxis: {
      type: "category",
      data: timeLabels,
      axisLabel: { rotate: 45, fontSize: 11 },
    },
    yAxis: yAxisConfig,
    dataZoom: [{ type: "inside" }],
    series,
  });
}

export function getAnalogOverlayChart(): ECharts | null {
  return analogOverlayChart;
}

// --- Wind Speed Increase Comparison Bar Chart ---

export function renderWindSpeedIncreaseChart(
  container: HTMLElement,
  panelData: SeaBreezePanelData,
): void {
  if (speedIncreaseChart) speedIncreaseChart.dispose();

  // Build data: target first, then analogs
  const labels: string[] = [];
  const values: (number | null)[] = [];
  const colors: string[] = [];

  if (panelData.target) {
    labels.push(`Target (${panelData.target.date})`);
    values.push(panelData.target.features.wind_speed_increase);
    colors.push("#228be6");
  }

  for (const analog of panelData.analogs) {
    labels.push(analog.date);
    values.push(analog.features.wind_speed_increase);
    colors.push("#adb5bd");
  }

  // Reverse for horizontal bar (bottom-to-top order)
  labels.reverse();
  values.reverse();
  colors.reverse();

  // Dynamic height: 40px per bar, minimum 200px
  const dynamicHeight = Math.max(200, labels.length * 40 + 80);
  container.style.height = `${dynamicHeight}px`;

  speedIncreaseChart = init(container);

  speedIncreaseChart.setOption({
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter(params: unknown) {
        const items = params as Array<{
          axisValueLabel: string;
          value: number | null;
        }>;
        if (!items.length) return "";
        const item = items[0];
        const val = item.value != null ? `${item.value.toFixed(2)} m/s` : "N/A";
        return `${item.axisValueLabel}: ${val}`;
      },
    },
    grid: { left: 140, right: 60, top: 10, bottom: 10 },
    xAxis: {
      type: "value",
      name: "m/s",
      nameLocation: "middle",
      nameGap: 25,
    },
    yAxis: {
      type: "category",
      data: labels,
      axisLabel: { fontSize: 11 },
    },
    series: [
      {
        type: "bar",
        data: values.map((v, i) => ({
          value: v,
          itemStyle: { color: colors[i] },
        })),
        barWidth: "60%",
        label: {
          show: true,
          position: "right",
          formatter(params: { value: number | null }) {
            return params.value != null ? `${params.value.toFixed(2)}` : "";
          },
          fontSize: 11,
        },
      },
    ],
  });
}

export function getSpeedIncreaseChart(): ECharts | null {
  return speedIncreaseChart;
}

function handleResize() {
  windOverlayChart?.resize();
  tempPressureChart?.resize();
  morningWindRoseChart?.resize();
  afternoonWindRoseChart?.resize();
  biasChart?.resize();
  analogDonutChart?.resize();
  analogOverlayChart?.resize();
  speedIncreaseChart?.resize();
}

window.addEventListener("resize", handleResize);
