import { use, init, type ECharts } from "echarts/core";
import { LineChart, ScatterChart, BarChart, CustomChart, PieChart, RadarChart, HeatmapChart } from "echarts/charts";
import {
  GridComponent,
  TitleComponent,
  TooltipComponent,
  DataZoomComponent,
  LegendComponent,
  PolarComponent,
  RadarComponent,
  MarkLineComponent,
  CalendarComponent,
  VisualMapContinuousComponent,
  VisualMapPiecewiseComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { WeatherRecord, BiasCorrection, DayHourlyRecords, SeaBreezePanelData, SeasonalHeatmapData, DistanceDistributionData, ForecastCompositeData, DayHourlyRecords as DayHourly, ObservationRecord } from "./types";

use([
  LineChart,
  ScatterChart,
  BarChart,
  CustomChart,
  PieChart,
  RadarChart,
  HeatmapChart,
  GridComponent,
  TitleComponent,
  TooltipComponent,
  DataZoomComponent,
  LegendComponent,
  PolarComponent,
  RadarComponent,
  MarkLineComponent,
  CalendarComponent,
  VisualMapContinuousComponent,
  VisualMapPiecewiseComponent,
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
let featureRadarChart: ECharts | null = null;
let directionShiftChart: ECharts | null = null;
let seasonalHeatmapChart: ECharts | null = null;
let distanceHistogramChart: ECharts | null = null;
let forecastChart: ECharts | null = null;
let valTimeseriesChart: ECharts | null = null;
let valHistogramChart: ECharts | null = null;
let valMonthlyChart: ECharts | null = null;

export function renderWindOverlayChart(
  container: HTMLElement,
  records: WeatherRecord[],
  source?: string,
  observations?: ObservationRecord[],
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

  const series: Array<Record<string, unknown>> = [
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
  ];

  // Optional observation overlay
  if (observations && observations.length > 0) {
    const obsByHour = new Map<number, ObservationRecord>();
    for (const obs of observations) {
      const h = new Date(obs.observation_time_local).getHours();
      if (!obsByHour.has(h)) obsByHour.set(h, obs);
    }

    const obsTwsData = records.map((r) => {
      const h = new Date(r.valid_time_local).getHours();
      return obsByHour.get(h)?.wind_speed ?? null;
    });
    const obsTwdData = records.map((r) => {
      const h = new Date(r.valid_time_local).getHours();
      return obsByHour.get(h)?.wind_direction ?? null;
    });

    series.push({
      name: "Observed TWS",
      type: "line",
      yAxisIndex: 0,
      data: obsTwsData,
      smooth: true,
      symbol: "diamond",
      symbolSize: 7,
      lineStyle: { color: "#2b8a3e", width: 2 },
      itemStyle: { color: "#2b8a3e" },
      z: 6,
    });
    series.push({
      name: "Observed TWD",
      type: "scatter",
      yAxisIndex: 1,
      data: obsTwdData,
      symbolSize: 7,
      symbol: "diamond",
      itemStyle: { color: "#2b8a3e" },
      z: 6,
    });
  }

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
              ? item.seriesName.includes("TWD")
                ? `${item.value}°`
                : `${item.value.toFixed(1)} m/s`
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
    series,
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

// --- Feature Radar Chart ---

interface RadarFeatureDef {
  key: keyof import("./types").DailyFeatures;
  label: string;
}

const RADAR_FEATURES: RadarFeatureDef[] = [
  { key: "morning_mean_wind_speed", label: "Morning Speed" },
  { key: "morning_mean_wind_direction", label: "Morning Dir" },
  { key: "reference_wind_speed", label: "Ref Speed" },
  { key: "reference_wind_direction", label: "Ref Dir" },
  { key: "afternoon_max_wind_speed", label: "Afternoon Max" },
  { key: "afternoon_mean_wind_direction", label: "Afternoon Dir" },
  { key: "wind_speed_increase", label: "Speed Increase" },
  { key: "wind_direction_shift", label: "Dir Shift" },
  { key: "onshore_fraction", label: "Onshore Frac" },
];

function getFeatureValue(features: import("./types").DailyFeatures, key: keyof import("./types").DailyFeatures): number | null {
  const v = features[key];
  return typeof v === "number" ? v : null;
}

export function renderFeatureRadarChart(
  container: HTMLElement,
  panelData: SeaBreezePanelData,
): void {
  if (featureRadarChart) featureRadarChart.dispose();
  featureRadarChart = init(container);

  if (!panelData.target) return;

  const targetFeatures = panelData.target.features;

  // Collect all feature values across target + analogs for normalization
  const allValues: (number | null)[][] = RADAR_FEATURES.map(() => []);
  for (let i = 0; i < RADAR_FEATURES.length; i++) {
    const key = RADAR_FEATURES[i].key;
    allValues[i].push(getFeatureValue(targetFeatures, key));
    for (const analog of panelData.analogs) {
      allValues[i].push(getFeatureValue(analog.features, key));
    }
  }

  // Compute min/max for each feature
  const mins: number[] = [];
  const maxs: number[] = [];
  for (let i = 0; i < RADAR_FEATURES.length; i++) {
    const nums = allValues[i].filter((v): v is number => v != null);
    if (nums.length === 0) {
      mins.push(0);
      maxs.push(1);
    } else {
      mins.push(Math.min(...nums));
      maxs.push(Math.max(...nums));
    }
  }

  function normalize(val: number | null, i: number): number {
    if (val == null) return 0;
    const range = maxs[i] - mins[i];
    if (range === 0) return 0.5;
    return (val - mins[i]) / range;
  }

  // Compute analog mean features
  const analogMeanRaw: (number | null)[] = RADAR_FEATURES.map((f, i) => {
    const vals = panelData.analogs
      .map((a) => getFeatureValue(a.features, f.key))
      .filter((v): v is number => v != null);
    if (vals.length === 0) return null;
    return vals.reduce((a, b) => a + b, 0) / vals.length;
  });

  // Actual values for tooltip
  const targetRaw = RADAR_FEATURES.map((f) => getFeatureValue(targetFeatures, f.key));

  // Normalized values for the polygon
  const targetNorm = targetRaw.map((v, i) => normalize(v, i));
  const analogMeanNorm = analogMeanRaw.map((v, i) => normalize(v, i));

  const indicators = RADAR_FEATURES.map((f) => ({
    name: f.label,
    max: 1,
  }));

  featureRadarChart.setOption({
    tooltip: {
      trigger: "item",
      formatter(params: unknown) {
        const p = params as { seriesName: string; value: number[]; name: string };
        const raw = p.seriesName === "Target" ? targetRaw : analogMeanRaw;
        let html = `<strong>${p.seriesName}</strong>`;
        for (let i = 0; i < RADAR_FEATURES.length; i++) {
          const v = raw[i];
          const unit = RADAR_FEATURES[i].key.includes("direction") || RADAR_FEATURES[i].key === "wind_direction_shift" ? "°" :
                       RADAR_FEATURES[i].key === "onshore_fraction" ? "" : " m/s";
          html += `<br/>${RADAR_FEATURES[i].label}: ${v != null ? v.toFixed(1) + unit : "N/A"}`;
        }
        return html;
      },
    },
    legend: {
      bottom: 0,
      left: "center",
      data: ["Target", "Analog Mean"],
    },
    radar: {
      indicator: indicators,
      shape: "polygon",
      radius: "60%",
      splitArea: { areaStyle: { color: ["rgba(34,139,230,0.02)", "rgba(34,139,230,0.05)"] } },
      splitLine: { lineStyle: { color: "#dee2e6" } },
      axisLine: { lineStyle: { color: "#dee2e6" } },
      axisName: { fontSize: 11, color: "#495057" },
    },
    series: [
      {
        type: "radar",
        data: [
          {
            value: targetNorm,
            name: "Target",
            lineStyle: { color: "#228be6", width: 2 },
            itemStyle: { color: "#228be6" },
            areaStyle: { color: "rgba(34,139,230,0.15)" },
            symbol: "circle",
            symbolSize: 5,
          },
          {
            value: analogMeanNorm,
            name: "Analog Mean",
            lineStyle: { color: "#e67700", width: 2, type: "dashed" },
            itemStyle: { color: "#e67700" },
            areaStyle: { color: "rgba(230,119,0,0.10)" },
            symbol: "circle",
            symbolSize: 5,
          },
        ],
      },
    ],
  });
}

export function getFeatureRadarChart(): ECharts | null {
  return featureRadarChart;
}

// --- Direction Shift Lollipop Chart ---

export function renderDirectionShiftChart(
  container: HTMLElement,
  panelData: SeaBreezePanelData,
): void {
  if (directionShiftChart) directionShiftChart.dispose();

  // Build data: target first, then analogs
  const labels: string[] = [];
  const values: (number | null)[] = [];
  const colors: string[] = [];

  if (panelData.target) {
    labels.push(`Target (${panelData.target.date})`);
    values.push(panelData.target.features.wind_direction_shift);
    colors.push("#228be6");
  }

  for (const analog of panelData.analogs) {
    labels.push(analog.date);
    values.push(analog.features.wind_direction_shift);
    colors.push("#adb5bd");
  }

  // Reverse for horizontal bar (bottom-to-top order)
  labels.reverse();
  values.reverse();
  colors.reverse();

  // Dynamic height: 40px per bar, minimum 200px
  const dynamicHeight = Math.max(200, labels.length * 40 + 80);
  container.style.height = `${dynamicHeight}px`;

  directionShiftChart = init(container);

  // Compute symmetric range
  const absMax = Math.max(...values.map((v) => (v != null ? Math.abs(v) : 0)), 10);
  const axisLimit = Math.ceil(absMax / 10) * 10;

  // Color bars by sign + magnitude; target gets its own color
  const maxAbs = Math.max(...values.map((v) => (v != null ? Math.abs(v) : 0)), 1);
  const barData = values.map((v, i) => {
    if (v == null) return { value: 0, itemStyle: { color: "#dee2e6" } };
    const isTarget = colors[i] === "#228be6";
    if (isTarget) {
      return { value: v, itemStyle: { color: "#228be6", borderColor: "#1971c2", borderWidth: 1 } };
    }
    const intensity = Math.abs(v) / maxAbs;
    const alpha = 0.3 + intensity * 0.7;
    const color = v >= 0
      ? `rgba(34,139,230,${alpha.toFixed(2)})`   // blue for veering (positive)
      : `rgba(224,49,49,${alpha.toFixed(2)})`;    // red for backing (negative)
    return { value: v, itemStyle: { color } };
  });

  directionShiftChart.setOption({
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter(params: unknown) {
        const items = params as Array<{ axisValueLabel: string; value: number | null }>;
        if (!items.length) return "";
        const item = items[0];
        const val = item.value != null ? `${item.value.toFixed(1)}°` : "N/A";
        return `${item.axisValueLabel}: ${val}`;
      },
    },
    grid: { left: 140, right: 80, top: 10, bottom: 30 },
    xAxis: {
      type: "value",
      min: -axisLimit,
      max: axisLimit,
      name: "Backing (CCW)                                              Veering (CW)",
      nameLocation: "middle",
      nameGap: 18,
      nameTextStyle: { fontSize: 10, color: "#868e96" },
    },
    yAxis: {
      type: "category",
      data: labels,
      axisLabel: { fontSize: 11 },
    },
    series: [
      {
        type: "bar",
        data: barData,
        barWidth: "60%",
        label: {
          show: true,
          position: "right",
          formatter(params: { value: number | null; dataIndex: number }) {
            if (params.value == null) return "";
            // Place label on the correct side
            return `${params.value > 0 ? "+" : ""}${params.value.toFixed(1)}°`;
          },
          fontSize: 11,
        },
        markLine: {
          silent: true,
          symbol: "none",
          lineStyle: { color: "#868e96", type: "solid", width: 1 },
          data: [{ xAxis: 0 }],
          label: { show: false },
        },
      },
    ],
  });
}

export function getDirectionShiftChart(): ECharts | null {
  return directionShiftChart;
}

// --- Seasonal Calendar Heatmap ---

const CLASSIFICATION_COLORS: Record<string, string> = {
  high: "#2b8a3e",
  medium: "#e67700",
  low: "#c92a2a",
};

export function renderSeasonalHeatmapChart(
  container: HTMLElement,
  data: SeasonalHeatmapData,
  colorMode: "speed" | "classification",
): void {
  if (seasonalHeatmapChart) seasonalHeatmapChart.dispose();

  if (data.days.length === 0) return;

  // Determine year range
  const years = new Set<number>();
  for (const d of data.days) years.add(new Date(d.date).getFullYear());
  const sortedYears = [...years].sort();

  // Dynamic height: ~180px per year + 80px padding
  const dynamicHeight = Math.max(300, sortedYears.length * 180 + 80);
  container.style.height = `${dynamicHeight}px`;

  seasonalHeatmapChart = init(container);

  // Build calendar configs and heatmap data
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const calendars: any[] = [];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const series: any[] = [];

  const targetDateStr = data.target_date ?? "";
  const analogDateSet = new Set(data.analog_dates);

  sortedYears.forEach((year, idx) => {
    calendars.push({
      top: idx * 170 + 60,
      left: 60,
      right: 40,
      cellSize: ["auto", 16],
      range: [`${year}-05-01`, `${year}-09-30`],
      itemStyle: { borderWidth: 1, borderColor: "#e9ecef" },
      splitLine: { lineStyle: { color: "#dee2e6" } },
      yearLabel: { show: true, position: "left", fontSize: 14 },
      dayLabel: { firstDay: 1, nameMap: "en", fontSize: 10 },
      monthLabel: { fontSize: 11 },
    });

    // Heatmap series for this calendar year
    const yearDays = data.days.filter((d) => new Date(d.date).getFullYear() === year);

    if (colorMode === "speed") {
      series.push({
        type: "heatmap",
        coordinateSystem: "calendar",
        calendarIndex: idx,
        data: yearDays.map((d) => [d.date, d.wind_speed_increase ?? 0]),
      });
    } else {
      // Classification mode: use piecewise colors
      series.push({
        type: "heatmap",
        coordinateSystem: "calendar",
        calendarIndex: idx,
        data: yearDays.map((d) => {
          const val = d.classification === "high" ? 3 : d.classification === "medium" ? 2 : 1;
          return [d.date, val];
        }),
      });
    }

    // Scatter markers for target + analog dates in this year
    const markers: [string, number, string][] = [];
    if (targetDateStr && new Date(targetDateStr).getFullYear() === year) {
      markers.push([targetDateStr, 1, "Target"]);
    }
    for (const ad of data.analog_dates) {
      if (new Date(ad).getFullYear() === year) {
        markers.push([ad, 1, "Analog"]);
      }
    }
    if (markers.length > 0) {
      series.push({
        type: "scatter",
        coordinateSystem: "calendar",
        calendarIndex: idx,
        symbolSize: 10,
        data: markers.map((m) => ({
          value: [m[0], m[1]],
          itemStyle: {
            color: m[2] === "Target" ? "#228be6" : "#e03131",
            borderColor: "#fff",
            borderWidth: 1.5,
          },
        })),
        tooltip: {
          formatter(params: unknown) {
            const p = params as { value: [string, number] };
            const dateStr = p.value[0];
            const isTarget = dateStr === targetDateStr;
            const isAnalog = analogDateSet.has(dateStr);
            const labels: string[] = [];
            if (isTarget) labels.push("Target");
            if (isAnalog) labels.push("Analog");
            return `${dateStr}<br/>${labels.join(", ")}`;
          },
        },
        z: 10,
      });
    }
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let visualMap: any;
  if (colorMode === "speed") {
    // Compute min/max
    const vals = data.days
      .map((d) => d.wind_speed_increase)
      .filter((v): v is number => v != null);
    const vMin = vals.length > 0 ? Math.min(...vals) : 0;
    const vMax = vals.length > 0 ? Math.max(...vals) : 5;
    visualMap = {
      type: "continuous",
      min: vMin,
      max: vMax,
      calculable: true,
      orient: "horizontal",
      left: "center",
      top: 10,
      inRange: { color: ["#f8f9fa", "#74c0fc", "#228be6", "#1864ab"] },
      text: [`${vMax.toFixed(1)} m/s`, `${vMin.toFixed(1)} m/s`],
      textStyle: { fontSize: 11 },
    };
  } else {
    visualMap = {
      type: "piecewise",
      categories: ["1", "2", "3"],
      orient: "horizontal",
      left: "center",
      top: 10,
      inRange: {
        color: [CLASSIFICATION_COLORS.low, CLASSIFICATION_COLORS.medium, CLASSIFICATION_COLORS.high],
      },
      formatter(val: string) {
        return val === "3" ? "High" : val === "2" ? "Medium" : "Low";
      },
      textStyle: { fontSize: 11 },
    };
  }

  seasonalHeatmapChart.setOption({
    tooltip: {
      formatter(params: unknown) {
        const p = params as { value: [string, number]; seriesType: string };
        if (p.seriesType === "scatter") return "";
        const dateStr = p.value[0];
        const day = data.days.find((d) => d.date === dateStr);
        if (!day) return dateStr;
        const spd = day.wind_speed_increase != null ? `${day.wind_speed_increase.toFixed(2)} m/s` : "N/A";
        return `${dateStr}<br/>Speed Increase: ${spd}<br/>Classification: ${day.classification}`;
      },
    },
    visualMap,
    calendar: calendars,
    series,
  });
}

export function getSeasonalHeatmapChart(): ECharts | null {
  return seasonalHeatmapChart;
}

// --- Distance Distribution Histogram ---

export function renderDistanceHistogramChart(
  container: HTMLElement,
  data: DistanceDistributionData,
): void {
  if (distanceHistogramChart) distanceHistogramChart.dispose();

  if (data.entries.length === 0) return;

  distanceHistogramChart = init(container);

  // Bin distances into histogram
  const distances = data.entries.map((e) => e.distance);
  const dMin = Math.min(...distances);
  const dMax = Math.max(...distances);
  const binCount = Math.min(40, Math.max(15, Math.ceil(Math.sqrt(distances.length))));
  const binWidth = (dMax - dMin) / binCount || 1;

  interface Bin {
    start: number;
    end: number;
    count: number;
    topNCount: number;
  }
  const bins: Bin[] = [];
  for (let i = 0; i < binCount; i++) {
    bins.push({ start: dMin + i * binWidth, end: dMin + (i + 1) * binWidth, count: 0, topNCount: 0 });
  }

  for (const entry of data.entries) {
    let idx = Math.floor((entry.distance - dMin) / binWidth);
    if (idx >= binCount) idx = binCount - 1;
    if (idx < 0) idx = 0;
    bins[idx].count++;
    if (entry.is_top_n) bins[idx].topNCount++;
  }

  const labels = bins.map((b) => b.start.toFixed(1));
  const barData = bins.map((b) => ({
    value: b.count,
    itemStyle: {
      color: b.topNCount > 0 ? "#228be6" : "#adb5bd",
    },
  }));

  // Mark lines for individual top-N analog distances — resolve to the
  // bin that contains each analog so the line aligns with the category axis.
  const topNEntries = data.entries.filter((e) => e.is_top_n);
  const markLineData = topNEntries.map((e) => {
    let idx = Math.floor((e.distance - dMin) / binWidth);
    if (idx >= binCount) idx = binCount - 1;
    if (idx < 0) idx = 0;
    return {
      xAxis: labels[idx],
      label: {
        formatter: `#${e.rank}`,
        fontSize: 10,
        position: "end" as const,
      },
      lineStyle: { color: "#e03131", type: "dashed" as const, width: 1 },
    };
  });

  distanceHistogramChart.setOption({
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter(params: unknown) {
        const items = params as Array<{ axisValueLabel: string; value: number }>;
        if (!items.length) return "";
        const item = items[0];
        const binIdx = labels.indexOf(item.axisValueLabel);
        const bin = binIdx >= 0 ? bins[binIdx] : null;
        let html = `Distance: ${item.axisValueLabel}–${bin ? bin.end.toFixed(1) : "?"}<br/>`;
        html += `Count: ${item.value}`;
        if (bin && bin.topNCount > 0) {
          html += `<br/><span style="color:#228be6">Top-N analogs: ${bin.topNCount}</span>`;
        }
        return html;
      },
    },
    grid: { left: 60, right: 30, top: 40, bottom: 60 },
    xAxis: {
      type: "category",
      data: labels,
      name: "Euclidean Distance",
      nameLocation: "middle",
      nameGap: 35,
      axisLabel: { rotate: 45, fontSize: 10 },
    },
    yAxis: {
      type: "value",
      name: "Count",
      nameLocation: "middle",
      nameGap: 40,
    },
    series: [
      {
        type: "bar",
        data: barData,
        barWidth: "90%",
        markLine: {
          silent: true,
          symbol: "none",
          data: markLineData,
        },
      },
    ],
  });
}

export function getDistanceHistogramChart(): ECharts | null {
  return distanceHistogramChart;
}

// --- Forecast Composite Chart ---

export function renderForecastChart(
  container: HTMLElement,
  data: ForecastCompositeData,
  analogTraces?: DayHourlyRecords[],
  showTraces?: boolean,
  observations?: ObservationRecord[],
): void {
  if (forecastChart) forecastChart.dispose();

  if (!data.hours || data.hours.length === 0) return;

  forecastChart = init(container);

  const hours = data.hours;
  const xLabels = hours.map((h) => `${String(h.hour_local).padStart(2, "0")}:00`);

  // TWS data
  const medianData = hours.map((h) => h.median_tws);
  const p25Data = hours.map((h) => h.p25_tws);
  const p75Data = hours.map((h) => h.p75_tws);
  const p10Data = hours.map((h) => h.p10_tws);
  const p90Data = hours.map((h) => h.p90_tws);

  // TWD data
  const twdData = hours.map((h) => h.circular_mean_twd);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const series: any[] = [
    // 10-90 band (lighter)
    {
      name: "P10",
      type: "line",
      data: p10Data,
      lineStyle: { opacity: 0 },
      itemStyle: { opacity: 0 },
      stack: "band90",
      symbol: "none",
      z: 1,
    },
    {
      name: "P10-P90",
      type: "line",
      data: hours.map((h) =>
        h.p90_tws != null && h.p10_tws != null ? h.p90_tws - h.p10_tws : null,
      ),
      lineStyle: { opacity: 0 },
      itemStyle: { opacity: 0 },
      areaStyle: { color: "rgba(34,139,230,0.10)" },
      stack: "band90",
      symbol: "none",
      z: 1,
    },
    // 25-75 band (darker)
    {
      name: "P25",
      type: "line",
      data: p25Data,
      lineStyle: { opacity: 0 },
      itemStyle: { opacity: 0 },
      stack: "band75",
      symbol: "none",
      z: 2,
    },
    {
      name: "P25-P75 (IQR)",
      type: "line",
      data: hours.map((h) =>
        h.p75_tws != null && h.p25_tws != null ? h.p75_tws - h.p25_tws : null,
      ),
      lineStyle: { opacity: 0 },
      itemStyle: { opacity: 0 },
      areaStyle: { color: "rgba(34,139,230,0.22)" },
      stack: "band75",
      symbol: "none",
      z: 2,
    },
    // Median line
    {
      name: "Median TWS",
      type: "line",
      data: medianData,
      smooth: true,
      symbol: "circle",
      symbolSize: 6,
      lineStyle: { color: "#228be6", width: 3 },
      itemStyle: { color: "#228be6" },
      z: 5,
    },
    // TWD scatter on secondary axis
    {
      name: "Mean TWD",
      type: "scatter",
      yAxisIndex: 1,
      data: twdData,
      symbolSize: 8,
      itemStyle: { color: "#e67700" },
      z: 5,
    },
  ];

  // Optional analog trace lines
  if (showTraces && analogTraces && analogTraces.length > 0) {
    const traceColors = ["#adb5bd", "#ced4da", "#868e96", "#dee2e6", "#495057"];
    analogTraces.forEach((analog, i) => {
      const traceData = xLabels.map((_, hi) => {
        const targetHour = hours[hi].hour_local;
        const rec = analog.records.find(
          (r) => new Date(r.valid_time_local).getHours() === targetHour,
        );
        return rec?.true_wind_speed ?? null;
      });
      series.push({
        name: `#${analog.rank ?? i + 1} (${analog.date})`,
        type: "line",
        data: traceData,
        smooth: true,
        symbol: "none",
        lineStyle: {
          color: traceColors[i % traceColors.length],
          width: 1,
          type: "dotted",
        },
        z: 3,
      });
    });
  }

  // Optional observation overlay
  if (observations && observations.length > 0) {
    // Build lookup by hour
    const obsByHour = new Map<number, ObservationRecord>();
    for (const obs of observations) {
      const h = new Date(obs.observation_time_local).getHours();
      if (!obsByHour.has(h)) obsByHour.set(h, obs);
    }

    const obsTwsData = xLabels.map((_, hi) => {
      const targetHour = hours[hi].hour_local;
      const obs = obsByHour.get(targetHour);
      return obs?.wind_speed ?? null;
    });

    const obsTwdData = xLabels.map((_, hi) => {
      const targetHour = hours[hi].hour_local;
      const obs = obsByHour.get(targetHour);
      return obs?.wind_direction ?? null;
    });

    series.push({
      name: "Observed TWS",
      type: "line",
      data: obsTwsData,
      smooth: true,
      symbol: "diamond",
      symbolSize: 7,
      lineStyle: { color: "#2b8a3e", width: 2 },
      itemStyle: { color: "#2b8a3e" },
      z: 6,
    });

    series.push({
      name: "Observed TWD",
      type: "scatter",
      yAxisIndex: 1,
      data: obsTwdData,
      symbolSize: 7,
      symbol: "diamond",
      itemStyle: { color: "#2b8a3e" },
      z: 6,
    });
  }

  const legendData = ["Median TWS", "P25-P75 (IQR)", "Mean TWD"];
  if (observations && observations.length > 0) {
    legendData.push("Observed TWS", "Observed TWD");
  }

  forecastChart.setOption({
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
        const hourLabel = items[0].axisValueLabel;
        // Find the data for this hour
        const hi = xLabels.indexOf(hourLabel);
        const h = hi >= 0 ? hours[hi] : null;
        if (!h) return hourLabel;

        let html = `<strong>${hourLabel}</strong>`;
        html += `<br/>Median TWS: ${h.median_tws != null ? h.median_tws.toFixed(1) : "N/A"} m/s`;
        html += `<br/>IQR: ${h.p25_tws != null ? h.p25_tws.toFixed(1) : "?"}\u2013${h.p75_tws != null ? h.p75_tws.toFixed(1) : "?"} m/s`;
        html += `<br/>90% range: ${h.p10_tws != null ? h.p10_tws.toFixed(1) : "?"}\u2013${h.p90_tws != null ? h.p90_tws.toFixed(1) : "?"} m/s`;
        html += `<br/>Mean TWD: ${h.circular_mean_twd != null ? h.circular_mean_twd.toFixed(0) : "N/A"}\u00b0`;
        if (h.twd_circular_std != null) {
          html += ` (\u00b1${h.twd_circular_std.toFixed(0)}\u00b0)`;
        }
        html += `<br/>Analogs: ${h.analog_count}`;
        return html;
      },
    },
    legend: {
      top: 0,
      left: "center",
      data: legendData,
    },
    grid: { left: 50, right: 65, top: 35, bottom: 50 },
    xAxis: {
      type: "category",
      data: xLabels,
      axisLabel: { fontSize: 12 },
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
            const labels: Record<number, string> = { 0: "N", 90: "E", 180: "S", 270: "W", 360: "N" };
            return labels[value] ?? `${value}\u00b0`;
          },
        },
      },
    ],
    series,
  });
}

