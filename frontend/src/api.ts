import type { AnalysisRequest, AnalysisRunDetail, AnalogResult, HealthResponse, Location, SeaBreezeClassification, WeatherFetchResponse, WeatherRecord } from "./types";

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch("/api/health");
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.status}`);
  }
  return res.json() as Promise<HealthResponse>;
}

export async function fetchLocations(): Promise<Location[]> {
  const res = await fetch("/api/locations");
  if (!res.ok) {
    throw new Error(`Locations fetch failed: ${res.status}`);
  }
  return res.json() as Promise<Location[]>;
}

export async function fetchWeather(
  locationId: number,
  startDate: string,
  endDate: string,
): Promise<WeatherFetchResponse> {
  const res = await fetch("/api/weather/fetch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      location_id: locationId,
      start_date: startDate,
      end_date: endDate,
    }),
  });
  if (!res.ok) {
    throw new Error(`Weather fetch failed: ${res.status}`);
  }
  return res.json() as Promise<WeatherFetchResponse>;
}

export async function getWeatherRecords(
  locationId: number,
  startDate: string,
  endDate: string,
): Promise<WeatherRecord[]> {
  const params = new URLSearchParams({
    location_id: String(locationId),
    start_date: startDate,
    end_date: endDate,
  });
  const res = await fetch(`/api/weather?${params}`);
  if (!res.ok) {
    throw new Error(`Weather records fetch failed: ${res.status}`);
  }
  return res.json() as Promise<WeatherRecord[]>;
}

export async function fetchClassification(
  locationId: number,
  date: string,
): Promise<SeaBreezeClassification> {
  const params = new URLSearchParams({
    location_id: String(locationId),
    date: date,
  });
  const res = await fetch(`/api/classification?${params}`);
  if (!res.ok) {
    throw new Error(`Classification fetch failed: ${res.status}`);
  }
  return res.json() as Promise<SeaBreezeClassification>;
}

export async function runAnalysis(
  request: AnalysisRequest,
): Promise<AnalysisRunDetail> {
  const res = await fetch("/api/analysis/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    throw new Error(`Analysis run failed: ${res.status}`);
  }
  return res.json() as Promise<AnalysisRunDetail>;
}

export async function getAnalysisRun(
  runId: number,
): Promise<AnalysisRunDetail> {
  const res = await fetch(`/api/analysis/${runId}`);
  if (!res.ok) {
    throw new Error(`Analysis run fetch failed: ${res.status}`);
  }
  return res.json() as Promise<AnalysisRunDetail>;
}

export async function getAnalysisAnalogs(
  runId: number,
): Promise<AnalogResult[]> {
  const res = await fetch(`/api/analysis/${runId}/analogs`);
  if (!res.ok) {
    throw new Error(`Analysis analogs fetch failed: ${res.status}`);
  }
  return res.json() as Promise<AnalogResult[]>;
}
