from __future__ import annotations

from time import perf_counter

from routing_opt.domain import (
    Job,
    Problem,
    Route,
    Solution,
    SolutionStatus,
    SolverMetrics,
    UnassignedCode,
    UnassignedJob,
)
from routing_opt.scheduling import evaluate_route


def explain_unassigned(problem: Problem, job: Job) -> UnassignedJob:
    if not job.planning_eligible:
        return UnassignedJob(
            job.id,
            UnassignedCode.EXCLUDED_POLICY,
            "Заявка исключена выбранной политикой обработки типа работ.",
        )
    skilled = [engineer for engineer in problem.engineers if job.required_skill in engineer.skills]
    if not skilled:
        return UnassignedJob(
            job.id,
            UnassignedCode.NO_SKILLED_ENGINEER,
            "Нет инженера с требуемой квалификацией.",
        )
    compatible = [
        engineer for engineer in skilled if job.required_transport in (None, engineer.transport)
    ]
    if not compatible:
        return UnassignedJob(
            job.id,
            UnassignedCode.NO_COMPATIBLE_TRANSPORT,
            "Нет инженера с требуемым типом транспорта.",
        )
    saw_reachable = False
    saw_window_fit = False
    for engineer in compatible:
        travel = problem.matrices.travel_minutes(engineer.start_location_id, job.location_id)
        distance = problem.matrices.distance(engineer.start_location_id, job.location_id)
        if travel is None or distance is None:
            continue
        saw_reachable = True
        arrival = engineer.shift_start + travel
        start = max(arrival, job.window_start)
        if start <= job.window_end:
            saw_window_fit = True
            if start + job.service_minutes <= engineer.shift_end:
                return UnassignedJob(
                    job.id,
                    UnassignedCode.OPTIMIZATION_DROPPED,
                    "Совместимый исполнитель существует, но заявка не вошла в итоговый план.",
                )
    if not saw_reachable:
        return UnassignedJob(
            job.id,
            UnassignedCode.ROUTING_UNREACHABLE,
            "Нет доступного маршрута от стартовой точки совместимого инженера.",
        )
    if not saw_window_fit:
        return UnassignedJob(
            job.id,
            UnassignedCode.TIME_WINDOW,
            "Ни один совместимый инженер не успевает начать работу во временном окне.",
        )
    return UnassignedJob(
        job.id,
        UnassignedCode.SHIFT,
        "Работа не помещается в смену совместимого инженера.",
    )


def build_solution(
    *,
    problem: Problem,
    solver_name: str,
    routes: list[Route] | tuple[Route, ...],
    assigned_job_ids: set[str],
    started_at: float,
    seed: int,
    objective_value: float | None = None,
    warnings: tuple[str, ...] = (),
    metadata: dict[str, object] | None = None,
) -> Solution:
    unassigned = tuple(
        explain_unassigned(problem, job) for job in problem.jobs if job.id not in assigned_job_ids
    )
    route_tuple = tuple(routes)
    runtime = perf_counter() - started_at
    metrics = SolverMetrics.from_routes(
        route_tuple,
        unassigned,
        problem.jobs_by_id,
        runtime,
        objective_value,
    )
    status = SolutionStatus.FEASIBLE if not unassigned else SolutionStatus.PARTIAL
    return Solution(
        solver_name=solver_name,
        status=status,
        routes=route_tuple,
        unassigned=unassigned,
        metrics=metrics,
        seed=seed,
        warnings=warnings,
        metadata=metadata or {},
    )


def empty_route(problem: Problem, engineer_id: str) -> Route:
    engineer = problem.engineers_by_id[engineer_id]
    return evaluate_route(problem, engineer, []).route
