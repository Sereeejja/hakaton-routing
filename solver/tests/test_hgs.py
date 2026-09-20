from __future__ import annotations

from routing_opt.solvers.hgs import HgsConfig, HybridGeneticSolver
from routing_opt.validation import validate_solution


def test_hgs_publishes_only_valid_solution(small_problem):
    solver = HybridGeneticSolver(
        HgsConfig(population_size=6, offspring_per_generation=2, local_search_moves=5)
    )
    solution = solver.solve(small_problem, time_limit_sec=0.15, seed=123)
    report = validate_solution(small_problem, solution)
    assert report.valid, report.errors
    assert solution.metadata["operators"] == [
        "selective_route_crossover",
        "relocate",
        "swap",
        "2-opt",
        "2-opt*",
    ]
