from __future__ import annotations

from dataclasses import replace

from routing_opt.solvers.greedy import GreedySolver, ImprovedGreedySolver
from routing_opt.validation import validate_solution


def test_official_greedy_is_valid_and_uses_first_engineer(small_problem):
    solution = GreedySolver().solve(small_problem, seed=42)
    report = validate_solution(small_problem, solution)
    assert report.valid, report.errors
    assert [stop.job_id for stop in solution.routes[0].stops] == ["j1", "j2"]
    assert [stop.job_id for stop in solution.routes[1].stops] == ["j3"]
    assert solution.metrics.completed_jobs == 3


def test_improved_greedy_is_valid(small_problem):
    solution = ImprovedGreedySolver().solve(small_problem, seed=7)
    assert validate_solution(small_problem, solution).valid


def test_validator_rejects_corrupted_metric(small_problem):
    solution = GreedySolver().solve(small_problem)
    corrupted = replace(
        solution,
        metrics=replace(solution.metrics, completed_jobs=solution.metrics.completed_jobs + 1),
    )
    report = validate_solution(small_problem, corrupted)
    assert not report.valid
    assert any("completed_jobs" in error for error in report.errors)
