import { use, init, type ECharts } from "echarts/core";
import { LineChart, ScatterChart } from "echarts/charts";
import {
  GridComponent,
  TitleComponent,
  TooltipComponent,
  DataZoomComponent,
  LegendComponent,
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
  LegendComponent,
  CanvasRenderer,
]);

let windOverlayChart: ECharts | null = null;
let tempPressureChart: ECharts | null = null;

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
          subtext: `Source: ${source}`,
          subtextStyle: { fontSize: 11, color: "#868e96" },
          left: "center",
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
    legend: { top: source ? 25 : 0, left: "center" },
    grid: { left: 50, right: 65, top: source ? 60 : 40, bottom: 50 },
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

  tempPressureChart.setOption({
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
    legend: { top: source ? 25 : 0, left: "center" },
    grid: { left: 50, right: 65, top: source ? 60 : 40, bottom: 50 },
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

function handleResize() {
  windOverlayChart?.resize();
  tempPressureChart?.resize();
}

window.addEventListener("resize", handleResize);
