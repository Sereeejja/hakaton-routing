from __future__ import annotations

import argparse
from pathlib import Path

from .benchmark import run_benchmark, save_benchmark
from .serialization import save_solution_json
from .solvers import GreedySolver, HybridGeneticSolver, ImprovedGreedySolver, OrToolsSolver
from .synthetic import SyntheticConfig, generate_synthetic_problem
from .validation import validate_solution
from .visualization import save_benchmark_html, save_gantt, save_route_map


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the routing optimization demo")
    parser.add_argument("--jobs", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--time-limit", type=float, default=3.0)
    parser.add_argument("--output", type=Path, default=Path("outputs/demo"))
    parser.add_argument("--skip-ortools", action="store_true")
    args = parser.parse_args()

    problem = generate_synthetic_problem(SyntheticConfig(job_count=args.jobs, seed=args.seed))
    solvers = [GreedySolver(), ImprovedGreedySolver()]
    if not args.skip_ortools:
        solvers.append(OrToolsSolver())
    solvers.append(HybridGeneticSolver())
    records, solutions = run_benchmark(
        problem,
        solvers,
        time_limit_sec=args.time_limit,
        seeds=(args.seed, args.seed + 1, args.seed + 2),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    save_benchmark(records, args.output / "benchmark.csv")
    save_benchmark_html(records, args.output / "benchmark.html")
    for solution in solutions:
        suffix = f"{solution.solver_name}-{solution.seed}"
        save_solution_json(solution, args.output / f"solution-{suffix}.json")
    if solutions:
        best = min(
            solutions,
            key=lambda solution: (
                solution.metrics.unassigned_urgent_jobs,
                solution.metrics.unassigned_jobs,
                solution.metrics.active_engineers,
                solution.metrics.total_distance_km,
            ),
        )
        assert validate_solution(problem, best).valid
        save_route_map(problem, best, args.output / "map.html")
        save_gantt(best, args.output / "gantt.html")
    print(f"Saved {len(records)} benchmark runs to {args.output}")


if __name__ == "__main__":
    main()