export function getForecastChart(): ECharts | null {
  return forecastChart;
}

export function disposeForecastChart(): void {
  if (forecastChart) {
    forecastChart.dispose();
    forecastChart = null;
  }
}

// --- Validation Charts ---

function maeColor(mae: number): string {
  if (mae <= 1.5) return "#40c057";
  if (mae <= 2.5) return "#fd7e14";
  return "#e03131";
}

export function renderValidationTimeSeriesChart(
  container: HTMLElement,
  perDayResults: Record<string, unknown>[],
): void {
  if (valTimeseriesChart) valTimeseriesChart.dispose();

  const rows = perDayResults
    .filter((r) => r.tws_mae != null)
    .sort((a, b) => String(a.date).localeCompare(String(b.date)));

  if (rows.length === 0) return;

  valTimeseriesChart = init(container);

  const dates = rows.map((r) => String(r.date));
  const maes = rows.map((r) => Number(r.tws_mae));

  // scatter points colored by threshold
  const scatterData = maes.map((v, i) => ({
    value: [dates[i], v],
    itemStyle: { color: maeColor(v) },
  }));

  // 7-day rolling average
  const rollingAvg: (number | null)[] = [];
  for (let i = 0; i < maes.length; i++) {
    if (i < 6) {
      rollingAvg.push(null);
    } else {
      let sum = 0;
      for (let j = i - 6; j <= i; j++) sum += maes[j];
      rollingAvg.push(sum / 7);
    }
  }

  const overallMean = maes.reduce((s, v) => s + v, 0) / maes.length;

  valTimeseriesChart.setOption({
    tooltip: {
      trigger: "axis",
      formatter(params: unknown) {
        const items = params as Array<{ seriesName: string; value: [string, number]; marker: string }>;
        if (!items.length) return "";
        let html = `${items[0].value[0]}<br/>`;
        for (const it of items) {
          if (it.value[1] != null) {
            html += `${it.marker} ${it.seriesName}: ${Number(it.value[1]).toFixed(2)} m/s<br/>`;
          }
        }
        return html;
      },
    },
    grid: { left: 60, right: 30, top: 30, bottom: 60 },
    xAxis: {
      type: "category",
      data: dates,
      axisLabel: { rotate: 45, fontSize: 10 },
    },
    yAxis: {
      type: "value",
      name: "TWS MAE (m/s)",
      nameLocation: "middle",
      nameGap: 40,
    },
    series: [
      {
        name: "MAE",
        type: "scatter",
        data: scatterData,
        symbolSize: 6,
      },
      {
        name: "7-day Avg",
        type: "line",
        data: rollingAvg.map((v, i) => [dates[i], v]),
        smooth: true,
        symbol: "none",
        lineStyle: { color: "#228be6", width: 2 },
        itemStyle: { color: "#228be6" },
        markLine: {
          silent: true,
          symbol: "none",
          data: [
            {
              yAxis: overallMean,
              label: { formatter: `Mean: ${overallMean.toFixed(2)}`, position: "insideEndTop", fontSize: 10 },
              lineStyle: { color: "#868e96", type: "dashed" as const, width: 1 },
            },
          ],
        },
      },
    ],
  });
}

