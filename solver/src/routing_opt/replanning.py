from __future__ import annotations

from dataclasses import dataclass, replace

from .domain import Job, Priority, Problem, Solution


@dataclass(frozen=True, slots=True)
class NewUrgentJob:
    job: Job


@dataclass(frozen=True, slots=True)
class CancelJob:
    job_id: str


@dataclass(frozen=True, slots=True)
class EngineerUnavailable:
    engineer_id: str


ReplanningEvent = NewUrgentJob | CancelJob | EngineerUnavailable


def apply_event(problem: Problem, event: ReplanningEvent, published: Solution) -> Problem:
    previous = {
        stop.job_id: route.engineer_id for route in published.routes for stop in route.stops
    }
    jobs = list(problem.jobs)
    engineers = list(problem.engineers)
    if isinstance(event, CancelJob):
        if event.job_id not in problem.jobs_by_id:
            raise KeyError(f"Unknown job {event.job_id}")
        jobs = [job for job in jobs if job.id != event.job_id]
        previous.pop(event.job_id, None)
    elif isinstance(event, EngineerUnavailable):
        if event.engineer_id not in problem.engineers_by_id:
            raise KeyError(f"Unknown engineer {event.engineer_id}")
        engineers = [engineer for engineer in engineers if engineer.id != event.engineer_id]
        previous = {
            job_id: engineer_id
            for job_id, engineer_id in previous.items()
            if engineer_id != event.engineer_id
        }
    else:
        if event.job.id in problem.jobs_by_id:
            raise ValueError(f"Duplicate job ID {event.job.id}")
        if not problem.matrices.contains(event.job.location_id):
            raise ValueError("Matrices must be extended before adding a job at a new location")
        jobs.append(replace(event.job, priority=Priority.URGENT))
    return Problem(
        id=f"{problem.id}:replanned",
        jobs=tuple(jobs),
        engineers=tuple(engineers),
        locations=problem.locations,
        matrices=problem.matrices,
        previous_assignments=previous,
        metadata={**dict(problem.metadata), "replanning_event": type(event).__name__},
    )


def compare_plans(before: Solution, after: Solution) -> dict[str, object]:
    old = {
        stop.job_id: (route.engineer_id, stop.sequence)
        for route in before.routes
        for stop in route.stops
    }
    new = {
        stop.job_id: (route.engineer_id, stop.sequence)
        for route in after.routes
        for stop in route.stops
    }
    common = set(old) & set(new)
    return {
        "assignment_changes": sorted(job for job in common if old[job][0] != new[job][0]),
        "sequence_changes": sorted(job for job in common if old[job][1] != new[job][1]),
        "newly_assigned": sorted(set(new) - set(old)),
        "newly_unassigned": sorted(set(old) - set(new)),
    }
