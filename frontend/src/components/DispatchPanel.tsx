import { useState } from "react";
import { motion } from "framer-motion";
import { api } from "../api";

interface Props {
  onAfterAction: () => void;
  onOptimize: (preferExact: boolean) => Promise<void>;
  lastSolver: string | null;
  lastSolveMs: number | null;
}

const DISRUPTIONS: { type: string; label: string; hint: string }[] = [
  { type: "traffic", label: "Traffic delay", hint: "Slows one vehicle's current leg" },
  { type: "breakdown", label: "Vehicle breakdown", hint: "Pulls a vehicle out, releases its stops" },
  { type: "urgent_order", label: "Urgent order", hint: "Drops a new high-priority stop" },
  { type: "closed_road", label: "Road closure", hint: "Fleet-wide delay until cleared" },
];

export default function DispatchPanel({ onAfterAction, onOptimize, lastSolver, lastSolveMs }: Props) {
  const [busy, setBusy] = useState<string | null>(null);

  async function run(key: string, fn: () => Promise<unknown>) {
    setBusy(key);
    try {
      await fn();
      onAfterAction();
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-sm font-medium text-ink tracking-tight mb-2">Re-optimize</h2>
        <div className="flex gap-2">
          <button
            onClick={() => run("fast", () => onOptimize(false))}
            disabled={busy !== null}
            className="flex-1 rounded-sm bg-route/90 hover:bg-route text-chart-bg font-medium text-sm py-2 transition-colors disabled:opacity-50"
          >
            {busy === "fast" ? "Solving…" : "Fast re-solve"}
          </button>
          <button
            onClick={() => run("exact", () => onOptimize(true))}
            disabled={busy !== null}
            className="flex-1 rounded-sm border border-chart-line hover:border-ink-muted text-ink text-sm py-2 transition-colors disabled:opacity-50"
          >
            {busy === "exact" ? "Solving…" : "Exact solve"}
          </button>
        </div>
        {lastSolver && (
          <p className="text-xs text-ink-muted mt-1.5 font-mono">
            last run: {lastSolver} in {lastSolveMs?.toFixed(0)}ms
          </p>
        )}
      </div>

      <div>
        <h2 className="text-sm font-medium text-ink tracking-tight mb-2">Simulate a disruption</h2>
        <div className="grid grid-cols-2 gap-2">
          {DISRUPTIONS.map((d) => (
            <motion.button
              key={d.type}
              whileTap={{ scale: 0.97 }}
              onClick={() => run(d.type, () => api.simulateDisruption(d.type))}
              disabled={busy !== null}
              title={d.hint}
              className="rounded-sm bg-chart-raised hover:bg-chart-line border border-chart-line text-left px-3 py-2 text-sm text-ink transition-colors disabled:opacity-50"
            >
              {busy === d.type ? "…" : d.label}
            </motion.button>
          ))}
        </div>
      </div>
    </div>
  );
}