export function getValTimeseriesChart(): ECharts | null {
  return valTimeseriesChart;
}

export function renderValidationHistogramChart(
  container: HTMLElement,
  perDayResults: Record<string, unknown>[],
): void {
  if (valHistogramChart) valHistogramChart.dispose();

  const maes = perDayResults
    .filter((r) => r.tws_mae != null)
    .map((r) => Number(r.tws_mae));

  if (maes.length === 0) return;

  valHistogramChart = init(container);

  const maeMin = Math.min(...maes);
  const maeMax = Math.max(...maes);
  const binCount = Math.min(40, Math.max(10, Math.ceil(Math.sqrt(maes.length))));
  const binWidth = (maeMax - maeMin) / binCount || 1;

  interface Bin { start: number; end: number; count: number; }
  const bins: Bin[] = [];
  for (let i = 0; i < binCount; i++) {
    bins.push({ start: maeMin + i * binWidth, end: maeMin + (i + 1) * binWidth, count: 0 });
  }

  for (const v of maes) {
    let idx = Math.floor((v - maeMin) / binWidth);
    if (idx >= binCount) idx = binCount - 1;
    if (idx < 0) idx = 0;
    bins[idx].count++;
  }

  const labels = bins.map((b) => b.start.toFixed(1));
  const barData = bins.map((b) => {
    const mid = (b.start + b.end) / 2;
    return {
      value: b.count,
      itemStyle: { color: maeColor(mid) },
    };
  });

  const mean = maes.reduce((s, v) => s + v, 0) / maes.length;
  const sorted = [...maes].sort((a, b) => a - b);
  const median = sorted.length % 2 === 0
    ? (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2
    : sorted[Math.floor(sorted.length / 2)];

  // Resolve mean/median to bin category labels
  const meanBinIdx = Math.min(Math.floor((mean - maeMin) / binWidth), binCount - 1);
  const medianBinIdx = Math.min(Math.floor((median - maeMin) / binWidth), binCount - 1);

  valHistogramChart.setOption({
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter(params: unknown) {
        const items = params as Array<{ axisValueLabel: string; value: number }>;
        if (!items.length) return "";
        const item = items[0];
        const binIdx = labels.indexOf(item.axisValueLabel);
        const bin = binIdx >= 0 ? bins[binIdx] : null;
        const pct = ((item.value / maes.length) * 100).toFixed(1);
        let html = `MAE: ${item.axisValueLabel}–${bin ? bin.end.toFixed(1) : "?"} m/s<br/>`;
        html += `Count: ${item.value} (${pct}%)`;
        return html;
      },
    },
    grid: { left: 60, right: 30, top: 40, bottom: 60 },
    xAxis: {
      type: "category",
      data: labels,
      name: "TWS MAE (m/s)",
      nameLocation: "middle",
      nameGap: 35,
      axisLabel: { rotate: 45, fontSize: 10 },
    },
    yAxis: {
      type: "value",
      name: "Count",
      nameLocation: "middle",
      nameGap: 40,
    },
    series: [
      {
        type: "bar",
        data: barData,
        barWidth: "90%",
        markLine: {
          silent: true,
          symbol: "none",
          data: [
            {
              xAxis: labels[meanBinIdx],
              label: { formatter: `Mean: ${mean.toFixed(2)}`, fontSize: 10, position: "end" as const },
              lineStyle: { color: "#228be6", type: "dashed" as const, width: 1 },
            },
            {
              xAxis: labels[medianBinIdx],
              label: { formatter: `Median: ${median.toFixed(2)}`, fontSize: 10, position: "end" as const },
              lineStyle: { color: "#be4bdb", type: "dashed" as const, width: 1 },
            },
          ],
        },
      },
    ],
  });
}

