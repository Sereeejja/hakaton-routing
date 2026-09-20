"""Autonomous optimization engine for field-engineer routing."""

from .domain import (
    Engineer,
    Job,
    Location,
    Priority,
    Problem,
    Route,
    Skill,
    Solution,
    Stop,
    Transport,
    TravelMatrices,
)
from .service import solve
from .validation import validate_solution

__all__ = [
    "Engineer",
    "Job",
    "Location",
    "Priority",
    "Problem",
    "Route",
    "Skill",
    "Solution",
    "Stop",
    "Transport",
    "TravelMatrices",
    "solve",
    "validate_solution",
]

__version__ = "0.1.0"
