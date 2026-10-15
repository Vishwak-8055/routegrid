# Waypoint — Real-Time Fleet Routing & Dispatch Engine

A capacitated vehicle routing system for a delivery/service fleet: assigns
and sequences stops across vehicles, then **re-optimizes live** when
something changes -- a vehicle breaks down, traffic hits a leg, or an
urgent order lands mid-shift.

Framed as an FDE-style case study: the demo data models a mid-size fleet
operating out of Hitech City, Hyderabad, as if this were configured
on-site against one operator's actual depot, vehicles, and stop list --
not shipped as a generic multi-tenant SaaS product.

## Why this project

Most "AI portfolio" projects are a chatbot wrapped around an LLM. This one
isn't -- it's systems work: a real routing algorithm, a real re-optimization
loop reacting to real-time events, and a real trade-off between solve
speed and solution quality, the same trade-off actual dispatch software
ships with.

## Architecture

```
backend/   FastAPI + SQLAlchemy + SQLite (Postgres-ready)
  app/solver.py        Clarke-Wright savings + 2-opt heuristic (primary,
                        real-time path) and an OR-Tools CP-SAT backend
                        (optional, near-optimal offline path)
  app/simulation.py    disruption injection + the re-optimization loop
                        it triggers
  app/eta.py           physics-based ETA baseline + a learned
                        gradient-boosted correction term
  app/models.py        Vehicle / Stop / Route / RouteStop / DisruptionEvent
  app/routers/          REST endpoints (fleet reads, dispatch actions)
  app/main.py           app wiring, WebSocket endpoint, startup seeding

frontend/  React + TypeScript + Vite + Tailwind + Leaflet + Framer Motion
  live map, dispatch controls, stats strip, and an event feed, all driven
  by REST reads plus a WebSocket subscription -- trigger a disruption and
  watch the map redraw within one round trip
```

## Why two solvers

Real dispatch systems don't use one algorithm for everything: a fast
heuristic answers "something just broke, replan now," while a slower,
closer-to-optimal solver answers "tonight's batch planning run." Waypoint
mirrors that split instead of picking one and hand-waving the other:

| | Heuristic (Clarke-Wright + 2-opt) | OR-Tools (CP-SAT) |
|---|---|---|
| Seeded demo (17 stops / 5 vehicles) | 0.57ms | ~5s (configurable budget) |
| 150 stops / 20 vehicles | 23ms | not benchmarked here |
| 300 stops / 35 vehicles | 99ms | not benchmarked here |
| Used for | live re-optimization | offline/nightly planning |

Numbers above are measured on this codebase, not estimated.

## Honest limitations

Worth stating plainly rather than glossing over:

- **Vehicle-assignment can leave capacity on the table.** The heuristic's
  route-to-vehicle matching is greedy best-fit-decreasing. In one 300-stop
  / 35-vehicle benchmark it left ~14% of stops unassigned even though the
  fleet sat at only 73% total capacity utilization. OR-Tools closes this
  gap by solving routing and capacity jointly; a production heuristic path
  would want a real bin-packing pass rather than my tail-shedding
  fallback.
- **The ETA "learning" is a pattern demonstration, not a real model.** It's
  a gradient-boosted regressor trained on synthetic data (see
  `app/eta.py`) to show a physics-baseline-plus-learned-correction
  architecture -- it is not fit to real historical trip data and
  shouldn't be read as production-accurate.
- **Single depot, soft time windows.** Multi-depot VRP and hard SLA
  enforcement (rejecting an assignment that violates a window, rather than
  just recording ETA) aren't implemented.
- **WebSocket state is in-process.** Fine for one instance; a
  multi-instance deployment needs Redis pub/sub (or similar) behind the
  same `broadcast()` call in `app/ws_manager.py`.
- **No auth or multi-tenancy.** One shared fleet, no login.
- **Docker Compose is provided but not build-tested in this environment**
  (no registry access here to pull base images) -- the underlying
  services were verified directly: the backend via `uvicorn` + live
  `curl`/WebSocket checks, the frontend via a clean `npm run build`.

## Running it

### Docker
```bash
docker compose up --build
```
Frontend: http://localhost:5173 · API: http://localhost:8000

### Manual
```bash
# backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# frontend, in a second terminal
cd frontend
npm install
npm run dev
```
Visit http://localhost:5173 -- the Vite dev server proxies `/api` and `/ws`
to the backend on :8000.

On first run the backend seeds a demo fleet (5 vehicles, 16 stops around
Hyderabad) and produces an initial plan automatically.

## API surface

| Endpoint | Purpose |
|---|---|
| `GET /api/vehicles` `/api/stops` `/api/routes` `/api/summary` `/api/depot` | Fleet state reads |
| `POST /api/stops` | Add a new stop |
| `POST /api/optimize?prefer_exact=<bool>` | Re-solve now (heuristic or OR-Tools) |
| `POST /api/disruptions/simulate` | Trigger a disruption: `traffic` \| `breakdown` \| `urgent_order` \| `closed_road` |
| `GET /api/disruptions` | Recent disruption log |
| `WS /ws` | `plan_updated` and `disruption` events, pushed live |

## Tests

```bash
cd backend && python -m pytest tests/ -v
```
7 tests: distance-matrix correctness, full stop coverage (nothing silently
dropped), capacity constraints, one-vehicle-per-route invariants, and a
solve-time ceiling.

## Suggested resume line

> Built Waypoint, a real-time fleet dispatch engine with a from-scratch
> capacitated VRP solver (Clarke-Wright + 2-opt) resolving 150-stop
> instances in 23ms, plus a pluggable OR-Tools exact-solver backend;
> disruption simulation drives live WebSocket-based re-optimization
> end-to-end.

Adjust freely -- swap in whatever numbers you want to lead with.
