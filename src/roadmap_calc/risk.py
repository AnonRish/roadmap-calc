"""Look-ups and conservative conventions on the roadmap's risk table.

The source gives only five rows (speedups 1.15x, 1.5x, 3x, 10x, 22x). Anything between rows
is **this tool's convention**, not a number from the source; every result says which it is.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from fractions import Fraction
from itertools import pairwise
from typing import Literal

from .data import RiskModifier, RiskRow

Field = Literal["marginal_risk", "p_scheming"]
Mode = Literal["loglinear", "conservative", "previous"]
Combine = Literal["max", "multiply"]


class OutOfRange(ValueError):
    """The requested speedup is outside the table."""


@dataclass(frozen=True)
class Estimate:
    """A risk percentage and how it was obtained.

    ``kind``: ``row`` (an exact table row), ``interpolated`` (between rows, by the stated
    convention) or ``upper_bound`` (the table only bounds it from above).
    """

    pct: float
    kind: Literal["row", "interpolated", "upper_bound"]
    detail: str


def to_fraction(value: float | int | str | Fraction) -> Fraction:
    """Exact fraction from a number as it was *written* (``1.15`` is 23/20, not a float)."""
    if isinstance(value, Fraction):
        return value
    return Fraction(str(value))


def _bound_of(row: RiskRow, field: Field) -> tuple[Fraction, bool]:
    bound = row.marginal_risk if field == "marginal_risk" else row.p_scheming
    return bound.pct, bound.op == "<"


def lookup(
    table: Sequence[RiskRow],
    speedup: float | int | str | Fraction,
    field: Field = "marginal_risk",
    mode: Mode = "loglinear",
) -> Estimate:
    """Risk at an AI R&D speedup. Rows are exact; between rows ``mode`` decides.

    ``loglinear`` interpolates linearly in log(speedup); ``conservative`` takes the next row
    up; ``previous`` takes the row below. Below the first row the table says "under X%".
    """
    s = to_fraction(speedup)
    if s < 1:
        raise ValueError(f"speedup must be at least 1, got {speedup}")
    first, last = table[0], table[-1]
    if s > last.speedup:
        raise OutOfRange(f"the table ends at {float(last.speedup):g}x; got {float(s):g}x")
    for row in table:
        if s == row.speedup:
            value, is_bound = _bound_of(row, field)
            return Estimate(float(value), _kind(is_bound), f"table row at {float(row.speedup):g}x")
    if s < first.speedup:
        value, _ = _bound_of(first, field)
        detail = (
            f"below the first row ({float(first.speedup):g}x): "
            f"the table says under {float(value):g}%"
        )
        return Estimate(float(value), "upper_bound", detail)
    for lower, upper in pairwise(table):
        if lower.speedup < s < upper.speedup:
            lo_value, lo_bound = _bound_of(lower, field)
            hi_value, hi_bound = _bound_of(upper, field)
            span = f"between {float(lower.speedup):g}x and {float(upper.speedup):g}x"
            if mode == "conservative":
                return Estimate(float(hi_value), _kind(hi_bound), f"next row up, {span}")
            if mode == "previous":
                return Estimate(float(lo_value), _kind(lo_bound), f"previous row, {span}")
            t = math.log(s / lower.speedup) / math.log(upper.speedup / lower.speedup)
            pct = (1 - t) * float(lo_value) + t * float(hi_value)
            kind: Literal["interpolated", "upper_bound"] = (
                "upper_bound" if lo_bound or hi_bound else "interpolated"
            )
            return Estimate(pct, kind, f"log-linear interpolation {span}")
    raise AssertionError("unreachable: s is inside the table")  # pragma: no cover


def _kind(is_bound: bool) -> Literal["row", "upper_bound"]:
    return "upper_bound" if is_bound else "row"


def apply_modifiers(
    pct: float,
    modifier_ids: Iterable[str],
    modifiers: Sequence[RiskModifier],
    combine: Combine = "max",
) -> float:
    """Scale a risk percentage by the roadmap's conditional adjustments (capped at 100%).

    The source gives one factor per observation and does not say how several combine:
    ``max`` (default) applies only the largest factor; ``multiply`` compounds them.
    """
    by_id = {m.id: m for m in modifiers}
    chosen: list[Fraction] = []
    for modifier_id in modifier_ids:
        if modifier_id not in by_id:
            raise KeyError(f"unknown modifier {modifier_id!r}; known: {sorted(by_id)}")
        chosen.append(by_id[modifier_id].factor)
    if not chosen:
        return min(pct, 100.0)
    factor = max(chosen) if combine == "max" else math.prod(chosen)
    return min(pct * float(factor), 100.0)


def latest_threshold_within(
    table: Sequence[RiskRow], max_pct: float | int | str | Fraction
) -> RiskRow | None:
    """The highest table row whose marginal risk is guaranteed to be at most ``max_pct``.

    ``<1%`` counts as 1% (the table only bounds it). Returns ``None`` if even the first row
    is not guaranteed to fit.
    """
    limit = to_fraction(max_pct)
    fitting = [row for row in table if row.marginal_risk.pct <= limit]
    return fitting[-1] if fitting else None
