"""
Domain model.

Depot        -- single origin/return point for the fleet (extend to a list
                for multi-depot VRP; the solver already takes a depot index).
Vehicle      -- a fleet unit with capacity + live position.
Stop         -- a delivery/pickup demand point with a service time window.
Route        -- one vehicle's planned sequence of stops for the current run.
RouteStop    -- ordered join of Route -> Stop, carrying the solver's ETA.
DisruptionEvent -- an event injected (or simulated) that invalidates part of
                the current plan and triggers re-optimization.
"""
import enum
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum
)
from sqlalchemy.orm import relationship

from app.database import Base


class VehicleStatus(str, enum.Enum):
    idle = "idle"
    en_route = "en_route"
    disrupted = "disrupted"
    returning = "returning"


class StopStatus(str, enum.Enum):
    pending = "pending"
    assigned = "assigned"
    completed = "completed"
    skipped = "skipped"


class DisruptionType(str, enum.Enum):
    traffic = "traffic"
    breakdown = "breakdown"
    urgent_order = "urgent_order"
    closed_road = "closed_road"


class Depot(Base):
    __tablename__ = "depots"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    capacity = Column(Float, nullable=False, default=100.0)
    speed_kmh = Column(Float, nullable=False, default=32.0)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    status = Column(Enum(VehicleStatus), default=VehicleStatus.idle, nullable=False)

    routes = relationship("Route", back_populates="vehicle")


class Stop(Base):
    __tablename__ = "stops"

    id = Column(Integer, primary_key=True)
    label = Column(String, nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    demand = Column(Float, nullable=False, default=1.0)
    service_minutes = Column(Float, nullable=False, default=5.0)
    window_start_min = Column(Integer, nullable=False, default=0)
    window_end_min = Column(Integer, nullable=False, default=600)
    priority = Column(Integer, nullable=False, default=1)  # 1 normal, 2 urgent
    status = Column(Enum(StopStatus), default=StopStatus.pending, nullable=False)

    route_links = relationship("RouteStop", back_populates="stop")


class Route(Base):
    __tablename__ = "routes"

    id = Column(Integer, primary_key=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    total_distance_km = Column(Float, default=0.0)
    total_duration_min = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    solver_used = Column(String, default="heuristic")  # "heuristic" | "ortools"

    vehicle = relationship("Vehicle", back_populates="routes")
    stops = relationship(
        "RouteStop", back_populates="route",
        order_by="RouteStop.sequence", cascade="all, delete-orphan"
    )


class RouteStop(Base):
    __tablename__ = "route_stops"

    id = Column(Integer, primary_key=True)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=False)
    stop_id = Column(Integer, ForeignKey("stops.id"), nullable=False)
    sequence = Column(Integer, nullable=False)
    eta_min = Column(Float, nullable=False, default=0.0)
    distance_from_prev_km = Column(Float, nullable=False, default=0.0)

    route = relationship("Route", back_populates="stops")
    stop = relationship("Stop", back_populates="route_links")


class DisruptionEvent(Base):
    __tablename__ = "disruption_events"

    id = Column(Integer, primary_key=True)
    type = Column(Enum(DisruptionType), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True)
    stop_id = Column(Integer, ForeignKey("stops.id"), nullable=True)
    description = Column(String, nullable=False)
    delay_factor = Column(Float, default=1.0)  # multiplier applied to travel time
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved = Column(Boolean, default=False)
