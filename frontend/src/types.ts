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

export interface AnalysisRequest {
  location_id: number;
  target_date: string;
  historical_start_date: string;
  historical_end_date: string;
  top_n: number;
}

export interface AnalogResult {
  id: number;
  analysis_run_id: number;
  analog_date: string;
  rank: number;
  similarity_score: number | null;
  distance: number | null;
  summary: string | null;
  created_at: string;
}

export interface AnalysisRunDetail {
  id: number;
  location_id: number;
  target_date: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  summary: string | null;
  historical_start_date: string | null;
  historical_end_date: string | null;
  top_n: number | null;
  created_at: string;
  analogs: AnalogResult[];
}
