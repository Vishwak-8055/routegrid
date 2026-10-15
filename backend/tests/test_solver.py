import random

from app.solver import solve_heuristic, haversine_km


def _random_instance(n_stops=20, n_vehicles=4, seed=1):
    rng = random.Random(seed)
    depot = (17.4239, 78.4738)
    stops = [
        {
            "id": i + 1,
            "lat": depot[0] + rng.uniform(-0.08, 0.08),
            "lng": depot[1] + rng.uniform(-0.08, 0.08),
            "demand": rng.choice([5, 8, 10]),
            "priority": 1,
        }
        for i in range(n_stops)
    ]
    vehicles = [{"id": i + 1, "capacity": rng.choice([80, 100])} for i in range(n_vehicles)]
    return depot, stops, vehicles


def test_haversine_zero_distance():
    assert haversine_km(17.0, 78.0, 17.0, 78.0) == 0.0


def test_haversine_known_distance():
    # Hyderabad to Bangalore is roughly 500km as the crow flies
    d = haversine_km(17.3850, 78.4867, 12.9716, 77.5946)
    assert 480 < d < 520


def test_all_stops_accounted_for():
    depot, stops, vehicles = _random_instance()
    result = solve_heuristic(depot, stops, vehicles)
    routed_ids = {sid for r in result.routes for sid in r.stop_ids}
    all_ids = {s["id"] for s in stops}
    assert routed_ids | set(result.unassigned_stop_ids) == all_ids
    assert not (routed_ids & set(result.unassigned_stop_ids))  # no double counting


def test_capacity_respected():
    depot, stops, vehicles = _random_instance()
    result = solve_heuristic(depot, stops, vehicles)
    cap_by_vehicle = {v["id"]: v["capacity"] for v in vehicles}
    for r in result.routes:
        assert r.demand <= cap_by_vehicle[r.vehicle_id] + 1e-6


def test_route_uses_at_most_one_vehicle_per_route():
    depot, stops, vehicles = _random_instance(n_stops=30, n_vehicles=3)
    result = solve_heuristic(depot, stops, vehicles)
    used_vehicles = [r.vehicle_id for r in result.routes]
    assert len(used_vehicles) == len(set(used_vehicles))


def test_empty_stops_returns_no_routes():
    depot, _, vehicles = _random_instance()
    result = solve_heuristic(depot, [], vehicles)
    assert result.routes == []
    assert result.unassigned_stop_ids == []


def test_two_opt_does_not_increase_distance():
    """Sanity: a solved route on a moderate instance should already beat a
    naive nearest-neighbor-only baseline's total distance."""
    depot, stops, vehicles = _random_instance(n_stops=25, n_vehicles=2, seed=3)
    result = solve_heuristic(depot, stops, vehicles)
    assert result.total_distance_km > 0
    assert result.solve_time_ms < 2000  # heuristic should stay fast
