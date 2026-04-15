import type { AnalogHourlyResponse, AnalysisRequest, AnalysisRunDetail, AnalysisRunSummary, AnalogResult, BiasReportResponse, DistanceDistributionData, ForecastCompositeData, HealthResponse, LibraryStatusResponse, Location, ObservationFetchResponse, ObservationRecord, SeaBreezeClassification, SeaBreezePanelData, SeasonalHeatmapData, ValidationMetrics, ValidationRunResult, ValidationRunStatus, ValidationRunSummary, WeatherFetchResponse, WeatherRecord, WeatherStation } from "./types";

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
  source?: string,
): Promise<WeatherRecord[]> {
  const params = new URLSearchParams({
    location_id: String(locationId),
    start_date: startDate,
    end_date: endDate,
  });
  if (source) {
    params.set("source", source);
  }
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

export async function getAnalogHourly(
  runId: number,
  topN: number = 3,
): Promise<AnalogHourlyResponse> {
  const params = new URLSearchParams({ top_n: String(topN) });
  const res = await fetch(`/api/analysis/${runId}/analog-hourly?${params}`);
  if (!res.ok) throw new Error(`Analog hourly fetch failed: ${res.status}`);
  return res.json() as Promise<AnalogHourlyResponse>;
}

export async function getSeaBreezePanel(
  runId: number,
): Promise<SeaBreezePanelData> {
  const res = await fetch(`/api/analysis/${runId}/sea-breeze-panel`);
  if (!res.ok) {
    throw new Error(`Sea breeze panel fetch failed: ${res.status}`);
  }
  return res.json() as Promise<SeaBreezePanelData>;
}

export async function getSeasonalHeatmap(
  locationId: number,
  source: string = "era5",
  targetDate?: string,
  analogDates?: string[],
): Promise<SeasonalHeatmapData> {
  const params = new URLSearchParams({
    location_id: String(locationId),
    source,
  });
  if (targetDate) params.set("target_date", targetDate);
  if (analogDates) {
    for (const d of analogDates) {
      params.append("analog_dates", d);
    }
  }
  const res = await fetch(`/api/library/seasonal-heatmap?${params}`);
  if (!res.ok) throw new Error(`Seasonal heatmap fetch failed: ${res.status}`);
  return res.json() as Promise<SeasonalHeatmapData>;
}

export async function getDistanceDistribution(
  runId: number,
): Promise<DistanceDistributionData> {
  const res = await fetch(`/api/analysis/${runId}/distance-distribution`);
  if (!res.ok) throw new Error(`Distance distribution fetch failed: ${res.status}`);
  return res.json() as Promise<DistanceDistributionData>;
}

export async function getForecastComposite(
  runId: number,
): Promise<ForecastCompositeData> {
  const res = await fetch(`/api/analysis/${runId}/forecast`);
  if (!res.ok) throw new Error(`Forecast composite fetch failed: ${res.status}`);
  return res.json() as Promise<ForecastCompositeData>;
}

export async function fetchStations(): Promise<WeatherStation[]> {
  const res = await fetch("/api/observations/stations");
  if (!res.ok) throw new Error(`Stations fetch failed: ${res.status}`);
  return res.json() as Promise<WeatherStation[]>;
}

export async function fetchObservations(
  stationId: number,
  startDate: string,
  endDate: string,
): Promise<ObservationFetchResponse> {
  const res = await fetch("/api/observations/fetch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      station_id: stationId,
      start_date: startDate,
      end_date: endDate,
    }),
  });
  if (!res.ok) throw new Error(`Observation fetch failed: ${res.status}`);
  return res.json() as Promise<ObservationFetchResponse>;
}

export async function getObservations(
  stationId: number,
  startDate: string,
  endDate: string,
): Promise<ObservationRecord[]> {
  const params = new URLSearchParams({
    station_id: String(stationId),
    start_date: startDate,
    end_date: endDate,
  });
  const res = await fetch(`/api/observations?${params}`);
  if (!res.ok) throw new Error(`Observations query failed: ${res.status}`);
  return res.json() as Promise<ObservationRecord[]>;
}

// --- Batch Validation ---

export async function triggerBatchValidation(
  locationId: number,
  evaluationMethod: string = "temporal_split",
  exclusionBufferDays: number = 7,
  topN: number = 10,
): Promise<{ run_id: number; status: string }> {
  const res = await fetch("/api/validation/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      location_id: locationId,
      evaluation_method: evaluationMethod,
      exclusion_buffer_days: exclusionBufferDays,
      top_n: topN,
    }),
  });
  if (!res.ok) throw new Error(`Batch validation trigger failed: ${res.status}`);
  return res.json();
}

export async function getValidationRunStatus(
  runId: number,
): Promise<ValidationRunStatus> {
  const res = await fetch(`/api/validation/${runId}/status`);
  if (!res.ok) throw new Error(`Validation run status fetch failed: ${res.status}`);
  return res.json() as Promise<ValidationRunStatus>;
}

export async function getValidationRunResult(
  runId: number,
): Promise<ValidationRunResult> {
  const res = await fetch(`/api/validation/${runId}`);
  if (!res.ok) throw new Error(`Validation run result fetch failed: ${res.status}`);
  return res.json() as Promise<ValidationRunResult>;
}

export async function listBatchValidationRuns(
  locationId: number,
): Promise<ValidationRunSummary[]> {
  const params = new URLSearchParams({ location_id: String(locationId) });
  const res = await fetch(`/api/validation/runs?${params}`);
  if (!res.ok) throw new Error(`List validation runs failed: ${res.status}`);
  return res.json() as Promise<ValidationRunSummary[]>;
}

// --- Single-day Observation Validation ---

export async function getValidationMetrics(
  runId: number,
  stationId: number,
): Promise<ValidationMetrics> {
  const params = new URLSearchParams({ station_id: String(stationId) });
  const res = await fetch(`/api/observations/validate/${runId}?${params}`);
  if (!res.ok) throw new Error(`Validation metrics fetch failed: ${res.status}`);
  return res.json() as Promise<ValidationMetrics>;
}
