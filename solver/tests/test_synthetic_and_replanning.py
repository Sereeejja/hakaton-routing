from __future__ import annotations

from routing_opt.replanning import CancelJob, EngineerUnavailable, apply_event, compare_plans
from routing_opt.solvers.greedy import GreedySolver
from routing_opt.synthetic import SyntheticConfig, generate_synthetic_problem


def test_synthetic_generator_is_reproducible():
    config = SyntheticConfig(job_count=20, engineer_count=4, seed=99)
    first = generate_synthetic_problem(config)
    second = generate_synthetic_problem(config)
    assert first.jobs == second.jobs
    assert first.locations == second.locations
    assert first.matrices == second.matrices


def test_replanning_events(small_problem):
    before = GreedySolver().solve(small_problem)
    cancelled = apply_event(small_problem, CancelJob("j1"), before)
    assert "j1" not in cancelled.jobs_by_id
    unavailable = apply_event(small_problem, EngineerUnavailable("e1"), before)
    assert "e1" not in unavailable.engineers_by_id
    after = GreedySolver().solve(cancelled)
    difference = compare_plans(before, after)
    assert "j1" in difference["newly_unassigned"]
