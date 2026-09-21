from __future__ import annotations

import json
import math
import ssl
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import certifi

from .domain import Location, TravelMatrices


def haversine_matrices(
    locations: Iterable[Location],
    *,
    speed_kmh: float = 28.0,
    road_factor: float = 1.3,
    profile: str = "driving-approximation",
) -> TravelMatrices:
    """Create deterministic debug matrices; not a replacement for road routing."""

    items = tuple(locations)
    if speed_kmh <= 0 or road_factor <= 0:
        raise ValueError("speed_kmh and road_factor must be positive")
    missing = [location.id for location in items if not location.has_coordinates]
    if missing:
        raise ValueError(f"Coordinates are missing for {len(missing)} locations: {missing[:5]}")
    distances: list[tuple[float, ...]] = []
    times: list[tuple[int, ...]] = []
    for source in items:
        distance_row = []
        time_row = []
        for target in items:
            straight = _haversine_km(
                source.latitude or 0.0,
                source.longitude or 0.0,
                target.latitude or 0.0,
                target.longitude or 0.0,
            )
            distance = straight * road_factor
            minutes = 0 if source.id == target.id else max(1, math.ceil(distance / speed_kmh * 60))
            distance_row.append(round(distance, 6))
            time_row.append(minutes)
        distances.append(tuple(distance_row))
        times.append(tuple(time_row))
    return TravelMatrices(
        location_ids=tuple(location.id for location in items),
        time_minutes=tuple(times),
        distance_km=tuple(distances),
        provider="haversine",
        profile=profile,
        metadata={"speed_kmh": speed_kmh, "road_factor": road_factor},
    )


class OsrmTableClient:
    """Provider client for OSRM's table endpoint with square-block batching."""

    def __init__(
        self,
        base_url: str,
        *,
        profile: str = "driving",
        max_locations_per_request: int = 100,
        timeout_seconds: float = 30.0,
        user_agent: str = "routing-opt-hackathon/0.1",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.profile = profile
        self.max_locations_per_request = max_locations_per_request
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent

    def build(self, locations: Iterable[Location]) -> TravelMatrices:
        items = tuple(locations)
        missing = [location.id for location in items if not location.has_coordinates]
        if missing:
            raise ValueError(f"Coordinates are missing for {len(missing)} locations")
        size = len(items)
        times: list[list[int | None]] = [[None] * size for _ in range(size)]
        distances: list[list[float | None]] = [[None] * size for _ in range(size)]
        block_size = max(1, self.max_locations_per_request // 2)
        for source_start in range(0, size, block_size):
            source_indices = list(range(source_start, min(size, source_start + block_size)))
            for destination_start in range(0, size, block_size):
                destination_indices = list(
                    range(destination_start, min(size, destination_start + block_size))
                )
                payload = self._request_block(items, source_indices, destination_indices)
                for row_offset, source_index in enumerate(source_indices):
                    for column_offset, destination_index in enumerate(destination_indices):
                        seconds = payload["durations"][row_offset][column_offset]
                        meters = payload["distances"][row_offset][column_offset]
                        duration_seconds = _finite_non_negative(seconds)
                        distance_meters = _finite_non_negative(meters)
                        # Public OSRM instances may encode an unreachable arc as
                        # null, NaN or infinity. All of them mean the same thing
                        # to the solvers: this directed leg cannot be used.
                        times[source_index][destination_index] = (
                            None
                            if duration_seconds is None
                            else math.ceil(duration_seconds / 60)
                        )
                        distances[source_index][destination_index] = (
                            None if distance_meters is None else distance_meters / 1000
                        )
        return TravelMatrices(
            location_ids=tuple(location.id for location in items),
            time_minutes=tuple(tuple(row) for row in times),
            distance_km=tuple(tuple(row) for row in distances),
            provider=self.base_url,
            profile=self.profile,
        )

    def _request_block(
        self,
        items: tuple[Location, ...],
        source_indices: list[int],
        destination_indices: list[int],
    ) -> dict[str, object]:
        combined = source_indices + destination_indices
        coordinates = ";".join(
            f"{items[index].longitude},{items[index].latitude}" for index in combined
        )
        params = urlencode(
            {
                "sources": ";".join(map(str, range(len(source_indices)))),
                "destinations": ";".join(map(str, range(len(source_indices), len(combined)))),
                "annotations": "duration,distance",
                "skip_waypoints": "true",
            }
        )
        url = f"{self.base_url}/table/v1/{self.profile}/{coordinates}?{params}"
        request = Request(url, headers={"User-Agent": self.user_agent})
        tls_context = ssl.create_default_context(cafile=certifi.where())
        with urlopen(
            request,
            timeout=self.timeout_seconds,
            context=tls_context,
        ) as response:
            payload = json.load(response)
        if payload.get("code") != "Ok":
            raise RuntimeError(f"OSRM table request failed: {payload.get('code')}")
        return payload


def save_matrices(matrices: TravelMatrices, path: str | Path) -> None:
    output = {
        "location_ids": matrices.location_ids,
        "time_minutes": matrices.time_minutes,
        "distance_km": matrices.distance_km,
        "provider": matrices.provider,
        "profile": matrices.profile,
        "metadata": dict(matrices.metadata),
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")


def load_matrices(path: str | Path) -> TravelMatrices:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return TravelMatrices(
        location_ids=tuple(payload["location_ids"]),
        time_minutes=tuple(tuple(row) for row in payload["time_minutes"]),
        distance_km=tuple(tuple(row) for row in payload["distance_km"]),
        provider=payload.get("provider", "unknown"),
        profile=payload.get("profile", "unknown"),
        metadata=payload.get("metadata", {}),
    )


def unreachable_pairs(matrices: TravelMatrices) -> tuple[tuple[str, str], ...]:
    result = []
    for row_index, source in enumerate(matrices.location_ids):
        for column_index, destination in enumerate(matrices.location_ids):
            if (
                matrices.time_minutes[row_index][column_index] is None
                or matrices.distance_km[row_index][column_index] is None
            ):
                result.append((source, destination))
    return tuple(result)


def _finite_non_negative(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0:
        return None
    return number


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_km = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    value = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * earth_radius_km * math.asin(math.sqrt(value))
