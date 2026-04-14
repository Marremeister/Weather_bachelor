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
