from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class VehicleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    capacity: float
    speed_kmh: float
    lat: float
    lng: float
    status: str


class StopOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    label: str
    lat: float
    lng: float
    demand: float
    service_minutes: float
    window_start_min: int
    window_end_min: int
    priority: int
    status: str


class StopCreate(BaseModel):
    label: str
    lat: float
    lng: float
    demand: float = 1.0
    service_minutes: float = 5.0
    window_start_min: int = 0
    window_end_min: int = 600
    priority: int = 1


class RouteStopOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    sequence: int
    eta_min: float
    distance_from_prev_km: float
    stop: StopOut


class RouteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    vehicle_id: int
    total_distance_km: float
    total_duration_min: float
    created_at: datetime
    is_active: bool
    solver_used: str
    stops: list[RouteStopOut]


class DisruptionEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    type: str
    vehicle_id: Optional[int]
    stop_id: Optional[int]
    description: str
    delay_factor: float
    created_at: datetime
    resolved: bool


class SimulateDisruptionIn(BaseModel):
    type: Optional[str] = None  # random if omitted
    vehicle_id: Optional[int] = None


class OptimizeResult(BaseModel):
    routes: list[RouteOut]
    total_distance_km: float
    total_duration_min: float
    solver_used: str
    solve_time_ms: float
    unassigned_stop_ids: list[int]


class FleetSummary(BaseModel):
    vehicles_total: int
    vehicles_active: int
    stops_pending: int
    stops_completed: int
    on_time_pct: float
    avg_delay_min: float
    total_distance_km: float