export function getValHistogramChart(): ECharts | null {
  return valHistogramChart;
}

export function renderValidationMonthlyChart(
  container: HTMLElement,
  perDayResults: Record<string, unknown>[],
): void {
  if (valMonthlyChart) valMonthlyChart.dispose();

  const rows = perDayResults.filter((r) => r.tws_mae != null && r.date != null);
  if (rows.length === 0) return;

  valMonthlyChart = init(container);

  const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  // Group by year+month
  const grouped: Record<string, { sum: number; count: number }> = {};
  const yearsSet = new Set<number>();
  const monthsSet = new Set<number>();

  for (const r of rows) {
    const parts = String(r.date).split("-");
    const year = Number(parts[0]);
    const month = Number(parts[1]) - 1; // 0-indexed to match monthNames
    const key = `${year}-${month}`;
    yearsSet.add(year);
    monthsSet.add(month);
    if (!grouped[key]) grouped[key] = { sum: 0, count: 0 };
    grouped[key].sum += Number(r.tws_mae);
    grouped[key].count++;
  }

  const years = [...yearsSet].sort();
  const months = [...monthsSet].sort();
  const monthLabels = months.map((m) => monthNames[m]);

  const yearColors = ["#228be6", "#40c057", "#fd7e14", "#e03131", "#be4bdb", "#fab005", "#15aabf", "#868e96"];

  const series = years.map((year, yi) => ({
    name: String(year),
    type: "bar" as const,
    data: months.map((month) => {
      const g = grouped[`${year}-${month}`];
      return g ? Math.round((g.sum / g.count) * 100) / 100 : null;
    }),
    itemStyle: { color: yearColors[yi % yearColors.length] },
    label: {
      show: true,
      position: "top" as const,
      fontSize: 9,
      formatter: (p: { value: number | null }) => (p.value != null ? p.value.toFixed(1) : ""),
    },
  }));

  valMonthlyChart.setOption({
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
    },
    legend: {
      data: years.map(String),
      top: 0,
    },
    grid: { left: 60, right: 30, top: 40, bottom: 40 },
    xAxis: {
      type: "category",
      data: monthLabels,
    },
    yAxis: {
      type: "value",
      name: "Mean TWS MAE (m/s)",
      nameLocation: "middle",
      nameGap: 40,
    },
    series,
  });
}

