import { AnimatePresence, motion } from "framer-motion";
import type { DisruptionEvent } from "../types";

const TYPE_COLOR: Record<string, string> = {
  traffic: "border-alert",
  breakdown: "border-danger",
  urgent_order: "border-route",
  closed_road: "border-alert",
};

export default function EventFeed({ events }: { events: DisruptionEvent[] }) {
  return (
    <div>
      <h2 className="text-sm font-medium text-ink tracking-tight mb-2">Event log</h2>
      <div className="flex flex-col gap-1.5 max-h-48 overflow-y-auto pr-1">
        <AnimatePresence initial={false}>
          {events.length === 0 && (
            <p className="text-xs text-ink-muted">No disruptions yet — the plan is running clean.</p>
          )}
          {events.map((e) => (
            <motion.div
              key={e.id}
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              className={`border-l-2 ${TYPE_COLOR[e.type] ?? "border-chart-line"} bg-chart-raised/60 pl-2.5 py-1.5 rounded-sm`}
            >
              <p className="text-xs text-ink">{e.description}</p>
              <p className="text-[10px] text-ink-muted font-mono mt-0.5">
                {new Date(e.created_at).toLocaleTimeString()}
              </p>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
