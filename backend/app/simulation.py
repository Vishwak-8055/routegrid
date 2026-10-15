"""
Disruption simulation + the re-optimization loop it triggers.

This is the "real-time" half of Waypoint: a disruption mutates state
(a vehicle breaks down, traffic hits a leg, a new urgent order lands),
then the fleet's remaining, not-yet-completed work is re-solved with the
fast heuristic so the live map reflects an updated plan within one solve
call rather than waiting for the next planning cycle.
"""
from __future__ import annotations

import random
from datetime import datetime

from sqlalchemy.orm import Session

from app import models, solver, eta

DISRUPTION_TYPES = ["traffic", "breakdown", "urgent_order", "closed_road"]

_HYDERABAD_BBOX = {  # rough city bounding box, used when spawning urgent stops
    "lat_min": 17.30, "lat_max": 17.50,
    "lng_min": 78.35, "lng_max": 78.55,
}


def _get_depot(db: Session) -> models.Depot:
    depot = db.query(models.Depot).first()
    if depot is None:
        raise RuntimeError("No depot configured -- run app.seed first")
    return depot


def trigger_disruption(
    db: Session, event_type: str | None = None, vehicle_id: int | None = None
) -> models.DisruptionEvent:
    rng = random.Random()
    event_type = event_type or rng.choice(DISRUPTION_TYPES)

    description = ""
    delay_factor = 1.0
    target_vehicle_id = vehicle_id
    target_stop_id = None

    if event_type == "breakdown":
        candidates = db.query(models.Vehicle).filter(
            models.Vehicle.status == models.VehicleStatus.en_route
        ).all()
        if vehicle_id:
            candidates = [v for v in candidates if v.id == vehicle_id] or candidates
        if not candidates:
            event_type, description = "traffic", "No active vehicle available to break down; downgraded to a traffic delay."
        else:
            veh = rng.choice(candidates)
            target_vehicle_id = veh.id
            veh.status = models.VehicleStatus.disrupted
            reassigned = 0
            for rs in db.query(models.RouteStop).join(models.Route).filter(
                models.Route.vehicle_id == veh.id, models.Route.is_active == True  # noqa: E712
            ).all():
                if rs.stop.status != models.StopStatus.completed:
                    rs.stop.status = models.StopStatus.pending
                    reassigned += 1
            description = f"{veh.name} broke down mid-route -- {reassigned} stop(s) released back to the pool."

    if event_type == "traffic":
        candidates = db.query(models.Vehicle).filter(
            models.Vehicle.status == models.VehicleStatus.en_route
        ).all()
        if vehicle_id:
            candidates = [v for v in candidates if v.id == vehicle_id] or candidates
        if candidates:
            veh = rng.choice(candidates)
            target_vehicle_id = veh.id
            delay_factor = round(rng.uniform(1.4, 2.2), 2)
            description = f"Heavy traffic reported on {veh.name}'s current leg (+{int((delay_factor - 1) * 100)}% travel time)."
        else:
            event_type, delay_factor = "closed_road", round(rng.uniform(1.1, 1.3), 2)
            description = "Traffic sensor triggered with no vehicle en route; logged as a shared closed-road delay instead."

    if event_type == "closed_road":
        delay_factor = round(rng.uniform(1.1, 1.35), 2)
        description = description or f"Road closure reported -- fleet-wide travel time +{int((delay_factor - 1) * 100)}% until cleared."

    if event_type == "urgent_order":
        depot = _get_depot(db)
        lat = rng.uniform(_HYDERABAD_BBOX["lat_min"], _HYDERABAD_BBOX["lat_max"])
        lng = rng.uniform(_HYDERABAD_BBOX["lng_min"], _HYDERABAD_BBOX["lng_max"])
        stop = models.Stop(
            label=f"Urgent order #{rng.randint(1000, 9999)}",
            lat=lat, lng=lng, demand=rng.uniform(1, 4),
            service_minutes=5, window_start_min=0, window_end_min=180,
            priority=2, status=models.StopStatus.pending,
        )
        db.add(stop)
        db.flush()
        target_stop_id = stop.id
        description = f"New urgent order dropped in ({lat:.3f}, {lng:.3f}) -- must be served within 3 hours."

    event = models.DisruptionEvent(
        type=event_type, vehicle_id=target_vehicle_id, stop_id=target_stop_id,
        description=description, delay_factor=delay_factor,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def reoptimize_fleet(db: Session, prefer_exact: bool = False) -> solver.SolveResult:
    depot = _get_depot(db)
    pending_stops = db.query(models.Stop).filter(
        models.Stop.status.in_([models.StopStatus.pending, models.StopStatus.assigned])
    ).order_by(models.Stop.priority.desc()).all()
    available_vehicles = db.query(models.Vehicle).filter(
        models.Vehicle.status != models.VehicleStatus.disrupted
    ).all()

    stop_dicts = [
        {"id": s.id, "lat": s.lat, "lng": s.lng, "demand": s.demand, "priority": s.priority}
        for s in pending_stops
    ]
    vehicle_dicts = [{"id": v.id, "capacity": v.capacity} for v in available_vehicles]

    result = solver.solve((depot.lat, depot.lng), stop_dicts, vehicle_dicts, prefer_exact=prefer_exact)

    # deactivate previous active routes, write the new plan
    db.query(models.Route).filter(models.Route.is_active == True).update(  # noqa: E712
        {"is_active": False}
    )

    active_delay = {
        e.vehicle_id: e.delay_factor
        for e in db.query(models.DisruptionEvent).filter(
            models.DisruptionEvent.resolved == False,  # noqa: E712
            models.DisruptionEvent.type.in_(["traffic", "closed_road"]),
        ).all() if e.vehicle_id
    }
    fleet_wide_delay = max(
        [e.delay_factor for e in db.query(models.DisruptionEvent).filter(
            models.DisruptionEvent.resolved == False,  # noqa: E712
            models.DisruptionEvent.type == "closed_road",
        ).all()] or [1.0]
    )

    hour = datetime.utcnow().hour
    vehicle_by_id = {v.id: v for v in available_vehicles}
    stop_by_id = {s.id: s for s in pending_stops}

    for planned in result.routes:
        veh = vehicle_by_id[planned.vehicle_id]
        route = models.Route(vehicle_id=veh.id, is_active=True, solver_used=result.solver_used)
        db.add(route)
        db.flush()
        cumulative_min = 0.0
        vfactor = active_delay.get(veh.id, 1.0) * fleet_wide_delay
        for seq, (stop_id, dist) in enumerate(zip(planned.stop_ids, planned.distances_km)):
            minutes = eta.travel_minutes(dist, veh.speed_kmh, hour, stop_index=seq, disruption_factor=vfactor)
            cumulative_min += minutes + stop_by_id[stop_id].service_minutes
            db.add(models.RouteStop(
                route_id=route.id, stop_id=stop_id, sequence=seq,
                eta_min=round(cumulative_min, 1), distance_from_prev_km=dist,
            ))
            stop_by_id[stop_id].status = models.StopStatus.assigned
        route.total_distance_km = planned.total_distance_km
        route.total_duration_min = round(cumulative_min, 1)
        veh.status = models.VehicleStatus.en_route

    for stop_id in result.unassigned_stop_ids:
        stop_by_id[stop_id].status = models.StopStatus.pending

    idle_vehicle_ids = {v.id for v in available_vehicles} - {p.vehicle_id for p in result.routes}
    for vid in idle_vehicle_ids:
        vehicle_by_id[vid].status = models.VehicleStatus.idle

    db.commit()
    return result
