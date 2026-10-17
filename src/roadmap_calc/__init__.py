"""roadmap-calc: tested calculators and consistency checks for the AI 2040 alignment roadmap."""

from __future__ import annotations

__version__ = "0.1.0"

from .botec import (
    equivalent_years,
    exp_time_average,
    extra_years,
    implied_input,
    numeric_exp_time_average,
    production_acceleration,
    safety_acceleration,
)
from .data import DataError, RoadmapData, check_data, load_data, parse_data
from .portfolio import allocate, apportion, interpolate
from .reproduce import Claim, Status, reproduce_all, reproduce_botec, reproduce_portfolios
from .risk import Estimate, OutOfRange, apply_modifiers, latest_threshold_within, lookup

__all__ = [
    "Claim",
    "DataError",
    "Estimate",
    "OutOfRange",
    "RoadmapData",
    "Status",
    "__version__",
    "allocate",
    "apply_modifiers",
    "apportion",
    "check_data",
    "equivalent_years",
    "exp_time_average",
    "extra_years",
    "implied_input",
    "interpolate",
    "latest_threshold_within",
    "load_data",
    "lookup",
    "numeric_exp_time_average",
    "parse_data",
    "production_acceleration",
    "reproduce_all",
    "reproduce_botec",
    "reproduce_portfolios",
    "safety_acceleration",
]
