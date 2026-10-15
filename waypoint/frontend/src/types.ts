export interface Vehicle {
  id: number;
  name: string;
  capacity: number;
  speed_kmh: number;
  lat: number;
  lng: number;
  status: "idle" | "en_route" | "disrupted" | "returning";
}

export interface Stop {
  id: number;
  label: string;
  lat: number;
  lng: number;
  demand: number;
  service_minutes: number;
  window_start_min: number;
  window_end_min: number;
  priority: number;
  status: "pending" | "assigned" | "completed" | "skipped";
}

export interface RouteStop {
  sequence: number;
  eta_min: number;
  distance_from_prev_km: number;
  stop: Stop;
}

export interface Route {
  id: number;
  vehicle_id: number;
  total_distance_km: number;
  total_duration_min: number;
  created_at: string;
  is_active: boolean;
  solver_used: string;
  stops: RouteStop[];
}

export interface DisruptionEvent {
  id: number;
  type: string;
  vehicle_id: number | null;
  stop_id: number | null;
  description: string;
  delay_factor: number;
  created_at: string;
  resolved: boolean;
}

export interface FleetSummary {
  vehicles_total: number;
  vehicles_active: number;
  stops_pending: number;
  stops_completed: number;
  on_time_pct: number;
  avg_delay_min: number;
  total_distance_km: number;
}

export interface Depot {
  name: string;
  lat: number;
  lng: number;
}
