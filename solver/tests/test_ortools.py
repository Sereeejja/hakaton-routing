from __future__ import annotations

import pytest

from routing_opt.solvers.ortools_solver import OrToolsSolver
from routing_opt.synthetic import SyntheticConfig, generate_synthetic_problem
from routing_opt.validation import validate_solution

pytest.importorskip("ortools")


def test_ortools_solution_is_valid(small_problem):
    solution = OrToolsSolver().solve(small_problem, time_limit_sec=0.2, seed=42)
    report = validate_solution(small_problem, solution)
    assert report.valid, report.errors
    assert solution.metrics.completed_jobs == 3


def test_ortools_can_drop_impossible_optional_jobs():
    problem = generate_synthetic_problem(
        SyntheticConfig(job_count=3, engineer_count=3, conflict_share=1.0, seed=42)
    )
    solution = OrToolsSolver().solve(problem, time_limit_sec=0.2, seed=42)
    report = validate_solution(problem, solution)
    assert report.valid, report.errors
    assert solution.metrics.completed_jobs == 0
    assert solution.metrics.unassigned_jobs == 3