export function getValMonthlyChart(): ECharts | null {
  return valMonthlyChart;
}

export function disposeValidationCharts(): void {
  if (valTimeseriesChart) { valTimeseriesChart.dispose(); valTimeseriesChart = null; }
  if (valHistogramChart) { valHistogramChart.dispose(); valHistogramChart = null; }
  if (valMonthlyChart) { valMonthlyChart.dispose(); valMonthlyChart = null; }
}

// Map container element IDs to their chart instance references
const chartByContainerId: Record<string, () => ECharts | null> = {
  "wind-overlay-chart": () => windOverlayChart,
  "temp-pressure-chart": () => tempPressureChart,
  "morning-windrose-chart": () => morningWindRoseChart,
  "afternoon-windrose-chart": () => afternoonWindRoseChart,
  "bias-chart": () => biasChart,
  "analog-overlay-chart": () => analogOverlayChart,
  "speed-increase-chart": () => speedIncreaseChart,
  "feature-radar-chart": () => featureRadarChart,
  "direction-shift-chart": () => directionShiftChart,
  "seasonal-heatmap-chart": () => seasonalHeatmapChart,
  "distance-histogram-chart": () => distanceHistogramChart,
  "forecast-chart": () => forecastChart,
  "val-timeseries-chart": () => valTimeseriesChart,
  "val-histogram-chart": () => valHistogramChart,
  "val-monthly-chart": () => valMonthlyChart,
};

export function resizeChartById(containerId: string): void {
  const getter = chartByContainerId[containerId];
  if (getter) getter()?.resize();
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
  featureRadarChart?.resize();
  directionShiftChart?.resize();
  seasonalHeatmapChart?.resize();
  distanceHistogramChart?.resize();
  forecastChart?.resize();
  valTimeseriesChart?.resize();
  valHistogramChart?.resize();
  valMonthlyChart?.resize();
}

window.addEventListener("resize", handleResize);
