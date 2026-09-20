from __future__ import annotations

import hashlib
import json
import ssl
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import certifi

Coordinate = tuple[float, float]  # latitude, longitude


class RouteGeometryProvider(Protocol):
    def route(self, coordinates: list[Coordinate]) -> tuple[Coordinate, ...]: ...


@dataclass(slots=True)
class OsrmRouteGeometryClient:
    """Fetch road-following route geometry from an explicitly selected OSRM server."""

    base_url: str
    profile: str = "driving"
    timeout_seconds: float = 30.0
    max_coordinates_per_request: int = 100
    user_agent: str = "routing-opt-hackathon/0.1"

    def route(self, coordinates: list[Coordinate]) -> tuple[Coordinate, ...]:
        if len(coordinates) < 2:
            return tuple(coordinates)
        if self.max_coordinates_per_request < 2:
            raise ValueError("max_coordinates_per_request must be at least 2")
        result: list[Coordinate] = []
        offset = 0
        while offset < len(coordinates) - 1:
            chunk = coordinates[offset : offset + self.max_coordinates_per_request]
            geometry = self._request(chunk)
            result.extend(geometry if not result else geometry[1:])
            offset += len(chunk) - 1
        return tuple(result)

    def _request(self, coordinates: list[Coordinate]) -> list[Coordinate]:
        encoded = ";".join(f"{longitude:.7f},{latitude:.7f}" for latitude, longitude in coordinates)
        params = urlencode(
            {
                "overview": "full",
                "geometries": "geojson",
                "steps": "false",
            }
        )
        url = f"{self.base_url.rstrip('/')}/route/v1/{self.profile}/{encoded}?{params}"
        request = Request(url, headers={"User-Agent": self.user_agent})
        tls_context = ssl.create_default_context(cafile=certifi.where())
        with urlopen(
            request,
            timeout=self.timeout_seconds,
            context=tls_context,
        ) as response:
            payload = json.load(response)
        if payload.get("code") != "Ok" or not payload.get("routes"):
            raise RuntimeError(f"OSRM route request failed: {payload.get('code')}")
        longitude_latitude = payload["routes"][0]["geometry"]["coordinates"]
        return [(float(latitude), float(longitude)) for longitude, latitude in longitude_latitude]


@dataclass(slots=True)
class CachedRouteGeometry:
    provider: RouteGeometryProvider
    cache_path: Path
    precision: int = 6
    _cache: dict[str, list[list[float]]] = field(default_factory=dict, init=False)
    _loaded: bool = field(default=False, init=False)

    def route(self, coordinates: list[Coordinate]) -> tuple[Coordinate, ...]:
        self._ensure_loaded()
        key = self._key(coordinates)
        cached = self._cache.get(key)
        if cached is not None:
            return tuple((float(item[0]), float(item[1])) for item in cached)
        geometry = self.provider.route(coordinates)
        self._cache[key] = [[latitude, longitude] for latitude, longitude in geometry]
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(self._cache, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        return geometry

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if self.cache_path.exists():
            self._cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
        self._loaded = True

    def _key(self, coordinates: list[Coordinate]) -> str:
        normalized = [
            [round(latitude, self.precision), round(longitude, self.precision)]
            for latitude, longitude in coordinates
        ]
        payload = json.dumps(normalized, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(payload.encode("ascii")).hexdigest()
