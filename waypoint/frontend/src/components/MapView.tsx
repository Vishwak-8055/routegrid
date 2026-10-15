import { MapContainer, TileLayer, Marker, Polyline, Popup } from "react-leaflet";
import L from "leaflet";
import type { Vehicle, Route, Depot } from "../types";

const ROUTE_PALETTE = ["#4FD1C5", "#F0A857", "#9F8FEF", "#6FCF97", "#E8646F", "#5EC8D8"];

function dotIcon(color: string, size = 12, ring = false) {
  return L.divIcon({
    className: "",
    html: `<div style="
      width:${size}px;height:${size}px;border-radius:50%;
      background:${color};
      box-shadow:0 0 0 2px #0A1628${ring ? `, 0 0 0 4px ${color}55` : ""};
    "></div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

function depotIcon() {
  return L.divIcon({
    className: "",
    html: `<div style="
      width:16px;height:16px;
      background:#E8EEF5; transform:rotate(45deg);
      box-shadow:0 0 0 2px #0A1628;
    "></div>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8],
  });
}

const STATUS_COLOR: Record<string, string> = {
  idle: "#7C93AD",
  en_route: "#4FD1C5",
  disrupted: "#E8646F",
  returning: "#F0A857",
};

interface Props {
  depot: Depot | null;
  vehicles: Vehicle[];
  routes: Route[];
}

export default function MapView({ depot, vehicles, routes }: Props) {
  const center: [number, number] = depot ? [depot.lat, depot.lng] : [17.4239, 78.4738];

  return (
    <MapContainer
      center={center}
      zoom={12}
      className="h-full w-full"
      zoomControl={false}
      attributionControl={false}
    >
      <TileLayer url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png" />

      {depot && (
        <Marker position={[depot.lat, depot.lng]} icon={depotIcon()}>
          <Popup>{depot.name}</Popup>
        </Marker>
      )}

      {routes.map((route, i) => {
        const color = ROUTE_PALETTE[i % ROUTE_PALETTE.length];
        const positions: [number, number][] = [
          depot ? [depot.lat, depot.lng] : [0, 0],
          ...route.stops
            .slice()
            .sort((a, b) => a.sequence - b.sequence)
            .map((rs) => [rs.stop.lat, rs.stop.lng] as [number, number]),
        ];
        return (
          <div key={route.id}>
            <Polyline
              positions={positions}
              pathOptions={{ color, weight: 2.5, opacity: 0.8, dashArray: "1 8" }}
            />
            {route.stops.map((rs) => (
              <Marker
                key={rs.stop.id}
                position={[rs.stop.lat, rs.stop.lng]}
                icon={dotIcon(color, rs.stop.priority > 1 ? 11 : 8, rs.stop.priority > 1)}
              >
                <Popup>
                  <div className="font-sans text-sm">
                    <div className="font-semibold">{rs.stop.label}</div>
                    <div>Stop #{rs.sequence + 1} on this route</div>
                    <div>ETA: {Math.round(rs.eta_min)} min</div>
                    {rs.stop.priority > 1 && <div className="text-amber-600">Urgent</div>}
                  </div>
                </Popup>
              </Marker>
            ))}
          </div>
        );
      })}

      {vehicles.map((v) => (
        <Marker key={v.id} position={[v.lat, v.lng]} icon={dotIcon(STATUS_COLOR[v.status], 14)}>
          <Popup>
            <div className="font-sans text-sm">
              <div className="font-semibold">{v.name}</div>
              <div>Status: {v.status.replace("_", " ")}</div>
              <div>Capacity {v.capacity}, {v.speed_kmh} km/h avg speed</div>
            </div>
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}
