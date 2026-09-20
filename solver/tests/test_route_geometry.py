from __future__ import annotations

import json

from routing_opt.route_geometry import CachedRouteGeometry, OsrmRouteGeometryClient
from routing_opt.solvers.greedy import GreedySolver
from routing_opt.visualization import save_route_map


class FakeProvider:
    def __init__(self) -> None:
        self.calls = 0

    def route(self, coordinates):
        self.calls += 1
        first, last = coordinates[0], coordinates[-1]
        midpoint = ((first[0] + last[0]) / 2, (first[1] + last[1]) / 2)
        return first, midpoint, last


def test_geometry_cache_avoids_repeated_provider_calls(tmp_path):
    provider = FakeProvider()
    cache = CachedRouteGeometry(provider, tmp_path / "routes.json")
    points = [(55.75, 37.61), (55.76, 37.62)]
    first = cache.route(points)
    second = cache.route(points)
    assert first == second
    assert provider.calls == 1
    assert json.loads((tmp_path / "routes.json").read_text(encoding="utf-8"))


def test_osrm_client_stitches_overlapping_chunks(monkeypatch):
    client = OsrmRouteGeometryClient("https://example.test", max_coordinates_per_request=3)
    calls = []

    def fake_request(_client, points):
        calls.append(points)
        return points

    monkeypatch.setattr(OsrmRouteGeometryClient, "_request", fake_request)
    points = [(55.0 + index / 100, 37.0 + index / 100) for index in range(5)]
    assert client.route(points) == tuple(points)
    assert calls == [points[:3], points[2:5]]


def test_map_uses_openfreemap_instead_of_blocked_osm_tiles(small_problem, tmp_path):
    solution = GreedySolver().solve(small_problem)
    target = tmp_path / "map.html"
    save_route_map(small_problem, solution, target)
    document = target.read_text(encoding="utf-8")
    assert "tiles.openfreemap.org/styles/liberty" in document
    assert "tile.openstreetmap.org" not in document
    assert "map.attributionControl.setPrefix(false)" in document
