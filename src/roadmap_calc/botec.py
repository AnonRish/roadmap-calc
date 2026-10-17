"""The roadmap's safety-acceleration back-of-envelope arithmetic, as plain functions."""

from __future__ import annotations

import math


def _positive(value: float, name: str) -> None:
    if not value > 0 or math.isinf(value):
        raise ValueError(f"{name} must be positive and finite, got {value!r}")


def safety_acceleration(ai_rd_accel: float, exponent: float) -> float:
    """Safety R&D acceleration modelled as ``ai_rd_accel ** exponent``."""
    _positive(ai_rd_accel, "ai_rd_accel")
    return math.pow(ai_rd_accel, exponent)


def implied_input(target: float, exponent: float) -> float:
    """The AI R&D acceleration that would give ``target`` safety acceleration."""
    _positive(target, "target")
    if exponent == 0:
        raise ValueError("exponent must be non-zero")
    return math.pow(target, 1.0 / exponent)


def exp_time_average(start: float, end: float, power: float = 1.0) -> float:
    """Time-average of ``A(t) ** power`` when ``A`` grows exponentially from ``start`` to ``end``.

    With ``A(t) = start * (end / start) ** t`` for ``t`` in [0, 1] the average is
    ``(end**power - start**power) / (power * ln(end / start))``. This is evaluated as
    ``start**power * expm1(x) / x`` with ``x = power * ln(end / start)``, which stays accurate
    when ``start`` and ``end`` are nearly equal (the textbook form cancels catastrophically).
    """
    _positive(start, "start")
    _positive(end, "end")
    if power == 0:
        return 1.0
    ratio = (end - start) / start
    # log1p keeps full precision for nearly equal endpoints; the log difference handles huge ratios.
    growth = math.log1p(ratio) if math.isfinite(ratio) else math.log(end) - math.log(start)
    x = power * growth
    if x == 0:
        return math.pow(start, power)
    try:
        return math.pow(start, power) * math.expm1(x) / x
    except OverflowError as exc:
        raise ValueError("growth range is too large for double precision") from exc


def numeric_exp_time_average(
    start: float, end: float, power: float = 1.0, steps: int = 20_000
) -> float:
    """Same quantity by Simpson's rule (an independent check of :func:`exp_time_average`)."""
    _positive(start, "start")
    _positive(end, "end")
    if steps < 2 or steps % 2:
        raise ValueError("steps must be an even integer >= 2")

    def f(t: float) -> float:
        return math.pow(start * math.pow(end / start, t), power)

    h = 1.0 / steps
    odd = math.fsum(f((2 * i - 1) * h) for i in range(1, steps // 2 + 1))
    even = math.fsum(f(2 * i * h) for i in range(1, steps // 2))
    return (f(0.0) + f(1.0) + 4.0 * odd + 2.0 * even) * h / 3.0


def production_acceleration(
    labor: float, compute: float = 1.0, labor_exponent: float = 0.75, compute_exponent: float = 0.25
) -> float:
    """``labor ** labor_exponent * compute ** compute_exponent`` (compute held fixed by default)."""
    _positive(labor, "labor")
    _positive(compute, "compute")
    return math.pow(labor, labor_exponent) * math.pow(compute, compute_exponent)


def extra_years(average_acceleration: float, years: float) -> float:
    """Additional years of safety progress beyond calendar time: ``(average - 1) * years``."""
    return (average_acceleration - 1.0) * years


def equivalent_years(acceleration: float, years: float) -> float:
    """Years of progress delivered in ``years`` of calendar time at ``acceleration``."""
    return acceleration * years
