from __future__ import annotations

import html
import json
from pathlib import Path

from .benchmark import BenchmarkRecord
from .domain import Problem, Solution
from .route_geometry import RouteGeometryProvider

_COLORS = (
    "#e6194b",
    "#3cb44b",
    "#4363d8",
    "#f58231",
    "#911eb4",
    "#46f0f0",
    "#f032e6",
    "#bcf60c",
    "#fabebe",
    "#008080",
    "#e6beff",
    "#9a6324",
    "#800000",
    "#aaffc3",
    "#000075",
    "#808000",
)


def save_route_map(
    problem: Problem,
    solution: Solution,
    path: str | Path,
    *,
    geometry_provider: RouteGeometryProvider | None = None,
) -> None:
    """Write a Leaflet HTML map, optionally following provider road geometry."""

    locations = problem.locations_by_id
    jobs = problem.jobs_by_id
    payload_routes = []
    for route_index, route in enumerate(solution.routes):
        if not route.stops:
            continue
        engineer = problem.engineers_by_id[route.engineer_id]
        start = locations[engineer.start_location_id]
        if not start.has_coordinates:
            raise ValueError(f"Missing coordinates for {start.id}")
        points = [[start.latitude, start.longitude]]
        stops = []
        for stop in route.stops:
            location = locations[jobs[stop.job_id].location_id]
            if not location.has_coordinates:
                raise ValueError(f"Missing coordinates for {location.id}")
            points.append([location.latitude, location.longitude])
            stops.append(
                {
                    "lat": location.latitude,
                    "lon": location.longitude,
                    "popup": (
                        f"{stop.sequence}. {stop.job_id}<br>"
                        f"Прибытие: {_clock(stop.arrival_minutes)}<br>"
                        f"Начало: {_clock(stop.service_start_minutes)}"
                    ),
                }
            )
        display_points = (
            geometry_provider.route(
                [(float(latitude), float(longitude)) for latitude, longitude in points]
            )
            if geometry_provider is not None
            else tuple((float(latitude), float(longitude)) for latitude, longitude in points)
        )
        payload_routes.append(
            {
                "engineer": route.engineer_id,
                "color": _COLORS[route_index % len(_COLORS)],
                "points": display_points,
                "stops": stops,
            }
        )
    unassigned = []
    for item in solution.unassigned:
        job = jobs[item.job_id]
        location = locations[job.location_id]
        if location.has_coordinates:
            unassigned.append(
                {
                    "lat": location.latitude,
                    "lon": location.longitude,
                    "popup": f"Не назначена: {job.id}<br>{html.escape(item.message)}",
                }
            )
    all_points = [point for route in payload_routes for point in route["points"]]
    center = all_points[0] if all_points else [55.751244, 37.618423]
    document = f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><title>Маршруты</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<link rel="stylesheet" href="https://unpkg.com/maplibre-gl@5/dist/maplibre-gl.css">
