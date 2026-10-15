from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas, simulation
from app.database import get_db
from app.ws_manager import manager

router = APIRouter(tags=["dispatch"])


@router.post("/optimize", response_model=schemas.OptimizeResult)
async def optimize(prefer_exact: bool = False, db: Session = Depends(get_db)):
    result = simulation.reoptimize_fleet(db, prefer_exact=prefer_exact)
    routes = db.query(models.Route).filter(models.Route.is_active == True).all()  # noqa: E712

    payload = schemas.OptimizeResult(
        routes=routes,
        total_distance_km=result.total_distance_km,
        total_duration_min=sum(r.total_duration_min for r in routes),
        solver_used=result.solver_used,
        solve_time_ms=round(result.solve_time_ms, 2),
        unassigned_stop_ids=result.unassigned_stop_ids,
    )
    await manager.broadcast({"event": "plan_updated", "data": _serialize_routes(routes)})
    return payload


@router.post("/disruptions/simulate", response_model=schemas.DisruptionEventOut)
async def simulate_disruption(
    payload: schemas.SimulateDisruptionIn, db: Session = Depends(get_db)
):
    event = simulation.trigger_disruption(db, event_type=payload.type, vehicle_id=payload.vehicle_id)
    result = simulation.reoptimize_fleet(db)
    routes = db.query(models.Route).filter(models.Route.is_active == True).all()  # noqa: E712

    await manager.broadcast({
        "event": "disruption",
        "data": {
            "id": event.id, "type": event.type, "description": event.description,
            "vehicle_id": event.vehicle_id, "stop_id": event.stop_id,
        },
    })
    await manager.broadcast({"event": "plan_updated", "data": _serialize_routes(routes)})
    return event


@router.get("/disruptions", response_model=list[schemas.DisruptionEventOut])
def list_disruptions(db: Session = Depends(get_db)):
    return db.query(models.DisruptionEvent).order_by(models.DisruptionEvent.created_at.desc()).limit(30).all()


def _serialize_routes(routes: list[models.Route]) -> list[dict]:
    return [
        {
            "id": r.id,
            "vehicle_id": r.vehicle_id,
            "total_distance_km": r.total_distance_km,
            "total_duration_min": r.total_duration_min,
            "solver_used": r.solver_used,
            "stops": [
                {
                    "sequence": rs.sequence,
                    "eta_min": rs.eta_min,
                    "stop_id": rs.stop_id,
                    "lat": rs.stop.lat,
                    "lng": rs.stop.lng,
                    "label": rs.stop.label,
                    "priority": rs.stop.priority,
                }
                for rs in r.stops
            ],
        }
        for r in routes
    ]
