from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from statistics import pstdev
from types import MappingProxyType
from typing import Any


class Skill(StrEnum):
    CONNECTION = "connection"
    LOCAL = "local"
    EMERGENCY = "emergency"


class Transport(StrEnum):
    CAR = "car"
    WALK = "walk"
    BICYCLE = "bicycle"
    PUBLIC_TRANSIT = "public_transit"


class Priority(StrEnum):
    NORMAL = "normal"
    URGENT = "urgent"


class SolutionStatus(StrEnum):
    FEASIBLE = "feasible"
    PARTIAL = "partial"
    INFEASIBLE = "infeasible"
    ERROR = "error"


class UnassignedCode(StrEnum):
    EXCLUDED_POLICY = "excluded_policy"
    NO_SKILLED_ENGINEER = "no_skilled_engineer"
    NO_COMPATIBLE_TRANSPORT = "no_compatible_transport"
    TIME_WINDOW = "time_window"
    SHIFT = "shift"
    ROUTING_UNREACHABLE = "routing_unreachable"
    OPTIMIZATION_DROPPED = "optimization_dropped"


@dataclass(frozen=True, slots=True)
class Location:
    id: str
    address: str = ""
    latitude: float | None = None
    longitude: float | None = None

    @property
    def has_coordinates(self) -> bool:
        return self.latitude is not None and self.longitude is not None


@dataclass(frozen=True, slots=True)
class Job:
    id: str
    location_id: str
    service_minutes: int
    window_start: int
    window_end: int
    required_skill: Skill
    required_transport: Transport | None = None
    priority: Priority = Priority.NORMAL
    planning_eligible: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.service_minutes < 0:
            raise ValueError(f"Job {self.id}: service_minutes cannot be negative")
        if not 0 <= self.window_start <= self.window_end:
            raise ValueError(f"Job {self.id}: invalid time window")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class Engineer:
    id: str
    start_location_id: str
    shift_start: int
    shift_end: int
    skills: frozenset[Skill]
    transport: Transport
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.shift_start > self.shift_end:
            raise ValueError(f"Engineer {self.id}: invalid shift")
        if not self.skills:
            raise ValueError(f"Engineer {self.id}: at least one skill is required")
        object.__setattr__(self, "skills", frozenset(self.skills))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def is_compatible(self, job: Job) -> bool:
        skill_ok = job.required_skill in self.skills
        transport_ok = job.required_transport in (None, self.transport)
        return skill_ok and transport_ok


@dataclass(frozen=True, slots=True)
class TravelMatrices:
    location_ids: tuple[str, ...]
    time_minutes: tuple[tuple[int | None, ...], ...]
    distance_km: tuple[tuple[float | None, ...], ...]
    provider: str = "unknown"
    profile: str = "driving"
    metadata: Mapping[str, Any] = field(default_factory=dict)
    _index: Mapping[str, int] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        size = len(self.location_ids)
        if len(set(self.location_ids)) != size:
            raise ValueError("TravelMatrices.location_ids must be unique")
        if len(self.time_minutes) != size or len(self.distance_km) != size:
            raise ValueError("Travel matrices must be square and match location_ids")
        for row in self.time_minutes:
            if len(row) != size:
                raise ValueError("time_minutes matrix is not square")
            if any(value is not None and value < 0 for value in row):
                raise ValueError("time_minutes cannot contain negative values")
        for row in self.distance_km:
            if len(row) != size:
                raise ValueError("distance_km matrix is not square")
            if any(value is not None and (value < 0 or not isfinite(value)) for value in row):
                raise ValueError("distance_km must contain finite non-negative values")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        object.__setattr__(
            self, "_index", MappingProxyType(dict(zip(self.location_ids, range(size))))
        )

    def travel_minutes(self, from_location: str, to_location: str) -> int | None:
        return self.time_minutes[self._index[from_location]][self._index[to_location]]

    def distance(self, from_location: str, to_location: str) -> float | None:
        return self.distance_km[self._index[from_location]][self._index[to_location]]

    def contains(self, location_id: str) -> bool:
        return location_id in self._index