<style>html,body,#map{{height:100%;margin:0}} .metrics{{position:absolute;z-index:1000;right:12px;top:12px;background:white;padding:10px;border-radius:6px}}</style>
</head><body><div id="map"></div>
<div class="metrics">Выполнено: {solution.metrics.completed_jobs}<br>Не назначено: {solution.metrics.unassigned_jobs}<br>Инженеров: {solution.metrics.active_engineers}<br>Пробег: {solution.metrics.total_distance_km:.1f} км</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/maplibre-gl@5/dist/maplibre-gl.js"></script>
<script src="https://unpkg.com/@maplibre/maplibre-gl-leaflet/leaflet-maplibre-gl.js"></script><script>
const map=L.map('map').setView({json.dumps(center)},11);
map.attributionControl.setPrefix(false);
try {{
  L.maplibreGL({{style:'https://tiles.openfreemap.org/styles/liberty'}}).addTo(map);
  map.attributionControl.addAttribution('OpenFreeMap &copy; OpenMapTiles Data from OpenStreetMap');
}} catch(error) {{ console.warn('Basemap unavailable; routes remain visible.', error); }}
const routes={json.dumps(payload_routes, ensure_ascii=False)};
routes.forEach(r=>{{L.polyline(r.points,{{color:r.color,weight:4}}).addTo(map).bindTooltip(r.engineer);r.stops.forEach(s=>L.circleMarker([s.lat,s.lon],{{radius:6,color:r.color,fillOpacity:1}}).addTo(map).bindPopup(s.popup));}});
const unassigned={json.dumps(unassigned, ensure_ascii=False)};
unassigned.forEach(s=>L.circleMarker([s.lat,s.lon],{{radius:7,color:'#111',fillColor:'#ff0',fillOpacity:1}}).addTo(map).bindPopup(s.popup));
if(routes.length) map.fitBounds(routes.flatMap(r=>r.points));
</script></body></html>"""
    _write(path, document)


def save_gantt(solution: Solution, path: str | Path) -> None:
    active = [route for route in solution.routes if route.stops]
    start = min((route.departure_minutes for route in active), default=600)
    end = max((route.finish_minutes for route in active), default=1320)
    span = max(1, end - start)
    rows = []
    for route_index, route in enumerate(active):
        bars = []
        for stop in route.stops:
            left = (stop.service_start_minutes - start) / span * 100
            width = (stop.service_end_minutes - stop.service_start_minutes) / span * 100
            bars.append(
                f'<div class="bar" style="left:{left:.3f}%;width:{max(width, 0.4):.3f}%;background:{_COLORS[route_index % len(_COLORS)]}" title="{html.escape(stop.job_id)} {_clock(stop.service_start_minutes)}–{_clock(stop.service_end_minutes)}"></div>'
            )
        rows.append(
            f'<div class="label">{html.escape(route.engineer_id)}</div><div class="track">{"".join(bars)}</div>'
        )
    document = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Расписание</title>
<style>body{{font-family:system-ui;margin:24px}}.grid{{display:grid;grid-template-columns:180px 1fr;gap:8px;align-items:center}}.track{{height:28px;background:#eee;position:relative}}.bar{{position:absolute;height:100%;border-right:1px solid white}}.axis{{display:flex;justify-content:space-between}}</style></head><body><h1>Расписание инженеров</h1><div class="axis"><span>{_clock(start)}</span><span>{_clock(end)}</span></div><div class="grid">{"".join(rows)}</div></body></html>"""
    _write(path, document)


def save_benchmark_html(records: list[BenchmarkRecord], path: str | Path) -> None:
    valid = [record for record in records if record.valid]
    max_completed = max((record.completed_jobs for record in valid), default=1)
    rows = []
    for record in records:
        width = record.completed_jobs / max_completed * 100
        rows.append(
            f"<tr><td>{html.escape(record.solver)}</td><td>{record.seed}</td><td>{'да' if record.valid else 'нет'}</td><td>{record.completed_jobs}</td><td>{record.unassigned_jobs}</td><td>{record.active_engineers}</td><td>{record.total_distance_km:.2f}</td><td>{record.runtime_seconds:.3f}</td><td><div style='width:{width:.1f}%;background:#4363d8;height:14px'></div></td></tr>"
        )
    document = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Benchmark</title><style>body{{font-family:system-ui;margin:24px}}table{{border-collapse:collapse;width:100%}}th,td{{padding:7px;border:1px solid #ccc;text-align:right}}th:first-child,td:first-child{{text-align:left}}</style></head><body><h1>Сравнение алгоритмов</h1><table><thead><tr><th>Solver</th><th>Seed</th><th>Валиден</th><th>Выполнено</th><th>Не назначено</th><th>Инженеров</th><th>Км</th><th>Сек.</th><th>Выполнение</th></tr></thead><tbody>{"".join(rows)}</tbody></table></body></html>"""
    _write(path, document)


def _clock(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _write(path: str | Path, content: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
