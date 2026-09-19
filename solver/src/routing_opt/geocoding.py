from __future__ import annotations

import csv
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .domain import Location


class Geocoder(Protocol):
    def geocode(self, address: str) -> tuple[float, float] | None: ...


@dataclass(slots=True)
class CachedGeocoder:
    """Provider-neutral JSON cache. Network policy belongs to the injected provider."""

    provider: Geocoder
    cache_path: Path

    def resolve(self, locations: Iterable[Location]) -> tuple[Location, ...]:
        cache = self._load()
        changed = False
        resolved: list[Location] = []
        for location in locations:
            if location.has_coordinates:
                resolved.append(location)
                continue
            cached = cache.get(location.address)
            if cached is None:
                coordinates = self.provider.geocode(location.address)
                if coordinates is not None:
                    cache[location.address] = list(coordinates)
                    changed = True
            else:
                coordinates = (float(cached[0]), float(cached[1]))
            if coordinates is None:
                resolved.append(location)
            else:
                resolved.append(
                    Location(
                        id=location.id,
                        address=location.address,
                        latitude=coordinates[0],
                        longitude=coordinates[1],
                    )
                )
        if changed:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(
                json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        return tuple(resolved)

    def _load(self) -> dict[str, list[float]]:
        if not self.cache_path.exists():
            return {}
        return json.loads(self.cache_path.read_text(encoding="utf-8"))


@dataclass(frozen=True, slots=True)
class CallableGeocoder:
    callback: Callable[[str], tuple[float, float] | None]

    def geocode(self, address: str) -> tuple[float, float] | None:
        return self.callback(address)


@dataclass(frozen=True, slots=True)
class CsvGeocoder:
    coordinates: dict[str, tuple[float, float]]

    @classmethod
    def from_file(cls, path: str | Path) -> CsvGeocoder:
        with Path(path).open("r", encoding="utf-8", newline="") as handle:
            rows = csv.DictReader(handle)
            coordinates = {
                row["address"]: (float(row["latitude"]), float(row["longitude"])) for row in rows
            }
        return cls(coordinates=coordinates)

    def geocode(self, address: str) -> tuple[float, float] | None:
        return self.coordinates.get(address)


def unresolved_locations(locations: Iterable[Location]) -> tuple[Location, ...]:
    return tuple(location for location in locations if not location.has_coordinates)
