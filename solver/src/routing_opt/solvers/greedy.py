from __future__ import annotations

from time import perf_counter

from routing_opt.domain import Problem, Route, Solution
from routing_opt.scheduling import evaluate_route

from .base import Solver
from .common import build_solution


class GreedySolver(Solver):
    """Official baseline: input order and first compatible available engineer."""

    name = "greedy_official"

    def solve(self, problem: Problem, time_limit_sec: float = 10, seed: int = 42) -> Solution:
        del time_limit_sec
        started_at = perf_counter()
        sequences: dict[str, list[str]] = {engineer.id: [] for engineer in problem.engineers}
        routes: dict[str, Route] = {
            engineer.id: evaluate_route(problem, engineer, []).route
            for engineer in problem.engineers
        }
        assigned: set[str] = set()
        for job in problem.jobs:
            if not job.planning_eligible:
                continue
            for engineer in problem.engineers:
                if not engineer.is_compatible(job):
                    continue
                candidate_ids = [*sequences[engineer.id], job.id]
                candidate = evaluate_route(problem, engineer, candidate_ids)
                if candidate.feasible:
                    sequences[engineer.id] = candidate_ids
                    routes[engineer.id] = candidate.route
                    assigned.add(job.id)
                    break
        return build_solution(
            problem=problem,
            solver_name=self.name,
            routes=[routes[engineer.id] for engineer in problem.engineers],
            assigned_job_ids=assigned,
            started_at=started_at,
            seed=seed,
            metadata={"policy": "input_order_first_feasible_append"},
        )


class ImprovedGreedySolver(Solver):
    """Best-feasible-insertion heuristic, kept separate from the official baseline."""

    name = "greedy_best_insertion"

    def solve(self, problem: Problem, time_limit_sec: float = 10, seed: int = 42) -> Solution:
        del time_limit_sec
        started_at = perf_counter()
        sequences: dict[str, list[str]] = {engineer.id: [] for engineer in problem.engineers}
        routes: dict[str, Route] = {
            engineer.id: evaluate_route(problem, engineer, []).route
            for engineer in problem.engineers
        }
        assigned: set[str] = set()
        ordered_jobs = sorted(
            (job for job in problem.jobs if job.planning_eligible),
            key=lambda job: (
                0 if job.priority.value == "urgent" else 1,
                job.window_end,
                job.window_start,
                int(job.metadata.get("source_order", 0)),
            ),
        )
        for job in ordered_jobs:
            best: tuple[tuple[float, ...], str, int, Route] | None = None
            for engineer in problem.engineers:
                if not engineer.is_compatible(job):
                    continue
                original = sequences[engineer.id]
                for position in range(len(original) + 1):
                    candidate_ids = [*original[:position], job.id, *original[position:]]
                    evaluation = evaluate_route(problem, engineer, candidate_ids)
                    if not evaluation.feasible:
                        continue
                    route = evaluation.route
                    was_active = bool(original)
                    score = (
                        0.0 if was_active else 1.0,
                        route.total_distance_km - routes[engineer.id].total_distance_km,
                        float(
                            route.total_travel_minutes - routes[engineer.id].total_travel_minutes
                        ),
                        float(position),
                    )
                    candidate = (score, engineer.id, position, route)
                    if best is None or candidate[0] < best[0]:
                        best = candidate
            if best is not None:
                _, engineer_id, position, route = best
                sequences[engineer_id].insert(position, job.id)
                routes[engineer_id] = route
                assigned.add(job.id)
        return build_solution(
            problem=problem,
            solver_name=self.name,
            routes=[routes[engineer.id] for engineer in problem.engineers],
            assigned_job_ids=assigned,
            started_at=started_at,
            seed=seed,
            metadata={"policy": "urgent_deadline_best_feasible_insertion"},
        )
