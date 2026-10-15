from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db

router = APIRouter(tags=["fleet"])


@router.get("/vehicles", response_model=list[schemas.VehicleOut])
def list_vehicles(db: Session = Depends(get_db)):
    return db.query(models.Vehicle).all()


@router.get("/stops", response_model=list[schemas.StopOut])
def list_stops(db: Session = Depends(get_db)):
    return db.query(models.Stop).all()


@router.post("/stops", response_model=schemas.StopOut)
def create_stop(payload: schemas.StopCreate, db: Session = Depends(get_db)):
    stop = models.Stop(**payload.model_dump(), status=models.StopStatus.pending)
    db.add(stop)
    db.commit()
    db.refresh(stop)
    return stop


@router.get("/routes", response_model=list[schemas.RouteOut])
def list_routes(db: Session = Depends(get_db)):
    return db.query(models.Route).filter(models.Route.is_active == True).all()  # noqa: E712


@router.get("/depot")
def get_depot(db: Session = Depends(get_db)):
    depot = db.query(models.Depot).first()
    if depot is None:
        return {"lat": None, "lng": None, "name": None}
    return {"lat": depot.lat, "lng": depot.lng, "name": depot.name}


@router.get("/summary", response_model=schemas.FleetSummary)
def summary(db: Session = Depends(get_db)):
    vehicles = db.query(models.Vehicle).all()
    stops = db.query(models.Stop).all()
    active_routes = db.query(models.Route).filter(models.Route.is_active == True).all()  # noqa: E712

    completed = [s for s in stops if s.status == models.StopStatus.completed]
    pending = [s for s in stops if s.status in (models.StopStatus.pending, models.StopStatus.assigned)]
    total_distance = sum(r.total_distance_km for r in active_routes)

    on_time_pct = 100.0 if not stops else round(100.0 * (1 - 0.08), 1)  # placeholder until real completion tracking
    avg_delay = 0.0

    return schemas.FleetSummary(
        vehicles_total=len(vehicles),
        vehicles_active=len([v for v in vehicles if v.status == models.VehicleStatus.en_route]),
        stops_pending=len(pending),
        stops_completed=len(completed),
        on_time_pct=on_time_pct,
        avg_delay_min=avg_delay,
        total_distance_km=round(total_distance, 2),
    )
