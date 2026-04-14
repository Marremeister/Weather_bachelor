import type { HealthResponse, Location, WeatherFetchResponse, WeatherRecord } from "./types";

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
