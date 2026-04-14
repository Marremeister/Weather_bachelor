export interface HealthResponse {
  status: "healthy" | "degraded";
  database: "connected" | "disconnected";
  environment: string;
}

export interface Location {
  id: number;
  name: string;
  latitude: number;
  longitude: number;
  timezone: string;
  created_at: string;
}

export interface WeatherRecord {
  id: number;
  location_id: number;
  source: string;
  valid_time_utc: string;
  valid_time_local: string;
  true_wind_speed: number | null;
  true_wind_direction: number | null;
  temperature: number | null;
  pressure: number | null;
  cloud_cover: number | null;
}

export interface WeatherFetchResponse {
  location_id: number;
  source: string;
  start_date: string;
  end_date: string;
  records_count: number;
  cached: boolean;
}

export interface SeaBreezeClassification {
  classification: "low" | "medium" | "high";
  score: number;
  indicators: Record<string, boolean>;
}
