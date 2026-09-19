from __future__ import annotations

import pytest

from routing_opt.domain import Engineer, Job, Location, Problem, Skill, Transport
from routing_opt.matrices import haversine_matrices


@pytest.fixture
def small_problem() -> Problem:
    locations = (
        Location("office", latitude=55.75, longitude=37.61),
        Location("a", latitude=55.76, longitude=37.62),
        Location("b", latitude=55.77, longitude=37.63),
        Location("c", latitude=55.78, longitude=37.64),
    )
    jobs = (
        Job("j1", "a", 30, 600, 720, Skill.LOCAL),
        Job("j2", "b", 30, 660, 780, Skill.LOCAL),
        Job("j3", "c", 60, 600, 840, Skill.CONNECTION),
    )
    engineers = (
        Engineer("e1", "office", 600, 900, frozenset({Skill.LOCAL}), Transport.CAR),
        Engineer(
            "e2",
            "office",
            600,
            900,
            frozenset({Skill.LOCAL, Skill.CONNECTION}),
            Transport.PUBLIC_TRANSIT,
        ),
    )
    return Problem(
        id="small",
        jobs=jobs,
        engineers=engineers,
        locations=locations,
        matrices=haversine_matrices(locations),
    )
