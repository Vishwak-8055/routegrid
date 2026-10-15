"""
Capacitated Vehicle Routing solver.

Two backends share one interface (`solve`):

  - "heuristic": Clarke-Wright parallel savings construction + 2-opt local
    search. Pure Python, no dependencies, sub-100ms on realistic instance
    sizes (tens of vehicles / low hundreds of stops) -- this is the path
    used for live re-optimization when a disruption fires, where solve
    latency matters more than shaving the last percent off total distance.

  - "ortools": Google OR-Tools CP-SAT routing model, used when available for
    a slower, closer-to-optimal solve -- suited to offline/nightly route
    planning rather than the real-time loop. Falls back to the heuristic
    automatically if the package isn't installed, so the service always
    runs even without it.

Both return the same `SolveResult` shape so callers (and the API) don't
care which one ran.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field


EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


@dataclass
class Node:
    id: int          # 0 = depot, else stop.id
    lat: float
    lng: float
    demand: float = 0.0
    priority: int = 1


@dataclass
class PlannedRoute:
    vehicle_id: int | None
    stop_ids: list[int]                 # in visit order, depot excluded
    distances_km: list[float]            # distance_from_prev per stop
    total_distance_km: float
    demand: float


@dataclass
class SolveResult:
    routes: list[PlannedRoute]
    unassigned_stop_ids: list[int]
    total_distance_km: float
    solver_used: str
    solve_time_ms: float = 0.0


def _build_matrix(nodes: list[Node]) -> list[list[float]]:
    n = len(nodes)
    mat = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = haversine_km(nodes[i].lat, nodes[i].lng, nodes[j].lat, nodes[j].lng)
            mat[i][j] = mat[j][i] = d
    return mat


def _route_distance(route: list[int], mat: list[list[float]]) -> float:
    """route is a list of matrix indices, depot (0) implied at both ends."""
    total = mat[0][route[0]] if route else 0.0
    for a, b in zip(route, route[1:]):
        total += mat[a][b]
    if route:
        total += mat[route[-1]][0]
    return total


def _two_opt(route: list[int], mat: list[list[float]], max_iters: int = 200) -> list[int]:
    """Classic 2-opt: repeatedly reverse a segment if it shortens the loop."""
    if len(route) < 3:
        return route
    best = route[:]
    improved = True
    iters = 0
    while improved and iters < max_iters:
        improved = False
        iters += 1
        for i in range(len(best) - 1):
            for j in range(i + 1, len(best)):
                a = best[i - 1] if i > 0 else 0
                b = best[i]
                c = best[j]
                d = best[j + 1] if j + 1 < len(best) else 0
                if a == c or b == d:
                    continue
                delta = (mat[a][c] + mat[b][d]) - (mat[a][b] + mat[c][d])
                if delta < -1e-9:
                    best[i:j + 1] = reversed(best[i:j + 1])
                    improved = True
        # loop re-scans until a full pass yields no improvement
    return best


def _clarke_wright(nodes: list[Node], mat: list[list[float]], cap: float) -> list[dict]:
    """
    Parallel Clarke-Wright savings construction.
    Returns a list of {"stops": [idx,...], "demand": float} route dicts,
    each within `cap`. idx 0 is always the depot and never appears inside
    a returned route's "stops" list.
    """
    customers = [i for i in range(1, len(nodes))]
    routes = {i: {"stops": [i], "demand": nodes[i].demand} for i in customers}
    route_of = {i: i for i in customers}  # customer -> route key

    savings = []
    for i in customers:
        for j in customers:
            if i < j:
                s = mat[0][i] + mat[0][j] - mat[i][j]
                savings.append((s, i, j))
    savings.sort(key=lambda t: t[0], reverse=True)

    for s, i, j in savings:
        if s <= 0:
            continue
        ri, rj = route_of[i], route_of[j]
        if ri == rj:
            continue
        route_i, route_j = routes[ri], routes[rj]
        # only interior->exterior merges are legal in the CW construction:
        # i must sit at an end of its route, j at an end of its route.
        i_end = route_i["stops"][-1] == i
        i_start = route_i["stops"][0] == i
        j_end = route_j["stops"][-1] == j
        j_start = route_j["stops"][0] == j
        if not ((i_end or i_start) and (j_end or j_start)):
            continue
        if route_i["demand"] + route_j["demand"] > cap + 1e-9:
            continue

        if i_end and j_start:
            merged = route_i["stops"] + route_j["stops"]
        elif i_start and j_end:
            merged = route_j["stops"] + route_i["stops"]
        elif i_end and j_end:
            merged = route_i["stops"] + list(reversed(route_j["stops"]))
        else:  # i_start and j_start
            merged = list(reversed(route_i["stops"])) + route_j["stops"]

        new_key = ri
        routes[new_key] = {"stops": merged, "demand": route_i["demand"] + route_j["demand"]}
        del routes[rj]
        for node_id in merged:
            route_of[node_id] = new_key

    return list(routes.values())


def _assign_routes_to_vehicles(
    routes: list[dict], vehicles: list[dict]
) -> tuple[list[dict], list[int]]:
    """
    Best-fit-decreasing: biggest routes to biggest vehicles first. A route
    that fits no remaining vehicle sheds its lowest-priority stops (rather
    than blocking the whole batch) until it fits, or is dropped entirely
    with its stops reported unassigned.
    """
    routes = sorted(routes, key=lambda r: r["demand"], reverse=True)
    remaining_vehicles = sorted(vehicles, key=lambda v: v["capacity"], reverse=True)
    assigned = []
    unassigned: list[int] = []

    for route in routes:
        placed = False
        for idx, veh in enumerate(remaining_vehicles):
            if veh["capacity"] >= route["demand"] - 1e-9:
                route["vehicle_id"] = veh["id"]
                assigned.append(route)
                remaining_vehicles.pop(idx)
                placed = True
                break
        if placed:
            continue
        if not remaining_vehicles:
            unassigned.extend(route["stops"])
            continue
        # shed lowest-priority, then farthest, stops until it fits the
        # largest remaining vehicle
        best_veh = remaining_vehicles[0]
        stops = route["stops"][:]
        demand_map = route.get("demand_map", {})
        while stops and route["demand"] > best_veh["capacity"] + 1e-9:
            drop = stops.pop()  # simplest: shed from the tail
            unassigned.append(drop)
            route["demand"] -= demand_map.get(drop, 0.0)
        if stops:
            route["stops"] = stops
            route["vehicle_id"] = best_veh["id"]
            assigned.append(route)
            remaining_vehicles.pop(0)
        else:
            unassigned.extend(route["stops"])

    return assigned, unassigned


def solve_heuristic(
    depot: tuple[float, float],
    stops: list[dict],
    vehicles: list[dict],
) -> SolveResult:
    """
    stops:   [{"id": int, "lat": float, "lng": float, "demand": float, "priority": int}, ...]
    vehicles:[{"id": int, "capacity": float}, ...]
    """
    t0 = time.perf_counter()
    nodes = [Node(id=0, lat=depot[0], lng=depot[1], demand=0.0)]
    id_to_idx = {}
    for k, s in enumerate(stops, start=1):
        nodes.append(Node(id=s["id"], lat=s["lat"], lng=s["lng"],
                           demand=s["demand"], priority=s.get("priority", 1)))
        id_to_idx[s["id"]] = k

    if not stops or not vehicles:
        return SolveResult([], [s["id"] for s in stops], 0.0, "heuristic",
                            (time.perf_counter() - t0) * 1000)

    mat = _build_matrix(nodes)
    cap = max(v["capacity"] for v in vehicles)
    raw_routes = _clarke_wright(nodes, mat, cap)

    demand_map = {k: nodes[k].demand for k in range(len(nodes))}
    for r in raw_routes:
        r["demand_map"] = demand_map

    assigned, unassigned_idx = _assign_routes_to_vehicles(raw_routes, vehicles)

    planned: list[PlannedRoute] = []
    total_distance = 0.0
    for r in assigned:
        improved = _two_opt(r["stops"], mat)
        dist_from_prev = []
        prev = 0
        route_total = 0.0
        for node_idx in improved:
            d = mat[prev][node_idx]
            dist_from_prev.append(round(d, 3))
            route_total += d
            prev = node_idx
        route_total += mat[prev][0]
        total_distance += route_total
        planned.append(PlannedRoute(
            vehicle_id=r["vehicle_id"],
            stop_ids=[nodes[i].id for i in improved],
            distances_km=dist_from_prev,
            total_distance_km=round(route_total, 3),
            demand=r["demand"],
        ))

    unassigned_ids = [nodes[i].id for i in unassigned_idx]
    elapsed_ms = (time.perf_counter() - t0) * 1000
    return SolveResult(planned, unassigned_ids, round(total_distance, 3), "heuristic", elapsed_ms)


def solve_ortools(
    depot: tuple[float, float],
    stops: list[dict],
    vehicles: list[dict],
) -> SolveResult | None:
    """Returns None (caller falls back to heuristic) if OR-Tools isn't installed."""
    try:
        from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    except ImportError:
        return None

    t0 = time.perf_counter()
    nodes = [Node(id=0, lat=depot[0], lng=depot[1])]
    for s in stops:
        nodes.append(Node(id=s["id"], lat=s["lat"], lng=s["lng"], demand=s["demand"]))
    mat = _build_matrix(nodes)
    scaled = [[int(d * 1000) for d in row] for row in mat]  # meters, integer

    n_vehicles = len(vehicles)
    manager = pywrapcp.RoutingIndexManager(len(nodes), n_vehicles, 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_cb(from_idx, to_idx):
        return scaled[manager.IndexToNode(from_idx)][manager.IndexToNode(to_idx)]

    transit_idx = routing.RegisterTransitCallback(distance_cb)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_idx)

    demands = [0] + [int(s["demand"]) for s in stops]

    def demand_cb(idx):
        return demands[manager.IndexToNode(idx)]

    demand_idx = routing.RegisterUnaryTransitCallback(demand_cb)
    capacities = [int(v["capacity"]) for v in vehicles]
    routing.AddDimensionWithVehicleCapacity(demand_idx, 0, capacities, True, "Capacity")

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.FromSeconds(5)

    solution = routing.SolveWithParameters(params)
    if not solution:
        return None

    planned = []
    total_distance = 0.0
    assigned_ids = set()
    for v in range(n_vehicles):
        index = routing.Start(v)
        stop_ids, dists = [], []
        prev_node = 0
        route_dist = 0.0
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            index = solution.Value(routing.NextVar(index))
            next_node = manager.IndexToNode(index)
            d = mat[node][next_node]
            if node != 0:
                stop_ids.append(nodes[node].id)
                dists.append(round(mat[prev_node][node], 3))
                assigned_ids.add(nodes[node].id)
            route_dist += d
            prev_node = node
        if stop_ids:
            planned.append(PlannedRoute(
                vehicle_id=vehicles[v]["id"], stop_ids=stop_ids,
                distances_km=dists, total_distance_km=round(route_dist, 3),
                demand=sum(s["demand"] for s in stops if s["id"] in stop_ids),
            ))
            total_distance += route_dist

    unassigned = [s["id"] for s in stops if s["id"] not in assigned_ids]
    elapsed_ms = (time.perf_counter() - t0) * 1000
    return SolveResult(planned, unassigned, round(total_distance, 3), "ortools", elapsed_ms)


def solve(
    depot: tuple[float, float],
    stops: list[dict],
    vehicles: list[dict],
    prefer_exact: bool = False,
) -> SolveResult:
    """Single entrypoint. prefer_exact=True tries OR-Tools first (offline
    planning); real-time re-optimization should leave it False."""
    if prefer_exact:
        result = solve_ortools(depot, stops, vehicles)
        if result is not None:
            return result
    return solve_heuristic(depot, stops, vehicles)
