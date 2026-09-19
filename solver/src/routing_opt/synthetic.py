from __future__ import annotations

import math
import random
from dataclasses import dataclass

from .domain import Engineer, Job, Location, Priority, Problem, Skill, Transport
from .matrices import haversine_matrices


@dataclass(frozen=True, slots=True)
class SyntheticConfig:
    job_count: int
    engineer_count: int | None = None
    cluster_count: int = 6
    urgent_share: float = 0.08
    transport_constraint_share: float = 0.10
    conflict_share: float = 0.05
    seed: int = 42
    center_latitude: float = 55.751244
    center_longitude: float = 37.618423


def generate_synthetic_problem(config: SyntheticConfig) -> Problem:
    """Generate clustered, reproducible VRPTW instances for 100-1000+ jobs."""

    if config.job_count <= 0:
        raise ValueError("job_count must be positive")
    rng = random.Random(config.seed)
    engineer_count = config.engineer_count or max(3, math.ceil(config.job_count / 8))
    office = Location(
        id="office:synthetic",
        address="Synthetic office",
        latitude=config.center_latitude,
        longitude=config.center_longitude,
    )
    cluster_centers = [
        (
            config.center_latitude + rng.gauss(0, 0.11),
            config.center_longitude + rng.gauss(0, 0.16),
        )
        for _ in range(config.cluster_count)
    ]
    locations = [office]
    jobs: list[Job] = []
    skill_choices = [Skill.CONNECTION, Skill.LOCAL, Skill.EMERGENCY]
    service_by_skill = {Skill.CONNECTION: 70, Skill.LOCAL: 30, Skill.EMERGENCY: 80}
    window_starts = [600, 720, 840, 960, 1080, 1200]
    for index in range(config.job_count):
        center_lat, center_lon = rng.choice(cluster_centers)
        location = Location(
            id=f"location:{index + 1}",
            address=f"Synthetic address {index + 1}",
            latitude=center_lat + rng.gauss(0, 0.018),
            longitude=center_lon + rng.gauss(0, 0.028),
        )
        locations.append(location)
        skill = rng.choices(skill_choices, weights=[0.46, 0.40, 0.14], k=1)[0]
        window_start = rng.choice(window_starts)
        window_end = min(1320, window_start + 120)
        if rng.random() < config.conflict_share:
            window_start, window_end = 480, 540  # deliberately before demo shifts
        required_transport = None
        if rng.random() < config.transport_constraint_share:
            required_transport = rng.choice(list(Transport))
        jobs.append(
            Job(
                id=f"job-{index + 1:04d}",
                location_id=location.id,
                service_minutes=service_by_skill[skill],
                window_start=window_start,
                window_end=window_end,
                required_skill=skill,
                required_transport=required_transport,
                priority=(
                    Priority.URGENT if rng.random() < config.urgent_share else Priority.NORMAL
                ),
                metadata={"synthetic": True, "clustered": True},
            )
        )
    engineers = _synthetic_engineers(engineer_count, office.id)
    matrices = haversine_matrices(locations, speed_kmh=28, road_factor=1.3)
    return Problem(
        id=f"synthetic-{config.job_count}-{config.seed}",
        jobs=tuple(jobs),
        engineers=engineers,
        locations=tuple(locations),
        matrices=matrices,
        metadata={"generator": "clustered", "seed": config.seed},
    )


def _synthetic_engineers(count: int, office_id: str) -> tuple[Engineer, ...]:
    templates = (
        (frozenset(Skill), Transport.CAR),
        (frozenset({Skill.CONNECTION, Skill.LOCAL}), Transport.PUBLIC_TRANSIT),
        (frozenset({Skill.CONNECTION}), Transport.CAR),
        (frozenset({Skill.LOCAL}), Transport.BICYCLE),
        (frozenset({Skill.EMERGENCY, Skill.LOCAL}), Transport.CAR),
        (frozenset({Skill.EMERGENCY, Skill.CONNECTION}), Transport.WALK),
    )
    return tuple(
        Engineer(
            id=f"engineer-{index + 1:03d}",
            start_location_id=office_id,
            shift_start=600,
            shift_end=1320,
            skills=templates[index % len(templates)][0],
            transport=templates[index % len(templates)][1],
            metadata={"synthetic": True},
        )
        for index in range(count)
    )
