from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean, median, pstdev

from .domain import Problem, Solution
from .solvers.base import Solver
from .validation import validate_solution


@dataclass(frozen=True, slots=True)
class BenchmarkRecord:
    solver: str
    seed: int
    valid: bool
    status: str
    completed_jobs: int
    unassigned_urgent_jobs: int
    unassigned_jobs: int
    active_engineers: int
    total_distance_km: float
    total_travel_minutes: int
    total_waiting_minutes: int
    max_route_duration_minutes: int
    workload_stddev_minutes: float
    runtime_seconds: float
    validation_errors: tuple[str, ...]


def run_benchmark(
    problem: Problem,
    solvers: Iterable[Solver],
    *,
    time_limit_sec: float = 10,
    seeds: Iterable[int] = (42,),
) -> tuple[list[BenchmarkRecord], list[Solution]]:
    records: list[BenchmarkRecord] = []
    solutions: list[Solution] = []
    seed_values = tuple(seeds) or (42,)
    for solver in solvers:
        solver_seeds = seed_values if solver.name == "hgs" else (seed_values[0],)
        for seed in solver_seeds:
            solution = solver.solve(problem, time_limit_sec=time_limit_sec, seed=seed)
            report = validate_solution(problem, solution)
            metrics = solution.metrics
            records.append(
                BenchmarkRecord(
                    solver=solver.name,
                    seed=seed,
                    valid=report.valid,
                    status=solution.status.value,
                    completed_jobs=metrics.completed_jobs,
                    unassigned_urgent_jobs=metrics.unassigned_urgent_jobs,
                    unassigned_jobs=metrics.unassigned_jobs,
                    active_engineers=metrics.active_engineers,
                    total_distance_km=metrics.total_distance_km,
                    total_travel_minutes=metrics.total_travel_minutes,
                    total_waiting_minutes=metrics.total_waiting_minutes,
                    max_route_duration_minutes=metrics.max_route_duration_minutes,
                    workload_stddev_minutes=metrics.workload_stddev_minutes,
                    runtime_seconds=metrics.runtime_seconds,
                    validation_errors=report.errors,
                )
            )
            if report.valid:
                solutions.append(solution)
    return records, solutions


def summarize_stochastic(
    records: Iterable[BenchmarkRecord], solver_name: str = "hgs"
) -> dict[str, dict[str, float]]:
    selected = [record for record in records if record.solver == solver_name and record.valid]
    result: dict[str, dict[str, float]] = {}
    for field_name in (
        "completed_jobs",
        "unassigned_jobs",
        "active_engineers",
        "total_distance_km",
        "runtime_seconds",
    ):
        values = [float(getattr(record, field_name)) for record in selected]
        if values:
            result[field_name] = {
                "mean": mean(values),
                "median": median(values),
                "best": min(values) if field_name != "completed_jobs" else max(values),
                "stddev": pstdev(values) if len(values) > 1 else 0.0,
            }
    return result


def save_benchmark(records: Iterable[BenchmarkRecord], path: str | Path) -> None:
    rows = [asdict(record) for record in records]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
