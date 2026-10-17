"""Effort portfolios: exact apportionment to headcount and interpolation between phases."""

from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction
from typing import Literal

from .data import Portfolio

Level = Literal["areas", "leaves"]


def apportion(percents: Sequence[int | Fraction], total: int) -> list[int]:
    """Split ``total`` whole units by ``percents`` using the largest-remainder method.

    The result always sums to ``total`` and each entry is within 1 of its exact share.
    Ties between equal remainders go to the earlier entry.
    """
    if total < 0:
        raise ValueError(f"total must be non-negative, got {total}")
    if any(p < 0 for p in percents):
        raise ValueError("percentages must be non-negative")
    if sum(Fraction(p) for p in percents) != 100:
        raise ValueError("percentages must sum to exactly 100")
    exact = [Fraction(total) * Fraction(p) / 100 for p in percents]
    parts = [e // 1 for e in exact]
    leftover = total - sum(parts)
    by_remainder = sorted(range(len(parts)), key=lambda i: (-(exact[i] - parts[i]), i))
    for index in by_remainder[:leftover]:
        parts[index] += 1
    return [int(p) for p in parts]


def entries(portfolio: Portfolio, level: Level = "areas") -> list[tuple[str, int]]:
    """``(name, pct)`` pairs: top-level areas, or leaves (sub-areas where they exist)."""
    if level == "areas":
        return [(a.id, a.pct) for a in portfolio.areas]
    items: list[tuple[str, int]] = []
    for area in portfolio.areas:
        if area.children:
            items.extend((f"{area.id}/{c.id}", c.pct) for c in area.children)
        else:
            items.append((area.id, area.pct))
    return items


def allocate(portfolio: Portfolio, headcount: int, level: Level = "areas") -> list[tuple[str, int]]:
    """Whole-person allocation of ``headcount`` following ``portfolio``."""
    pairs = entries(portfolio, level)
    counts = apportion([pct for _, pct in pairs], headcount)
    return [(name, count) for (name, _), count in zip(pairs, counts, strict=True)]


def interpolate(
    first: Portfolio, second: Portfolio, t: Fraction | int
) -> list[tuple[str, Fraction]]:
    """Blend two portfolios at ``t`` (0 = first, 1 = second) over the union of their areas.

    The roadmap suggests interpolating between its phase priorities to see how priorities
    evolve; matching areas by identifier (and treating a missing area as 0%) is this tool's
    convention. The weights always sum to exactly 100.
    """
    weight = Fraction(t)
    if not 0 <= weight <= 1:
        raise ValueError(f"t must be between 0 and 1, got {t}")
    before = {a.id: Fraction(a.pct) for a in first.areas}
    after = {a.id: Fraction(a.pct) for a in second.areas}
    names = [a.id for a in first.areas] + [a.id for a in second.areas if a.id not in before]
    return [
        (name, (1 - weight) * before.get(name, Fraction(0)) + weight * after.get(name, Fraction(0)))
        for name in names
    ]


def shifts(first: Portfolio, second: Portfolio) -> list[tuple[str, int, int]]:
    """``(area, pct in first, pct in second)`` for every area in either portfolio."""
    before = {a.id: a.pct for a in first.areas}
    after = {a.id: a.pct for a in second.areas}
    names = [a.id for a in first.areas] + [a.id for a in second.areas if a.id not in before]
    return [(name, before.get(name, 0), after.get(name, 0)) for name in names]
