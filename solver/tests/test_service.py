from __future__ import annotations

import pytest

from routing_opt.service import create_solver, solve
from routing_opt.validation import validate_solution


@pytest.mark.parametrize("solver_name", ("greedy", "improved_greedy", "hgs"))
def test_backend_facade_returns_valid_solution(small_problem, solver_name):
    solution = solve(
        small_problem,
        solver_name=solver_name,
        time_limit_sec=0.05,
        seed=42,
    )
    assert validate_solution(small_problem, solution).valid


def test_backend_facade_rejects_unknown_solver():
    with pytest.raises(ValueError, match="Unknown solver"):
        create_solver("not-a-solver")  # type: ignore[arg-type]
