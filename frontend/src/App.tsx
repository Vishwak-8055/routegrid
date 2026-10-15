import { useCallback, useEffect, useState } from "react";
import MapView from "./components/MapView";
import DispatchPanel from "./components/DispatchPanel";
import StatsPanel from "./components/StatsPanel";
import EventFeed from "./components/EventFeed";
import { useWaypointSocket } from "./hooks/useWebSocket";
import { api } from "./api";
import type { Vehicle, Route, FleetSummary, DisruptionEvent, Depot } from "./types";

export default function App() {
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [routes, setRoutes] = useState<Route[]>([]);
  const [summary, setSummary] = useState<FleetSummary | null>(null);
  const [depot, setDepot] = useState<Depot | null>(null);
  const [events, setEvents] = useState<DisruptionEvent[]>([]);
  const [lastSolver, setLastSolver] = useState<string | null>(null);
  const [lastSolveMs, setLastSolveMs] = useState<number | null>(null);

  const refreshAll = useCallback(async () => {
    const [v, r, s, d, ev] = await Promise.all([
      api.vehicles(),
      api.routes(),
      api.summary(),
      api.depot(),
      api.disruptions(),
    ]);
    setVehicles(v as Vehicle[]);
    setRoutes(r as Route[]);
    setSummary(s as FleetSummary);
    setDepot(d as Depot);
    setEvents(ev as DisruptionEvent[]);
  }, []);

  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  const { connected } = useWaypointSocket({
    onPlanUpdated: () => {
      refreshAll();
    },
    onDisruption: (data) => {
      setEvents((prev) => [data as DisruptionEvent, ...prev].slice(0, 30));
    },
  });

  async function handleOptimize(preferExact: boolean) {
    const t0 = performance.now();
    const result = (await api.optimize(preferExact)) as { solver_used: string; solve_time_ms: number };
    setLastSolver(result.solver_used);
    setLastSolveMs(result.solve_time_ms ?? performance.now() - t0);
    await refreshAll();
  }

  return (
    <div className="h-screen w-screen flex flex-col bg-chart-bg text-ink overflow-hidden">
      <header className="flex items-center justify-between px-5 py-3 border-b border-chart-line shrink-0">
        <div className="flex items-baseline gap-2.5">
          <h1 className="text-lg font-semibold tracking-tight">Waypoint</h1>
          <span className="text-xs text-ink-muted">real-time fleet dispatch</span>
        </div>
        <div className="flex items-center gap-2 text-xs text-ink-muted">
          <span
            className={`inline-block w-1.5 h-1.5 rounded-full ${connected ? "bg-success" : "bg-danger"}`}
          />
          {connected ? "live" : "reconnecting…"}
        </div>
      </header>

      <div className="flex flex-1 min-h-0">
        <main className="flex-1 relative">
          <MapView depot={depot} vehicles={vehicles} routes={routes} />
        </main>

        <aside className="w-[340px] shrink-0 border-l border-chart-line bg-chart-surface flex flex-col gap-6 p-5 overflow-y-auto">
          <StatsPanel summary={summary} />
          <div className="h-px bg-chart-line" />
          <DispatchPanel
            onAfterAction={refreshAll}
            onOptimize={handleOptimize}
            lastSolver={lastSolver}
            lastSolveMs={lastSolveMs}
          />
          <div className="h-px bg-chart-line" />
          <EventFeed events={events} />
        </aside>
      </div>
    </div>
  );
}
