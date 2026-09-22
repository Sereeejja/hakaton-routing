from __future__ import annotations

from dataclasses import dataclass
from math import isclose

from .domain import Problem, Solution, SolverMetrics


@dataclass(frozen=True, slots=True)
class ValidationReport:
    valid: bool
    errors: tuple[str, ...]
    recalculated_metrics: SolverMetrics


def validate_solution(problem: Problem, solution: Solution) -> ValidationReport:
    """Independently verify assignments, schedules, matrices, and aggregate metrics."""

    errors: list[str] = []
    jobs = problem.jobs_by_id
    engineers = problem.engineers_by_id
    assigned: dict[str, str] = {}
    routed_engineers: set[str] = set()

    for route in solution.routes:
        engineer = engineers.get(route.engineer_id)
        if engineer is None:
            errors.append(f"unknown engineer in route: {route.engineer_id}")
            continue
        if route.engineer_id in routed_engineers:
            errors.append(f"duplicate route for engineer: {route.engineer_id}")
        routed_engineers.add(route.engineer_id)
        if route.departure_minutes < engineer.shift_start:
            errors.append(f"{engineer.id}: departure precedes shift")
        if route.departure_minutes > engineer.shift_end:
            errors.append(f"{engineer.id}: departure exceeds shift")
        current_location = engineer.start_location_id
        current_end = route.departure_minutes
        travel_total = 0
        wait_total = 0
        service_total = 0
        distance_total = 0.0
        for expected_sequence, stop in enumerate(route.stops, start=1):
            job = jobs.get(stop.job_id)
            if job is None:
                errors.append(f"unknown job in route: {stop.job_id}")
                continue
            if stop.job_id in assigned:
                errors.append(
                    f"job {stop.job_id} assigned more than once: "
                    f"{assigned[stop.job_id]} and {engineer.id}"
                )
            assigned[stop.job_id] = engineer.id
            if not job.planning_eligible:
                errors.append(f"job {job.id} is excluded by policy but assigned")
            if job.required_skill not in engineer.skills:
                errors.append(f"{engineer.id} lacks skill for job {job.id}")
            if job.required_transport not in (None, engineer.transport):
                errors.append(f"{engineer.id} has incompatible transport for job {job.id}")
            if stop.sequence != expected_sequence:
                errors.append(f"{engineer.id}: invalid sequence number at job {job.id}")
            if stop.from_location_id != current_location:
                errors.append(f"{engineer.id}: invalid predecessor for job {job.id}")
            expected_travel = problem.travel_minutes_for(
                engineer, current_location, job.location_id
            )
            expected_distance = problem.matrices.distance(current_location, job.location_id)
            if expected_travel is None or expected_distance is None:
                errors.append(f"unreachable matrix leg to job {job.id}")
                continue
            expected_arrival = current_end + expected_travel
            if stop.travel_minutes != expected_travel:
                errors.append(f"job {job.id}: incorrect matrix travel time")
            if not isclose(stop.distance_km, expected_distance, abs_tol=1e-6):
                errors.append(f"job {job.id}: incorrect matrix distance")
            if stop.arrival_minutes != expected_arrival:
                errors.append(f"job {job.id}: incorrect arrival time")
            earliest_start = max(expected_arrival, job.window_start)
            if stop.service_start_minutes < earliest_start:
                errors.append(f"job {job.id}: service starts before arrival/window")
            if stop.service_start_minutes > job.window_end:
                errors.append(f"job {job.id}: time window violated")
            expected_wait = stop.service_start_minutes - expected_arrival
            if stop.waiting_minutes != expected_wait:
                errors.append(f"job {job.id}: incorrect waiting time")
            expected_end = stop.service_start_minutes + job.service_minutes
            if stop.service_end_minutes != expected_end:
                errors.append(f"job {job.id}: incorrect service end")
            if expected_end > engineer.shift_end:
                errors.append(f"job {job.id}: engineer shift violated")
            travel_total += expected_travel
            wait_total += expected_wait
            service_total += job.service_minutes
            distance_total += expected_distance
            current_location = job.location_id
            current_end = expected_end
        expected_finish = current_end if route.stops else route.departure_minutes
        if route.finish_minutes != expected_finish:
            errors.append(f"{engineer.id}: incorrect route finish")
        if route.total_travel_minutes != travel_total:
            errors.append(f"{engineer.id}: incorrect total travel time")
        if route.total_waiting_minutes != wait_total:
            errors.append(f"{engineer.id}: incorrect total waiting time")
        if route.total_service_minutes != service_total:
            errors.append(f"{engineer.id}: incorrect total service time")
        if not isclose(route.total_distance_km, distance_total, abs_tol=1e-6):
            errors.append(f"{engineer.id}: incorrect total distance")

    unassigned_ids = [item.job_id for item in solution.unassigned]
    if len(set(unassigned_ids)) != len(unassigned_ids):
        errors.append("duplicate jobs in unassigned list")
    overlap = set(assigned) & set(unassigned_ids)
    if overlap:
        errors.append(f"jobs are both assigned and unassigned: {sorted(overlap)}")
    unknown_unassigned = set(unassigned_ids) - set(jobs)
    if unknown_unassigned:
        errors.append(f"unknown jobs in unassigned list: {sorted(unknown_unassigned)}")
    missing = set(jobs) - set(assigned) - set(unassigned_ids)
    if missing:
        errors.append(f"jobs missing from solution: {sorted(missing)}")

    recalculated = SolverMetrics.from_routes(
        solution.routes,
        solution.unassigned,
        jobs,
        solution.metrics.runtime_seconds,
        solution.metrics.objective_value,
    )
    comparable_fields = (
        "completed_jobs",
        "unassigned_urgent_jobs",
        "unassigned_jobs",
        "active_engineers",
        "total_distance_km",
        "total_travel_minutes",
        "total_waiting_minutes",
        "max_route_duration_minutes",
        "workload_stddev_minutes",
    )
    for field_name in comparable_fields:
        actual = getattr(solution.metrics, field_name)
        expected = getattr(recalculated, field_name)
        if isinstance(actual, float):
            matches = isclose(actual, expected, abs_tol=1e-6)
        else:
            matches = actual == expected
        if not matches:
            errors.append(f"incorrect metric {field_name}: got {actual}, expected {expected}")
    return ValidationReport(not errors, tuple(errors), recalculated)
