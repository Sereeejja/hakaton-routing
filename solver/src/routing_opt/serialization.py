from __future__ import annotations

import csv
import json
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .domain import Solution


def to_primitive(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: to_primitive(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): to_primitive(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [to_primitive(item) for item in value]
    return value


def solution_to_dict(solution: Solution) -> dict[str, Any]:
    return to_primitive(solution)


def save_solution_json(solution: Solution, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(solution_to_dict(solution), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_stops_csv(solution: Solution, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "engineer_id",
        "sequence",
        "job_id",
        "from_location_id",
        "travel_minutes",
        "distance_km",
        "arrival_minutes",
        "service_start_minutes",
        "service_end_minutes",
        "waiting_minutes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for route in solution.routes:
            for stop in route.stops:
                row = to_primitive(stop)
                writer.writerow({"engineer_id": route.engineer_id, **row})
