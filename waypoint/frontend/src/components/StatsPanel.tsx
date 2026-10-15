import type { FleetSummary } from "../types";

interface Props {
  summary: FleetSummary | null;
}

function Stat({ value, label, accent }: { value: string; label: string; accent?: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className={`font-mono text-2xl leading-none ${accent ?? "text-ink"}`}>{value}</span>
      <span className="text-xs text-ink-muted">{label}</span>
    </div>
  );
}

export default function StatsPanel({ summary }: Props) {
  if (!summary) return null;
  return (
    <div className="grid grid-cols-3 gap-x-6 gap-y-4">
      <Stat
        value={`${summary.vehicles_active}/${summary.vehicles_total}`}
        label="vehicles en route"
        accent="text-route"
      />
      <Stat value={String(summary.stops_pending)} label="stops in plan" />
      <Stat value={String(summary.stops_completed)} label="stops completed" accent="text-success" />
      <Stat value={`${summary.total_distance_km.toFixed(1)} km`} label="total route distance" />
      <Stat value={`${summary.on_time_pct.toFixed(0)}%`} label="on-time estimate" />
      <Stat value={`${summary.avg_delay_min.toFixed(0)} min`} label="avg delay" />
    </div>
  );
}
