from __future__ import annotations

from typing import Literal

from .domain import Problem, Solution
from .solvers import (
    GreedySolver,
    HgsConfig,
    HybridGeneticSolver,
    ImprovedGreedySolver,
    OrToolsSolver,
    Solver,
)

SolverName = Literal["greedy", "improved_greedy", "ortools", "hgs"]


def create_solver(name: SolverName, *, hgs_config: HgsConfig | None = None) -> Solver:
    """Build a solver by the stable name used in the backend contract."""

    if name == "greedy":
        return GreedySolver()
    if name == "improved_greedy":
        return ImprovedGreedySolver()
    if name == "ortools":
        return OrToolsSolver()
    if name == "hgs":
        return HybridGeneticSolver(hgs_config)
    raise ValueError(f"Unknown solver name: {name}")


def solve(
    problem: Problem,
    *,
    solver_name: SolverName = "ortools",
    time_limit_sec: float = 10,
    seed: int = 42,
    hgs_config: HgsConfig | None = None,
) -> Solution:
    """Backend-facing facade; domain construction and serialization stay outside."""

    solver = create_solver(solver_name, hgs_config=hgs_config)
    return solver.solve(problem, time_limit_sec=time_limit_sec, seed=seed)
