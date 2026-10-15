import { useEffect, useRef, useState } from "react";

type WSMessage =
  | { event: "plan_updated"; data: unknown }
  | { event: "disruption"; data: unknown };

interface Options {
  onPlanUpdated?: (data: unknown) => void;
  onDisruption?: (data: unknown) => void;
}

export function useWaypointSocket({ onPlanUpdated, onDisruption }: Options) {
  const [connected, setConnected] = useState(false);
  const handlersRef = useRef({ onPlanUpdated, onDisruption });
  handlersRef.current = { onPlanUpdated, onDisruption };

  useEffect(() => {
    let socket: WebSocket | null = null;
    let retryTimer: ReturnType<typeof setTimeout>;
    let cancelled = false;

    function connect() {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      socket = new WebSocket(`${protocol}//${window.location.host}/ws`);

      socket.onopen = () => setConnected(true);
      socket.onclose = () => {
        setConnected(false);
        if (!cancelled) retryTimer = setTimeout(connect, 2000);
      };
      socket.onerror = () => socket?.close();
      socket.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data) as WSMessage;
          if (msg.event === "plan_updated") handlersRef.current.onPlanUpdated?.(msg.data);
          if (msg.event === "disruption") handlersRef.current.onDisruption?.(msg.data);
        } catch {
          // ignore malformed frames
        }
      };
    }

    connect();
    return () => {
      cancelled = true;
      clearTimeout(retryTimer);
      socket?.close();
    };
  }, []);

  return { connected };
}
