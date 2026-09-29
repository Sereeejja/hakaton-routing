from __future__ import annotations

import math
from time import perf_counter
from typing import Any

from routing_opt.domain import Problem, Route, Solution, Stop, business_priority_rank

from .base import MissingDependencyError, Solver
from .common import build_solution


class OrToolsSolver(Solver):
    """VRPTW solver with optional visits, skills, transport, shifts, and open routes."""

    name = "ortools"

    def solve(self, problem: Problem, time_limit_sec: float = 10, seed: int = 42) -> Solution:
        try:
            from ortools.constraint_solver import pywrapcp, routing_enums_pb2
        except ImportError as exc:  # pragma: no cover - tested in an environment with the extra
            raise MissingDependencyError(
                "Install the OR-Tools extra: pip install -e './solver[ortools]'"
            ) from exc

        started_at = perf_counter()
        routable_jobs = [
            job
            for job in problem.jobs
            if job.planning_eligible and any(e.is_compatible(job) for e in problem.engineers)
        ]
        if not routable_jobs:
            return build_solution(
                problem=problem,
                solver_name=self.name,
                routes=[_empty_route(problem, engineer.id) for engineer in problem.engineers],
                assigned_job_ids=set(),
                started_at=started_at,
                seed=seed,
            )

        node_locations = [job.location_id for job in routable_jobs]
        node_jobs = [job.id for job in routable_jobs]
        start_node_by_location: dict[str, int] = {}
        for engineer in problem.engineers:
            if engineer.start_location_id not in start_node_by_location:
                start_node_by_location[engineer.start_location_id] = len(node_locations)
                node_locations.append(engineer.start_location_id)
                node_jobs.append("")
        starts = [start_node_by_location[e.start_location_id] for e in problem.engineers]
        ends = list(starts)

        manager = pywrapcp.RoutingIndexManager(
            len(node_locations), len(problem.engineers), starts, ends
        )
        routing = pywrapcp.RoutingModel(manager)
        jobs_by_id = problem.jobs_by_id
        node_to_job = {index: job_id for index, job_id in enumerate(node_jobs) if job_id}

        time_callback_indices: list[int] = []
        for engineer in problem.engineers:
            def time_callback(
                from_index: int,
                to_index: int,
                vehicle_engineer: Any = engineer,
            ) -> int:
                from_node = manager.IndexToNode(from_index)
                from_job_id = node_to_job.get(from_node)
                service = jobs_by_id[from_job_id].service_minutes if from_job_id else 0
                if routing.IsEnd(to_index):
                    return service
                to_node = manager.IndexToNode(to_index)
                travel = problem.travel_minutes_for(
                    vehicle_engineer,
                    node_locations[from_node],
                    node_locations[to_node],
                )
                return service + (travel if travel is not None else 1_000_000)

            time_callback_indices.append(routing.RegisterTransitCallback(time_callback))
        horizon = max(engineer.shift_end for engineer in problem.engineers)
        routing.AddDimensionWithVehicleTransits(
            time_callback_indices,
            horizon,
            horizon,
            False,
            "Time",
        )
        time_dimension = routing.GetDimensionOrDie("Time")
        time_dimension.SetSlackCostCoefficientForAllVehicles(1)

        objective = _objective_weights(problem, routable_jobs)
        for vehicle_id, engineer in enumerate(problem.engineers):
            routing.SetFixedCostOfVehicle(objective["vehicle_fixed"], vehicle_id)

            def distance_callback(
                from_index: int,
                to_index: int,
                engineer_id: str = engineer.id,
            ) -> int:
                if routing.IsEnd(to_index):
                    return 0
                from_node = manager.IndexToNode(from_index)
                to_node = manager.IndexToNode(to_index)
                distance = problem.matrices.distance(
                    node_locations[from_node], node_locations[to_node]
                )
                if distance is None:
                    return 1_000_000_000
                cost = round(distance * objective["distance_scale"])
                destination_job = node_to_job.get(to_node)
                previous = problem.previous_assignments.get(destination_job or "")
                if previous and previous != engineer_id:
                    cost += objective["assignment_change"]
                return cost

            cost_callback = routing.RegisterTransitCallback(distance_callback)
            routing.SetArcCostEvaluatorOfVehicle(cost_callback, vehicle_id)

        time_dimension.SetGlobalSpanCostCoefficient(1)
        for node, job in enumerate(routable_jobs):
            index = manager.NodeToIndex(node)
            time_dimension.CumulVar(index).SetRange(job.window_start, job.window_end)
            allowed = [
                vehicle_id
                for vehicle_id, engineer in enumerate(problem.engineers)
                if engineer.is_compatible(job)
            ]
            # Keep -1 in the domain: it represents an unperformed optional node.
            # The OR-Tools 9.15 SWIG binding rejects a plain Python list in
            # SetAllowedVehiclesForIndex, while IntVar.SetValues is stable.
            routing.VehicleVar(index).SetValues([-1, *allowed])
            penalty = {
                2: objective["drop_urgent"],
                1: objective["drop_connection"],
                0: objective["drop_normal"],
            }[business_priority_rank(job)]
            routing.AddDisjunction([index], penalty)

        for vehicle_id, engineer in enumerate(problem.engineers):
            start_index = routing.Start(vehicle_id)
            end_index = routing.End(vehicle_id)
            time_dimension.CumulVar(start_index).SetRange(engineer.shift_start, engineer.shift_end)
            time_dimension.CumulVar(end_index).SetRange(engineer.shift_start, engineer.shift_end)
            routing.AddVariableMinimizedByFinalizer(time_dimension.CumulVar(start_index))
            routing.AddVariableMinimizedByFinalizer(time_dimension.CumulVar(end_index))

        search = pywrapcp.DefaultRoutingSearchParameters()
        search.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
        )
        search.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        search.time_limit.FromMilliseconds(max(1, int(time_limit_sec * 1000)))
        search.log_search = False
        if hasattr(search, "sat_parameters"):
            search.sat_parameters.random_seed = seed
            search.sat_parameters.num_search_workers = 1

        assignment = routing.SolveWithParameters(search)
        if assignment is None:
            return build_solution(
                problem=problem,
                solver_name=self.name,
                routes=[_empty_route(problem, engineer.id) for engineer in problem.engineers],
                assigned_job_ids=set(),
                started_at=started_at,
                seed=seed,
                warnings=("OR-Tools did not find a routing assignment.",),
            )

        routes: list[Route] = []
        assigned: set[str] = set()
        for vehicle_id, engineer in enumerate(problem.engineers):
            index = routing.Start(vehicle_id)
            departure = assignment.Value(time_dimension.CumulVar(index))
            current_location = engineer.start_location_id
            current_end = departure
            stops: list[Stop] = []
            while True:
                next_index = assignment.Value(routing.NextVar(index))
                if routing.IsEnd(next_index):
                    break
                node = manager.IndexToNode(next_index)
                job_id = node_to_job[node]
                job = jobs_by_id[job_id]
                travel = problem.travel_minutes_for(
                    engineer, current_location, job.location_id
                )
                distance = problem.matrices.distance(current_location, job.location_id)
                if travel is None or distance is None:
                    raise RuntimeError("OR-Tools selected an unreachable matrix leg")
                arrival = current_end + travel
                service_start = assignment.Value(time_dimension.CumulVar(next_index))
                service_end = service_start + job.service_minutes
                stops.append(
                    Stop(
                        sequence=len(stops) + 1,
                        job_id=job_id,
                        from_location_id=current_location,
                        travel_minutes=travel,
                        distance_km=distance,
                        arrival_minutes=arrival,
                        service_start_minutes=service_start,
                        service_end_minutes=service_end,
                        waiting_minutes=service_start - arrival,
                    )
                )
                assigned.add(job_id)
                current_location = job.location_id
                current_end = service_end
                index = next_index
            routes.append(
                Route(
                    engineer_id=engineer.id,
                    departure_minutes=departure,
                    finish_minutes=current_end if stops else departure,
                    stops=tuple(stops),
                    total_travel_minutes=sum(stop.travel_minutes for stop in stops),
                    total_waiting_minutes=sum(stop.waiting_minutes for stop in stops),
                    total_service_minutes=sum(
                        jobs_by_id[stop.job_id].service_minutes for stop in stops
                    ),
                    total_distance_km=sum(stop.distance_km for stop in stops),
                )
            )
        return build_solution(
            problem=problem,
            solver_name=self.name,
            routes=routes,
            assigned_job_ids=assigned,
            started_at=started_at,
            seed=seed,
            objective_value=float(assignment.ObjectiveValue()),
            metadata={"objective_weights": objective, "open_routes": True},
        )


