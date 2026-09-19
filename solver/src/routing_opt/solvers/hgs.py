from __future__ import annotations

import random
from dataclasses import dataclass
from itertools import pairwise
from time import perf_counter

from routing_opt.domain import Priority, Problem, Route, Solution
from routing_opt.scheduling import evaluate_route

from .base import Solver
from .common import build_solution
from .greedy import ImprovedGreedySolver


@dataclass(slots=True)
class _Individual:
    routes: list[list[str]]
    unassigned: set[str]
    score: float = float("inf")
    feasible: bool = False
    violation: int = 0
    distance: float = 0.0
    active: int = 0

    def clone(self) -> _Individual:
        return _Individual(
            routes=[list(route) for route in self.routes],
            unassigned=set(self.unassigned),
            score=self.score,
            feasible=self.feasible,
            violation=self.violation,
            distance=self.distance,
            active=self.active,
        )


@dataclass(frozen=True, slots=True)
class HgsConfig:
    population_size: int = 24
    offspring_per_generation: int = 8
    max_generations: int = 2_000
    local_search_moves: int = 40
    penalty_update_interval: int = 20
    target_feasible_ratio: float = 0.30
    initial_violation_penalty: float = 100_000_000.0
    diversity_weight: float = 10_000.0


class HybridGeneticSolver(Solver):
    """Compact HGS: route crossover, local search, diversity, and adaptive penalties."""

    name = "hgs"

    def __init__(self, config: HgsConfig | None = None) -> None:
        self.config = config or HgsConfig()

    def solve(self, problem: Problem, time_limit_sec: float = 10, seed: int = 42) -> Solution:
        started_at = perf_counter()
        deadline = started_at + max(0.01, time_limit_sec)
        rng = random.Random(seed)
        penalty = self.config.initial_violation_penalty
        population = self._initial_population(problem, rng, penalty, deadline)
        feasible_population = [individual for individual in population if individual.feasible]
        best = min(feasible_population, key=lambda item: item.score).clone()
        generation = 0

        while generation < self.config.max_generations and perf_counter() < deadline:
            generation += 1
            offspring: list[_Individual] = []
            for _ in range(self.config.offspring_per_generation):
                if perf_counter() >= deadline:
                    break
                parent_a = self._tournament(population, rng)
                parent_b = self._tournament(population, rng)
                child = self._crossover(problem, parent_a, parent_b, rng, penalty)
                self._mutate(child, rng)
                self._evaluate(problem, child, penalty)
                child = self._local_search(problem, child, rng, penalty, deadline)
                offspring.append(child)
                if child.feasible and child.score < best.score:
                    best = child.clone()
            population.extend(offspring)
            population = self._survivor_selection(population)
            if generation % self.config.penalty_update_interval == 0:
                feasible_ratio = sum(item.feasible for item in population) / len(population)
                if feasible_ratio < self.config.target_feasible_ratio:
                    penalty *= 1.2
                else:
                    penalty = max(1.0, penalty * 0.85)
                for individual in population:
                    self._evaluate(problem, individual, penalty)

        routes = self._build_routes(problem, best)
        assigned = {job_id for route in best.routes for job_id in route}
        return build_solution(
            problem=problem,
            solver_name=self.name,
            routes=routes,
            assigned_job_ids=assigned,
            started_at=started_at,
            seed=seed,
            objective_value=best.score,
            metadata={
                "generations": generation,
                "population_size": len(population),
                "final_violation_penalty": penalty,
                "operators": ["selective_route_crossover", "relocate", "swap", "2-opt", "2-opt*"],
            },
        )

    def _initial_population(
        self,
        problem: Problem,
        rng: random.Random,
        penalty: float,
        deadline: float,
    ) -> list[_Individual]:
        greedy = ImprovedGreedySolver().solve(
            problem, time_limit_sec=0, seed=rng.randrange(1 << 30)
        )
        engineer_index = {engineer.id: index for index, engineer in enumerate(problem.engineers)}
        routes = [[] for _ in problem.engineers]
        for route in greedy.routes:
            routes[engineer_index[route.engineer_id]] = [stop.job_id for stop in route.stops]
        eligible = {job.id for job in problem.jobs if job.planning_eligible}
        base = _Individual(routes=routes, unassigned=eligible - {j for r in routes for j in r})
        self._evaluate(problem, base, penalty)
        population = [base]
        while len(population) < self.config.population_size and perf_counter() < deadline:
            individual = self._random_individual(problem, rng)
            self._evaluate(problem, individual, penalty)
            individual = self._local_search(problem, individual, rng, penalty, deadline)
            population.append(individual)
        return population

    def _random_individual(self, problem: Problem, rng: random.Random) -> _Individual:
        routes = [[] for _ in problem.engineers]
        unassigned: set[str] = set()
        jobs = [job for job in problem.jobs if job.planning_eligible]
        rng.shuffle(jobs)
        for job in jobs:
            compatible = [
                index
                for index, engineer in enumerate(problem.engineers)
                if engineer.is_compatible(job)
            ]
            if not compatible or rng.random() < 0.08:
                unassigned.add(job.id)
                continue
            route_index = rng.choice(compatible)
            position = rng.randrange(len(routes[route_index]) + 1)
            routes[route_index].insert(position, job.id)
        return _Individual(routes=routes, unassigned=unassigned)

    def _evaluate(self, problem: Problem, individual: _Individual, penalty: float) -> None:
        violation = 0
        distance = 0.0
        travel = 0
        waiting = 0
        active = 0
        workloads: list[int] = []
        for engineer, route_ids in zip(problem.engineers, individual.routes):
            evaluation = evaluate_route(problem, engineer, route_ids, allow_violations=True)
            violation += evaluation.time_window_violation + evaluation.shift_violation
            violation += evaluation.compatibility_violations * 10_000
            violation += evaluation.unreachable_legs * 10_000
            distance += evaluation.route.total_distance_km
            travel += evaluation.route.total_travel_minutes
            waiting += evaluation.route.total_waiting_minutes
            active += bool(route_ids)
            if route_ids:
                workloads.append(
                    evaluation.route.total_service_minutes + evaluation.route.total_travel_minutes
                )
        unassigned_jobs = [problem.jobs_by_id[job_id] for job_id in individual.unassigned]
        urgent = sum(job.priority is Priority.URGENT for job in unassigned_jobs)
        changes = sum(
            previous != problem.engineers[route_index].id
            for route_index, route in enumerate(individual.routes)
            for job_id in route
            if (previous := problem.previous_assignments.get(job_id)) is not None
        )
        individual.violation = violation
        individual.feasible = violation == 0
        individual.distance = distance
        individual.active = active
        workload_range = max(workloads) - min(workloads) if len(workloads) > 1 else 0
        individual.score = (
            urgent * 1_000_000_000_000_000
            + len(individual.unassigned) * 1_000_000_000_000
            + active * 1_000_000_000
            + distance * 10_000
            + travel * 10
            + waiting
            + workload_range
            + changes
            + violation * penalty
        )

    def _crossover(
        self,
        problem: Problem,
        parent_a: _Individual,
        parent_b: _Individual,
        rng: random.Random,
        penalty: float,
    ) -> _Individual:
        route_count = len(problem.engineers)
        keep_count = rng.randint(1, max(1, route_count // 2))
        kept_indices = set(rng.sample(range(route_count), keep_count))
        child_routes = [
            list(parent_a.routes[i]) if i in kept_indices else [] for i in range(route_count)
        ]
        present = {job_id for route in child_routes for job_id in route}
        ordered_remaining = [
            job_id for route in parent_b.routes for job_id in route if job_id not in present
        ]
        ordered_remaining.extend(job_id for job_id in parent_b.unassigned if job_id not in present)
        eligible = {job.id for job in problem.jobs if job.planning_eligible}
        ordered_remaining.extend(sorted(eligible - present - set(ordered_remaining)))
        child = _Individual(routes=child_routes, unassigned=set())
        for job_id in ordered_remaining:
            self._insert_best(problem, child, job_id, penalty, allow_unassigned=True)
        return child

    def _insert_best(
        self,
        problem: Problem,
        individual: _Individual,
        job_id: str,
        penalty: float,
        *,
        allow_unassigned: bool,
    ) -> None:
        job = problem.jobs_by_id[job_id]
        best_score = float("inf")
        best_location: tuple[int, int] | None = None
        for route_index, engineer in enumerate(problem.engineers):
            if not engineer.is_compatible(job):
                continue
            for position in range(len(individual.routes[route_index]) + 1):
                trial = individual.clone()
                trial.unassigned.discard(job_id)
                trial.routes[route_index].insert(position, job_id)
                self._evaluate(problem, trial, penalty)
                if trial.score < best_score:
                    best_score = trial.score
                    best_location = (route_index, position)
        if allow_unassigned:
            trial = individual.clone()
            trial.unassigned.add(job_id)
            self._evaluate(problem, trial, penalty)
            if trial.score <= best_score:
                individual.unassigned.add(job_id)
                return
        if best_location is None:
            individual.unassigned.add(job_id)
        else:
            individual.unassigned.discard(job_id)
            route_index, position = best_location
            individual.routes[route_index].insert(position, job_id)

    def _mutate(self, individual: _Individual, rng: random.Random) -> None:
        non_empty = [index for index, route in enumerate(individual.routes) if route]
        if non_empty and rng.random() < 0.7:
            source = rng.choice(non_empty)
            job_id = individual.routes[source].pop(rng.randrange(len(individual.routes[source])))
            target = rng.randrange(len(individual.routes))
            position = rng.randrange(len(individual.routes[target]) + 1)
            individual.routes[target].insert(position, job_id)
        non_empty = [index for index, route in enumerate(individual.routes) if route]
        if len(non_empty) >= 2 and rng.random() < 0.4:
            first, second = rng.sample(non_empty, 2)
            i = rng.randrange(len(individual.routes[first]))
            j = rng.randrange(len(individual.routes[second]))
            individual.routes[first][i], individual.routes[second][j] = (
                individual.routes[second][j],
                individual.routes[first][i],
            )

    def _local_search(
        self,
        problem: Problem,
        individual: _Individual,
        rng: random.Random,
        penalty: float,
        deadline: float,
    ) -> _Individual:
        current = individual.clone()
        self._evaluate(problem, current, penalty)
        for move_number in range(self.config.local_search_moves):
            if perf_counter() >= deadline:
                break
            candidate = current.clone()
            operator = move_number % 4
            changed = False
            non_empty = [i for i, route in enumerate(candidate.routes) if route]
            if operator == 0 and non_empty:  # relocate
                source = rng.choice(non_empty)
                job = candidate.routes[source].pop(rng.randrange(len(candidate.routes[source])))
                target = rng.randrange(len(candidate.routes))
                candidate.routes[target].insert(
                    rng.randrange(len(candidate.routes[target]) + 1), job
                )
                changed = True
            elif operator == 1 and len(non_empty) >= 2:  # swap
                first, second = rng.sample(non_empty, 2)
                i, j = (
                    rng.randrange(len(candidate.routes[first])),
                    rng.randrange(len(candidate.routes[second])),
                )
                candidate.routes[first][i], candidate.routes[second][j] = (
                    candidate.routes[second][j],
                    candidate.routes[first][i],
                )
                changed = True
            elif operator == 2:  # 2-opt
                long_routes = [i for i, route in enumerate(candidate.routes) if len(route) >= 3]
                if long_routes:
                    route_index = rng.choice(long_routes)
                    i, j = sorted(rng.sample(range(len(candidate.routes[route_index])), 2))
                    candidate.routes[route_index][i : j + 1] = reversed(
                        candidate.routes[route_index][i : j + 1]
                    )
                    changed = True
            elif operator == 3 and len(non_empty) >= 2:  # 2-opt*
                first, second = rng.sample(non_empty, 2)
                cut_a = rng.randrange(len(candidate.routes[first]) + 1)
                cut_b = rng.randrange(len(candidate.routes[second]) + 1)
                tail_a = candidate.routes[first][cut_a:]
                tail_b = candidate.routes[second][cut_b:]
                candidate.routes[first][cut_a:] = tail_b
                candidate.routes[second][cut_b:] = tail_a
                changed = True
            if not changed:
                continue
            self._evaluate(problem, candidate, penalty)
            if candidate.score < current.score:
                current = candidate
        return current

    def _tournament(self, population: list[_Individual], rng: random.Random) -> _Individual:
        candidates = rng.sample(population, min(3, len(population)))
        return min(candidates, key=lambda item: item.score)

    def _survivor_selection(self, population: list[_Individual]) -> list[_Individual]:
        unique: dict[tuple[tuple[str, ...], ...], _Individual] = {}
        for individual in population:
            signature = tuple(tuple(route) for route in individual.routes)
            if signature not in unique or individual.score < unique[signature].score:
                unique[signature] = individual
        items = list(unique.values())
        if len(items) <= self.config.population_size:
            return items
        adjusted = []
        for individual in items:
            distances = sorted(
                self._diversity(individual, other) for other in items if other is not individual
            )
            diversity = sum(distances[: min(3, len(distances))]) / max(1, min(3, len(distances)))
            adjusted.append(
                (individual.score - diversity * self.config.diversity_weight, individual)
            )
        adjusted.sort(key=lambda item: item[0])
        return [item[1] for item in adjusted[: self.config.population_size]]

    @staticmethod
    def _diversity(first: _Individual, second: _Individual) -> float:
        def edges(individual: _Individual) -> set[tuple[str, str]]:
            result = set()
            for route in individual.routes:
                result.update(pairwise(route))
            return result

        first_edges, second_edges = edges(first), edges(second)
        union = first_edges | second_edges
        edge_distance = 0.0 if not union else len(first_edges ^ second_edges) / len(union)
        return edge_distance + len(first.unassigned ^ second.unassigned) / max(
            1, len(first.unassigned | second.unassigned)
        )

    @staticmethod
    def _build_routes(problem: Problem, individual: _Individual) -> list[Route]:
        result = []
        for engineer, job_ids in zip(problem.engineers, individual.routes):
            evaluation = evaluate_route(problem, engineer, job_ids)
            if not evaluation.feasible:
                raise RuntimeError("HGS attempted to publish an infeasible individual")
            result.append(evaluation.route)
        return result
