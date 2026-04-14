import type { AnalysisRequest, AnalysisRunDetail, AnalysisRunSummary, AnalogResult, BiasReportResponse, HealthResponse, LibraryStatusResponse, Location, SeaBreezeClassification, WeatherFetchResponse, WeatherRecord } from "./types";

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

export async function listAnalysisRuns(
  locationId?: number,
): Promise<AnalysisRunSummary[]> {
  const params = new URLSearchParams();
  if (locationId !== undefined) {
    params.set("location_id", String(locationId));
  }
  const qs = params.toString();
  const res = await fetch(`/api/analysis${qs ? `?${qs}` : ""}`);
  if (!res.ok) {
    throw new Error(`List analysis runs failed: ${res.status}`);
  }
  return res.json() as Promise<AnalysisRunSummary[]>;
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

export async function triggerLibraryBuild(
  locationId: number,
  source: string = "era5",
): Promise<{ status: string; location_id: number; source: string }> {
  const params = new URLSearchParams({
    location_id: String(locationId),
    source,
  });
  const res = await fetch(`/api/library/build?${params}`, { method: "POST" });
  if (!res.ok) {
    throw new Error(`Library build trigger failed: ${res.status}`);
  }
  return res.json();
}

export async function getLibraryStatus(
  locationId: number,
): Promise<LibraryStatusResponse> {
  const params = new URLSearchParams({
    location_id: String(locationId),
  });
  const res = await fetch(`/api/library/status?${params}`);
  if (!res.ok) {
    throw new Error(`Library status fetch failed: ${res.status}`);
  }
  return res.json() as Promise<LibraryStatusResponse>;
}

export async function triggerBiasCalibration(
  locationId: number,
): Promise<{ status: string; location_id: number }> {
  const params = new URLSearchParams({
    location_id: String(locationId),
  });
  const res = await fetch(`/api/library/calibrate?${params}`, { method: "POST" });
  if (!res.ok) {
    throw new Error(`Bias calibration trigger failed: ${res.status}`);
  }
  return res.json();
}

export async function getBiasReport(
  locationId: number,
): Promise<BiasReportResponse> {
  const params = new URLSearchParams({
    location_id: String(locationId),
  });
  const res = await fetch(`/api/library/bias-report?${params}`);
  if (!res.ok) {
    throw new Error(`Bias report fetch failed: ${res.status}`);
  }
  return res.json() as Promise<BiasReportResponse>;
}