@dataclass(frozen=True, slots=True)
class Problem:
    id: str
    jobs: tuple[Job, ...]
    engineers: tuple[Engineer, ...]
    locations: tuple[Location, ...]
    matrices: TravelMatrices
    previous_assignments: Mapping[str, str] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        job_ids = [job.id for job in self.jobs]
        engineer_ids = [engineer.id for engineer in self.engineers]
        location_ids = [location.id for location in self.locations]
        if len(set(job_ids)) != len(job_ids):
            raise ValueError("Job IDs must be unique")
        if len(set(engineer_ids)) != len(engineer_ids):
            raise ValueError("Engineer IDs must be unique")
        if len(set(location_ids)) != len(location_ids):
            raise ValueError("Location IDs must be unique")
        known_locations = set(location_ids)
        used_locations = {job.location_id for job in self.jobs}
        used_locations.update(engineer.start_location_id for engineer in self.engineers)
        missing = used_locations - known_locations
        if missing:
            raise ValueError(f"Unknown locations in problem: {sorted(missing)}")
        missing_matrix = {loc for loc in used_locations if not self.matrices.contains(loc)}
        if missing_matrix:
            raise ValueError(f"Locations missing from matrices: {sorted(missing_matrix)}")
        unknown_previous_jobs = set(self.previous_assignments) - set(job_ids)
        unknown_previous_engineers = set(self.previous_assignments.values()) - set(engineer_ids)
        if unknown_previous_jobs or unknown_previous_engineers:
            raise ValueError("previous_assignments refers to unknown jobs or engineers")
        object.__setattr__(
            self, "previous_assignments", MappingProxyType(dict(self.previous_assignments))
        )
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def jobs_by_id(self) -> dict[str, Job]:
        return {job.id: job for job in self.jobs}

    @property
    def engineers_by_id(self) -> dict[str, Engineer]:
        return {engineer.id: engineer for engineer in self.engineers}

    @property
    def locations_by_id(self) -> dict[str, Location]:
        return {location.id: location for location in self.locations}


@dataclass(frozen=True, slots=True)
class Stop:
    sequence: int
    job_id: str
    from_location_id: str
    travel_minutes: int
    distance_km: float
    arrival_minutes: int
    service_start_minutes: int
    service_end_minutes: int
    waiting_minutes: int


@dataclass(frozen=True, slots=True)
class Route:
    engineer_id: str
    departure_minutes: int
    finish_minutes: int
    stops: tuple[Stop, ...]
    total_travel_minutes: int
    total_waiting_minutes: int
    total_service_minutes: int
    total_distance_km: float

    @property
    def is_active(self) -> bool:
        return bool(self.stops)

    @property
    def duration_minutes(self) -> int:
        return self.finish_minutes - self.departure_minutes if self.stops else 0


@dataclass(frozen=True, slots=True)
class UnassignedJob:
    job_id: str
    code: UnassignedCode
    message: str


@dataclass(frozen=True, slots=True)
class SolverMetrics:
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
    objective_value: float | None = None

    @classmethod
    def from_routes(
        cls,
        routes: Sequence[Route],
        unassigned: Sequence[UnassignedJob],
        jobs_by_id: Mapping[str, Job],
        runtime_seconds: float,
        objective_value: float | None = None,
    ) -> SolverMetrics:
        active = [route for route in routes if route.is_active]
        workloads = [route.total_service_minutes + route.total_travel_minutes for route in active]
        return cls(
            completed_jobs=sum(len(route.stops) for route in routes),
            unassigned_urgent_jobs=sum(
                jobs_by_id[item.job_id].priority is Priority.URGENT for item in unassigned
            ),
            unassigned_jobs=len(unassigned),
            active_engineers=len(active),
            total_distance_km=round(sum(route.total_distance_km for route in routes), 6),
            total_travel_minutes=sum(route.total_travel_minutes for route in routes),
            total_waiting_minutes=sum(route.total_waiting_minutes for route in routes),
            max_route_duration_minutes=max((route.duration_minutes for route in routes), default=0),
            workload_stddev_minutes=pstdev(workloads) if len(workloads) > 1 else 0.0,
            runtime_seconds=runtime_seconds,
            objective_value=objective_value,
        )


@dataclass(frozen=True, slots=True)
class Solution:
    solver_name: str
    status: SolutionStatus
    routes: tuple[Route, ...]
    unassigned: tuple[UnassignedJob, ...]
    metrics: SolverMetrics
    seed: int
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