def _objective_weights(problem: Problem, jobs: list[Any]) -> dict[str, int]:
    distance_scale = 100  # integer cost per 10 metres
    finite_distances = [
        value
        for row in problem.matrices.distance_km
        for value in row
        if value is not None and math.isfinite(value)
    ]
    max_arc = max((math.ceil(value * distance_scale) for value in finite_distances), default=1)
    max_distance_cost = max_arc * max(1, len(jobs))
    max_time_cost = max(engineer.shift_end for engineer in problem.engineers) * (
        len(problem.engineers) + 1
    )
    assignment_change = 1
    lower_bound = max_distance_cost + max_time_cost + len(jobs) * assignment_change
    vehicle_fixed = lower_bound + 1
    drop_normal = vehicle_fixed * (len(problem.engineers) + 1) + lower_bound + 1
    drop_connection = drop_normal * (len(jobs) + 1)
    drop_urgent = drop_connection * (len(jobs) + 1)
    return {
        "distance_scale": distance_scale,
        "assignment_change": assignment_change,
        "vehicle_fixed": vehicle_fixed,
        "drop_normal": drop_normal,
        "drop_connection": drop_connection,
        "drop_urgent": drop_urgent,
    }


def _empty_route(problem: Problem, engineer_id: str) -> Route:
    engineer = problem.engineers_by_id[engineer_id]
    return Route(
        engineer_id=engineer.id,
        departure_minutes=engineer.shift_start,
        finish_minutes=engineer.shift_start,
        stops=(),
        total_travel_minutes=0,
        total_waiting_minutes=0,
        total_service_minutes=0,
        total_distance_km=0.0,
    )
