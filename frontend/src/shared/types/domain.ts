export type Coordinate = [longitude: number, latitude: number];

export type PointKind = "request" | "brigade";
export type PlacementMode = PointKind | null;

export interface PointDraft {
  kind: PointKind;
  longitude: number;
  latitude: number;
}

export interface ServiceRequest {
  id: string;
  external_id?: string;
  address: string;
  latitude: number;
  longitude: number;
  service_minutes: number;
  window_start: string;
  window_end: string;
  required_skill: "connection" | "local" | "emergency" | string;
  required_transport?: string | null;
  priority: "normal" | "urgent" | string;
  status: "pending" | "planned" | "completed" | "canceled" | string;
  created_at: string;
  updated_at: string;
}

export interface Brigade {
  id: string;
  name: string;
  start_address: string;
  start_latitude: number;
  start_longitude: number;
  shift_start: string;
  shift_end: string;
  skills: string[];
  transport: string;
  status: "available" | "unavailable" | string;
  created_at: string;
  updated_at: string;
}

export interface RouteStop {
  sequence: number;
  job_id: string;
  from_location_id: string;
  travel_minutes: number;
  distance_km: number;
  arrival_minutes: number;
  service_start_minutes: number;
  service_end_minutes: number;
  waiting_minutes: number;
}

export interface RouteGeometry {
  type: "LineString";
  coordinates: Coordinate[];
}

export interface PlannedRoute {
  engineer_id: string;
  departure_minutes: number;
  finish_minutes: number;
  stops: RouteStop[];
  total_travel_minutes: number;
  total_waiting_minutes: number;
  total_service_minutes: number;
  total_distance_km: number;
  geometry?: RouteGeometry;
}

export interface PlanMetrics {
  completed_jobs: number;
  unassigned_urgent_jobs: number;
  unassigned_jobs: number;
  active_engineers: number;
  total_distance_km: number;
  total_travel_minutes: number;
  total_waiting_minutes: number;
  max_route_duration_minutes: number;
  workload_stddev_minutes: number;
  runtime_seconds: number;
  objective_value?: number | null;
}

export interface PlanSolution {
  solver_name: string;
  status: string;
  routes: PlannedRoute[];
  unassigned: Array<{ job_id: string; code: string; message: string }>;
  metrics: PlanMetrics;
  seed: number;
  warnings: string[];
  explanations?: Record<string, string>;
  baseline?: {
    solver_name: string;
    metrics: PlanMetrics;
  };
}

export interface Plan {
  id: string;
  source_plan_id?: string;
  status: string;
  solver_name: string;
  seed: number;
  time_limit_seconds: number;
  solution?: PlanSolution;
  error_message?: string;
  created_at: string;
  completed_at?: string;
}

export interface CreateRequestInput {
  address: string;
  latitude: number;
  longitude: number;
  service_minutes: number;
  window_start: string;
  window_end: string;
  required_skill: string;
  required_transport?: string | null;
  priority: string;
}

export interface CreateBrigadeInput {
  name: string;
  start_address: string;
  start_latitude: number;
  start_longitude: number;
  shift_start: string;
  shift_end: string;
  skills: string[];
  transport: string;
}

export interface RunPlanInput {
  solver_name: string;
  time_limit_seconds: number;
  seed: number;
}
