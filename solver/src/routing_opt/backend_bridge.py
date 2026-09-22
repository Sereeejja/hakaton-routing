from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from typing import Any

from .domain import (
    Engineer,
    Job,
    Location,
    Priority,
    Problem,
    Skill,
    Transport,
)
from .explanations import explain_solution
from .matrices import OsrmTableClient, haversine_matrices
from .serialization import solution_to_dict, to_primitive
from .service import solve
from .validation import validate_solution


def _minutes(value: str) -> int:
    try:
        hours, minutes = (int(part) for part in value.split(":"))
    except (TypeError, ValueError) as error:
        raise ValueError(f"Invalid time {value!r}; expected HH:MM") from error
    if not 0 <= hours <= 23 or not 0 <= minutes <= 59:
        raise ValueError(f"Invalid time {value!r}; expected HH:MM")
    return hours * 60 + minutes


def solve_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    locations = tuple(
        Location(
            id=str(item["id"]),
            address=str(item.get("address", "")),
            latitude=float(item["latitude"]),
            longitude=float(item["longitude"]),
        )
        for item in payload["locations"]
    )
    jobs = tuple(
        Job(
            id=str(item["id"]),
            location_id=str(item["location_id"]),
            service_minutes=int(item["service_minutes"]),
            window_start=_minutes(item["window_start"]),
            window_end=_minutes(item["window_end"]),
            required_skill=Skill(item["required_skill"]),
            required_transport=(
                Transport(item["required_transport"]) if item.get("required_transport") else None
            ),
            priority=Priority(item.get("priority", "normal")),
        )
        for item in payload["jobs"]
    )
    engineers = tuple(
        Engineer(
            id=str(item["id"]),
            start_location_id=str(item["start_location_id"]),
            shift_start=_minutes(item["shift_start"]),
            shift_end=_minutes(item["shift_end"]),
            skills=frozenset(Skill(value) for value in item["skills"]),
            transport=Transport(item["transport"]),
        )
        for item in payload["engineers"]
    )
    options = payload.get("options", {})
    routing_base_url = str(options.get("routing_base_url", "")).strip()
    if routing_base_url:
        matrices = OsrmTableClient(routing_base_url).build(locations)
    else:
        matrices = haversine_matrices(
            locations,
            speed_kmh=float(options.get("travel_speed_kmh", 30)),
        )
    problem = Problem(
        id=str(payload["problem_id"]),
        jobs=jobs,
        engineers=engineers,
        locations=locations,
        matrices=matrices,
        previous_assignments={
            str(job_id): str(engineer_id)
            for job_id, engineer_id in payload.get("previous_assignments", {}).items()
        },
    )
    solution = solve(
        problem,
        solver_name=options.get("solver", "ortools"),
        time_limit_sec=float(options.get("time_limit_sec", 10)),
        seed=int(options.get("seed", 42)),
    )
    report = validate_solution(problem, solution)
    if not report.valid:
        raise RuntimeError("Solver produced invalid solution: " + "; ".join(report.errors))
    baseline = (
        solution
        if solution.solver_name == "greedy_official"
        else solve(
            problem,
            solver_name="greedy",
            time_limit_sec=1,
            seed=int(options.get("seed", 42)),
        )
    )
    baseline_report = validate_solution(problem, baseline)
    if not baseline_report.valid:
        raise RuntimeError(
            "Baseline produced invalid solution: " + "; ".join(baseline_report.errors)
        )
    result = solution_to_dict(solution)
    result["explanations"] = explain_solution(problem, solution)
    result["baseline"] = {
        "solver_name": baseline.solver_name,
        "metrics": to_primitive(baseline.metrics),
    }
    return result


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        json.dump(solve_payload(payload), sys.stdout, ensure_ascii=False)
        return 0
    except Exception as error:  # noqa: BLE001 - process boundary returns a clean error
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
