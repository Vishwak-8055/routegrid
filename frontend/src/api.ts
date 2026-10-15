const BASE = "/api";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const api = {
  vehicles: () => fetch(`${BASE}/vehicles`).then(json),
  stops: () => fetch(`${BASE}/stops`).then(json),
  routes: () => fetch(`${BASE}/routes`).then(json),
  summary: () => fetch(`${BASE}/summary`).then(json),
  depot: () => fetch(`${BASE}/depot`).then(json),
  disruptions: () => fetch(`${BASE}/disruptions`).then(json),
  optimize: (preferExact = false) =>
    fetch(`${BASE}/optimize?prefer_exact=${preferExact}`, { method: "POST" }).then(json),
  simulateDisruption: (type?: string) =>
    fetch(`${BASE}/disruptions/simulate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type: type ?? null }),
    }).then(json),
};
