from __future__ import annotations

from routing_opt.domain import Location
from routing_opt.matrices import haversine_matrices, load_matrices, save_matrices, unreachable_pairs


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
