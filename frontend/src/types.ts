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
  model_run_time: string | null;
  forecast_hour: number | null;
  model_name: string | null;
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
  mode?: string;
  forecast_source?: string;
  historical_source?: string;
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

export interface AnalysisRunSummary {
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
  mode: string | null;
  forecast_source: string | null;
  historical_source: string | null;
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
  mode: string | null;
  forecast_source: string | null;
  historical_source: string | null;
  created_at: string;
  analogs: AnalogResult[];
}

export interface LibraryStatusResponse {
  id?: number;
  location_id: number;
  source?: string;
  total_chunks?: number;
  completed_chunks?: number;
  status: string;
  error_message?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface BiasReportResponse {
  location_id: number;
  corrections: BiasCorrection[];
}

export interface DailyFeatures {
  location_id: number;
  date: string;
  morning_mean_wind_speed: number | null;
  morning_mean_wind_direction: number | null;
  reference_wind_speed: number | null;
  reference_wind_direction: number | null;
  afternoon_max_wind_speed: number | null;
  afternoon_mean_wind_direction: number | null;
  wind_speed_increase: number | null;
  wind_direction_shift: number | null;
  onshore_fraction: number | null;
  hours_available: number;
  morning_hours_used: number;
  afternoon_hours_used: number;
}

export interface SeaBreezeThresholds {
  minimum_speed_increase_mps: number;
  minimum_direction_shift_degrees: number;
  minimum_onshore_fraction: number;
}

export interface DayClassificationDetail {
  date: string;
  features: DailyFeatures;
  classification: SeaBreezeClassification;
}

export interface SeaBreezePanelData {
  run_id: number;
  target: DayClassificationDetail | null;
  analogs: DayClassificationDetail[];
  thresholds: SeaBreezeThresholds;
  analog_high_count: number;
  analog_medium_count: number;
  analog_low_count: number;
  analog_total: number;
}

export interface DayHourlyRecords {
  date: string;
  rank: number | null;
  similarity_score: number | null;
  records: WeatherRecord[];
}

export interface AnalogHourlyResponse {
  run_id: number;
  target: DayHourlyRecords;
  analogs: DayHourlyRecords[];
}

export interface BiasCorrection {
  forecast_source: string;
  historical_source: string;
  feature_name: string;
  bias_mean: number;
  bias_std: number;
  calibration_start: string;
  calibration_end: string;
  sample_count: number;
}

export interface LibraryDaySummary {
  date: string;
  wind_speed_increase: number | null;
  classification: "low" | "medium" | "high";
}

export interface SeasonalHeatmapData {
  location_id: number;
  days: LibraryDaySummary[];
  target_date: string | null;
  analog_dates: string[];
}

export interface DistanceEntry {
  date: string;
  distance: number;
  similarity_score: number;
  is_top_n: boolean;
  rank: number | null;
}

export interface DistanceDistributionData {
  run_id: number;
  target_date: string;
  entries: DistanceEntry[];
  top_n_dates: string[];
}

export interface ForecastCompositeHour {
  hour_local: number;
  median_tws: number | null;
  p25_tws: number | null;
  p75_tws: number | null;
  p10_tws: number | null;
  p90_tws: number | null;
  circular_mean_twd: number | null;
  twd_circular_std: number | null;
  twd_arc_radius_75: number | null;
  analog_count: number;
}

export interface ForecastCompositeData {
  run_id: number;
  gate_result: string;
  hours: ForecastCompositeHour[] | null;
  summary: string | null;
}

export interface WeatherStation {
  id: number;
  name: string;
  station_code: string;
  source: string;
  latitude: number;
  longitude: number;
  timezone: string;
  created_at: string;
}

export interface ObservationRecord {
  id: number;
  station_id: number;
  observation_time_utc: string;
  observation_time_local: string;
  wind_speed: number | null;
  wind_direction: number | null;
  gust_speed: number | null;
  temperature: number | null;
  pressure: number | null;
  created_at: string;
}

export interface ObservationFetchResponse {
  station_id: number;
  station_code: string;
  source: string;
  start_date: string;
  end_date: string;
  count: number;
  cached: boolean;
}

// --- Batch Validation ---

export interface BatchAggregateMetrics {
  tp: number;
  fp: number;
  tn: number;
  fn: number;
  precision: number | null;
  recall: number | null;
  f1: number | null;
  tws_mae: number | null;
  tws_rmse: number | null;
  twd_circular_mae: number | null;
  peak_speed_error_mean: number | null;
  peak_speed_bias_mean: number | null;
  onset_error_mean: number | null;
  skill_score: number | null;
  total_days: number;
  insufficient_days: number;
  sea_breeze_days: number;
  forecast_produced_days: number;
}

export interface GateSensitivityEntry {
  gate_level: number;
  gate_label: string;
  coverage: number | null;
  tp: number;
  fp: number;
  tn: number;
  fn: number;
  precision: number | null;
  recall: number | null;
  f1: number | null;
  conditional_tws_mae: number | null;
  conditional_tws_rmse: number | null;
}

export interface SourceStratificationEntry {
  source: string;
  day_count: number;
  tws_mae: number | null;
  tws_rmse: number | null;
  twd_circular_mae: number | null;
}

export interface ValidationRunStatus {
  id: number;
  status: string;
  total_days: number;
  completed_days: number;
  error_message: string | null;
}

export interface ValidationRunResult {
  id: number;
  location_id: number;
  evaluation_method: string;
  exclusion_buffer_days: number;
  top_n: number;
  library_start_date: string | null;
  library_end_date: string | null;
  test_start_date: string | null;
  test_end_date: string | null;
  historical_source: string | null;
  forecast_source: string | null;
  status: string;
  total_days: number;
  completed_days: number;
  error_message: string | null;
  aggregate_metrics: BatchAggregateMetrics | null;
  gate_sensitivity: GateSensitivityEntry[] | null;
  source_stratification: SourceStratificationEntry[] | null;
  per_day_results: Record<string, unknown>[] | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string | null;
}

export interface ValidationRunSummary {
  id: number;
  location_id: number;
  evaluation_method: string;
  status: string;
  total_days: number;
  completed_days: number;
  started_at: string | null;
  finished_at: string | null;
  created_at: string | null;
}

// --- Single-day Observation Validation ---

export interface ValidationMetrics {
  tws_mae: number | null;
  tws_max_error: number | null;
  twd_circular_mae: number | null;
  twd_max_error: number | null;
  peak_speed_forecast: number | null;
  peak_speed_observed: number | null;
  peak_speed_error: number | null;
  onset_hour_forecast: number | null;
  onset_hour_observed: number | null;
  onset_error_hours: number | null;
  matched_hours: number;
  total_forecast_hours: number;
  total_observation_hours: number;
}
