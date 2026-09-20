from __future__ import annotations

from dataclasses import dataclass

from .domain import Engineer, Problem, Route, Stop


@dataclass(frozen=True, slots=True)
class RouteEvaluation:
    route: Route
    time_window_violation: int = 0
    shift_violation: int = 0
    compatibility_violations: int = 0
    unreachable_legs: int = 0

    @property
    def feasible(self) -> bool:
        return not (
            self.time_window_violation
            or self.shift_violation
            or self.compatibility_violations
            or self.unreachable_legs
        )


def evaluate_route(
    problem: Problem,
    engineer: Engineer,
    job_ids: list[str] | tuple[str, ...],
    *,
    departure_minutes: int | None = None,
    allow_violations: bool = False,
) -> RouteEvaluation:
    """Build the earliest schedule for a fixed engineer and job order."""

    jobs = problem.jobs_by_id
    departure = engineer.shift_start if departure_minutes is None else departure_minutes
    current_time = departure
    current_location = engineer.start_location_id
    stops: list[Stop] = []
    window_violation = 0
    compatibility_violations = 0
    unreachable = 0

    for sequence, job_id in enumerate(job_ids, start=1):
        job = jobs[job_id]
        if not engineer.is_compatible(job) or not job.planning_eligible:
            compatibility_violations += 1
        travel = problem.matrices.travel_minutes(current_location, job.location_id)
        distance = problem.matrices.distance(current_location, job.location_id)
        if travel is None or distance is None:
            unreachable += 1
            if not allow_violations:
                return _empty_failed_route(engineer, departure, unreachable_legs=unreachable)
            travel = 10_000
            distance = 10_000.0
        arrival = current_time + travel
        start = max(arrival, job.window_start)
        window_violation += max(0, start - job.window_end)
        end = start + job.service_minutes
        stops.append(
            Stop(
                sequence=sequence,
                job_id=job.id,
                from_location_id=current_location,
                travel_minutes=travel,
                distance_km=distance,
                arrival_minutes=arrival,
                service_start_minutes=start,
                service_end_minutes=end,
                waiting_minutes=start - arrival,
            )
        )
        current_time = end
        current_location = job.location_id

    shift_violation = max(0, current_time - engineer.shift_end) if stops else 0
    route = Route(
        engineer_id=engineer.id,
        departure_minutes=departure,
        finish_minutes=current_time if stops else departure,
        stops=tuple(stops),
        total_travel_minutes=sum(stop.travel_minutes for stop in stops),
        total_waiting_minutes=sum(stop.waiting_minutes for stop in stops),
        total_service_minutes=sum(jobs[stop.job_id].service_minutes for stop in stops),
        total_distance_km=sum(stop.distance_km for stop in stops),
    )
    evaluation = RouteEvaluation(
        route=route,
        time_window_violation=window_violation,
        shift_violation=shift_violation,
        compatibility_violations=compatibility_violations,
        unreachable_legs=unreachable,
    )
    if not allow_violations and not evaluation.feasible:
        return evaluation
    return evaluation


def _empty_failed_route(
    engineer: Engineer, departure: int, *, unreachable_legs: int
) -> RouteEvaluation:
    return RouteEvaluation(
        route=Route(
            engineer_id=engineer.id,
            departure_minutes=departure,
            finish_minutes=departure,
            stops=(),
            total_travel_minutes=0,
            total_waiting_minutes=0,
            total_service_minutes=0,
            total_distance_km=0.0,
        ),
        unreachable_legs=unreachable_legs,
    )
