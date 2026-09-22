from __future__ import annotations

from routing_opt.domain import Engineer, Location, Problem, Skill, Transport, TravelMatrices
from routing_opt.matrices import haversine_matrices


def test_transport_changes_travel_time_but_not_distance():
    locations = (
        Location("office", latitude=55.75, longitude=37.61),
        Location("job", latitude=55.75, longitude=37.71),
    )
    matrices = haversine_matrices(locations, speed_kmh=30, road_factor=1.3)
    problem = Problem(
        id="transport-times",
        jobs=(),
        engineers=(),
        locations=locations,
        matrices=matrices,
    )
    def make_engineer(transport: Transport) -> Engineer:
        return Engineer(
            transport.value,
            "office",
            540,
            1080,
            frozenset({Skill.LOCAL}),
            transport,
        )

    car = problem.travel_minutes_for(make_engineer(Transport.CAR), "office", "job")
    transit = problem.travel_minutes_for(
        make_engineer(Transport.PUBLIC_TRANSIT), "office", "job"
    )
    bicycle = problem.travel_minutes_for(
        make_engineer(Transport.BICYCLE), "office", "job"
    )
    walk = problem.travel_minutes_for(make_engineer(Transport.WALK), "office", "job")

    assert car is not None
    assert transit is not None
    assert bicycle is not None
    assert walk is not None
    assert car < transit < bicycle < walk


def test_transport_keeps_unreachable_legs_unreachable():
    locations = (Location("office"), Location("job"))
    problem = Problem(
        id="unreachable",
        jobs=(),
        engineers=(),
        locations=locations,
        matrices=TravelMatrices(
            location_ids=("office", "job"),
            time_minutes=((0, None), (None, 0)),
            distance_km=((0.0, None), (None, 0.0)),
        ),
    )
    engineer = Engineer(
        "walker", "office", 540, 1080, frozenset({Skill.LOCAL}), Transport.WALK
    )

    assert problem.travel_minutes_for(engineer, "office", "job") is None
