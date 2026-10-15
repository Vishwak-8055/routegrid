"""
Generates a demo fleet + order book around Hyderabad so the app has
something realistic to look at on first run. Swap this for a real
ingestion pipeline (CSV import, TMS webhook, etc.) in production -- the
solver and API don't know or care where Vehicle/Stop rows came from.
"""
import random

from sqlalchemy.orm import Session

from app import models

DEPOT_LAT, DEPOT_LNG = 17.4239, 78.4738  # Hitech City, Hyderabad

VEHICLE_NAMES = [
    "Falcon-01", "Falcon-02", "Falcon-03", "Falcon-04", "Falcon-05", "Falcon-06",
]

STOP_LABELS = [
    "Gachibowli Tech Park", "Madhapur Complex", "Jubilee Hills Residency",
    "Banjara Hills Tower", "Kondapur Warehouse", "Kukatpally Mall",
    "Begumpet Office Park", "Secunderabad Station Hub", "Ameerpet Retail",
    "Miyapur Depot Annex", "LB Nagar Distribution", "Uppal Industrial Estate",
    "Dilsukhnagar Market", "Somajiguda Plaza", "Manikonda Heights",
    "Nanakramguda Financial District", "Shamshabad Cargo Terminal",
    "Kompally Logistics Park", "Malkajgiri Depot", "Attapur Junction",
]


def seed_if_empty(db: Session, n_stops: int = 16, n_vehicles: int = 5) -> None:
    if db.query(models.Depot).first() is not None:
        return  # already seeded

    rng = random.Random(7)
    depot = models.Depot(name="Hitech City Depot", lat=DEPOT_LAT, lng=DEPOT_LNG)
    db.add(depot)

    for i in range(n_vehicles):
        db.add(models.Vehicle(
            name=VEHICLE_NAMES[i % len(VEHICLE_NAMES)],
            capacity=rng.choice([80, 100, 120]),
            speed_kmh=rng.choice([26, 30, 34]),
            lat=DEPOT_LAT + rng.uniform(-0.003, 0.003),
            lng=DEPOT_LNG + rng.uniform(-0.003, 0.003),
            status=models.VehicleStatus.idle,
        ))

    for i in range(n_stops):
        label = STOP_LABELS[i % len(STOP_LABELS)]
        db.add(models.Stop(
            label=label if i < len(STOP_LABELS) else f"{label} #{i}",
            lat=DEPOT_LAT + rng.uniform(-0.09, 0.09),
            lng=DEPOT_LNG + rng.uniform(-0.09, 0.09),
            demand=rng.choice([5, 8, 10, 12, 15]),
            service_minutes=rng.choice([4, 6, 8]),
            window_start_min=0,
            window_end_min=rng.choice([240, 360, 480]),
            priority=1 if rng.random() > 0.15 else 2,
            status=models.StopStatus.pending,
        ))

    db.commit()
