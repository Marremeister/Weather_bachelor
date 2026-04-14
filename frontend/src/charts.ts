import { use, init, type ECharts } from "echarts/core";
import { LineChart, ScatterChart } from "echarts/charts";
import {
  GridComponent,
  TitleComponent,
  TooltipComponent,
  DataZoomComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { WeatherRecord } from "./types";

use([
  LineChart,
  ScatterChart,
  GridComponent,
  TitleComponent,
  TooltipComponent,
  DataZoomComponent,
  CanvasRenderer,
]);

let speedChart: ECharts | null = null;
let directionChart: ECharts | null = null;

export function renderWindSpeedChart(
  container: HTMLElement,
  records: WeatherRecord[],
  source?: string,
): void {
  if (speedChart) {
    speedChart.dispose();
  }
  speedChart = init(container);

  const times = records.map((r) => {
    const d = new Date(r.valid_time_local);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  });
  const speeds = records.map((r) => r.true_wind_speed);

  speedChart.setOption({
    title: source
      ? {
          subtext: `Source: ${source}`,
          subtextStyle: { fontSize: 11, color: "#868e96" },
          left: "center",
        }
      : undefined,
    tooltip: {
      trigger: "axis",
      formatter(params: unknown) {
        const p = (params as Array<{ axisValueLabel: string; value: number | null }>)[0];
        const val = p.value != null ? `${p.value.toFixed(1)} m/s` : "N/A";
        return `${p.axisValueLabel}<br/>Wind speed: ${val}`;
      },
    },
    grid: { left: 50, right: 20, top: source ? 35 : 20, bottom: 50 },
    xAxis: {
      type: "category",
      data: times,
      axisLabel: { rotate: 45, fontSize: 11 },
    },
    yAxis: {
      type: "value",
      name: "m/s",
      nameLocation: "middle",
      nameGap: 35,
    },
    dataZoom: [{ type: "inside" }],
    series: [
      {
        type: "line",
        data: speeds,
        smooth: true,
        symbol: "circle",
        symbolSize: 4,
        lineStyle: { color: "#228be6", width: 2 },
        itemStyle: { color: "#228be6" },
      },
    ],
  });
}

export function renderWindDirectionChart(
  container: HTMLElement,
  records: WeatherRecord[],
  source?: string,
): void {
  if (directionChart) {
    directionChart.dispose();
  }
  directionChart = init(container);

  const data = records
    .map((r, i) => [i, r.true_wind_direction])
    .filter((d) => d[1] != null);

  const times = records.map((r) => {
    const d = new Date(r.valid_time_local);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  });

  directionChart.setOption({
    title: source
      ? {
          subtext: `Source: ${source}`,
          subtextStyle: { fontSize: 11, color: "#868e96" },
          left: "center",
        }
      : undefined,
    tooltip: {
      trigger: "item",
      formatter(params: unknown) {
        const p = params as { dataIndex: number; value: [number, number] };
        const idx = p.value[0];
        const deg = p.value[1];
        return `${times[idx]}<br/>Direction: ${deg}°`;
      },
    },
    grid: { left: 50, right: 20, top: source ? 35 : 20, bottom: 50 },
    xAxis: {
      type: "category",
      data: times,
      axisLabel: { rotate: 45, fontSize: 11 },
    },
    yAxis: {
      type: "value",
      min: 0,
      max: 360,
      interval: 90,
      axisLabel: {
        formatter(value: number) {
          const labels: Record<number, string> = {
            0: "N (0°)",
            90: "E (90°)",
            180: "S (180°)",
            270: "W (270°)",
            360: "N (360°)",
          };
          return labels[value] ?? `${value}°`;
        },
      },
    },
    dataZoom: [{ type: "inside" }],
    series: [
      {
        type: "scatter",
        data,
        symbolSize: 6,
        itemStyle: { color: "#e67700" },
      },
    ],
  });
}

export function getSpeedChart(): ECharts | null {
  return speedChart;
}

export function getDirectionChart(): ECharts | null {
  return directionChart;
}

function handleResize() {
  speedChart?.resize();
  directionChart?.resize();
}

window.addEventListener("resize", handleResize);
