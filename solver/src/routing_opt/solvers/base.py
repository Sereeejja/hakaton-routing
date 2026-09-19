from __future__ import annotations

from abc import ABC, abstractmethod

from routing_opt.domain import Problem, Solution


class Solver(ABC):
    """Common contract implemented by every planning algorithm."""

    name: str

    @abstractmethod
    def solve(self, problem: Problem, time_limit_sec: float = 10, seed: int = 42) -> Solution:
        raise NotImplementedError


class MissingDependencyError(RuntimeError):
    pass
