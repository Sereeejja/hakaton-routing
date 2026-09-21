from __future__ import annotations

from routing_opt.domain import Location
from routing_opt.matrices import (
    OsrmTableClient,
    haversine_matrices,
    load_matrices,
    save_matrices,
    unreachable_pairs,
)


def test_haversine_matrix_roundtrip(tmp_path):
    locations = (
        Location("a", latitude=55.75, longitude=37.61),
        Location("b", latitude=55.76, longitude=37.62),
    )
    matrices = haversine_matrices(locations)
    assert matrices.travel_minutes("a", "a") == 0
    assert matrices.travel_minutes("a", "b") > 0
    assert not unreachable_pairs(matrices)
    path = tmp_path / "matrix.json"
    save_matrices(matrices, path)
    restored = load_matrices(path)
    assert restored == matrices


def test_osrm_non_finite_and_negative_arcs_become_unreachable(monkeypatch):
    locations = (
        Location("a", latitude=55.75, longitude=37.61),
        Location("b", latitude=55.76, longitude=37.62),
    )
    client = OsrmTableClient("https://router.invalid", max_locations_per_request=100)

    def fake_request(_items, _sources, _destinations):
        return {
            "durations": [[0, "NaN"], [float("inf"), -1]],
            "distances": [[0, float("nan")], ["Infinity", -20]],
        }

    monkeypatch.setattr(client, "_request_block", fake_request)
    matrices = client.build(locations)

    assert matrices.time_minutes == ((0, None), (None, None))
    assert matrices.distance_km == ((0.0, None), (None, None))
    assert set(unreachable_pairs(matrices)) == {("a", "b"), ("b", "a"), ("b", "b")}


def test_osrm_finite_values_are_converted_to_minutes_and_kilometres(monkeypatch):
    locations = (
        Location("a", latitude=55.75, longitude=37.61),
        Location("b", latitude=55.76, longitude=37.62),
    )
    client = OsrmTableClient("https://router.invalid", max_locations_per_request=100)
    monkeypatch.setattr(
        client,
        "_request_block",
        lambda _items, _sources, _destinations: {
            "durations": [[0, 61], [119, 0]],
            "distances": [[0, 1250], [1400, 0]],
        },
    )

    matrices = client.build(locations)

    assert matrices.time_minutes == ((0, 2), (2, 0))
    assert matrices.distance_km == ((0.0, 1.25), (1.4, 0.0))
