"""Recompute every checkable number in the roadmap from its own stated inputs.

Each *claim* is a figure the page states. For each we list the recomputations that are
plausible readings of the page (``checks``) and report whether any reproduces the stated
value. Nothing here asserts that the source is wrong: a figure that does not reproduce under
the stated formula may use inputs or definitions that the page does not spell out.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from . import botec as bt
from .data import RoadmapData

Status = Literal["reproduced", "approximately_reproduced", "not_reproduced"]
APPROXIMATE_RELATIVE = 0.10


@dataclass(frozen=True)
class Check:
    """One way of recomputing a stated figure."""

    assumption: str
    value: float


@dataclass(frozen=True)
class Claim:
    """A stated figure and its candidate recomputations.

    ``half_unit`` is the rounding tolerance of the stated figure (half of its last digit).
    ``exact`` claims (sums of percentages) must match with no tolerance.
    """

    id: str
    description: str
    stated: float
    half_unit: float
    unit: str
    checks: tuple[Check, ...]
    exact: bool = False

    @property
    def best(self) -> Check:
        return min(self.checks, key=lambda c: abs(c.value - self.stated))

    @property
    def difference(self) -> float:
        return self.best.value - self.stated

    @property
    def relative_difference(self) -> float:
        return abs(self.difference) / abs(self.stated) if self.stated else abs(self.difference)

    @property
    def matching(self) -> tuple[Check, ...]:
        """Recomputations that reproduce the stated figure to its rounding precision."""
        tolerance = 0.0 if self.exact else self.half_unit + 1e-9
        return tuple(c for c in self.checks if abs(c.value - self.stated) <= tolerance)

    @property
    def status(self) -> Status:
        if self.matching:
            return "reproduced"
        if not self.exact and self.relative_difference <= APPROXIMATE_RELATIVE:
            return "approximately_reproduced"
        return "not_reproduced"


def reproduce_botec(data: RoadmapData) -> list[Claim]:
    """The safety-acceleration arithmetic of the roadmap's "expected acceleration" section."""
    b = data.botec
    stated = {k: float(v) for k, v in b.stated.items()}
    k, k_min = float(b.safety_exponent_itai_to_sc), float(b.safety_exponent_min_h)
    labor_exp = float(b.production_labor_exponent)
    x_itai, x_sc = float(b.itai_ai_rd_accel), float(b.superhuman_coder_ai_rd_accel)
    min_h = float(b.min_h_safety_labor_accel)
    years_1, years_2 = float(b.years_itai_to_sc), float(b.years_sc_to_min_h)
    months = float(b.harness_months)

    low_re, high_re = bt.safety_acceleration(x_itai, k), bt.safety_acceleration(x_sc, k)
    low_st = stated["safety_accel_at_itai"]
    high_st = stated["safety_accel_at_superhuman_coder"]
    cap = bt.safety_acceleration(min_h, k_min)

    rough_re = bt.exp_time_average(low_re, high_re)
    rough_st = bt.exp_time_average(low_st, high_st)
    prod_st = bt.exp_time_average(low_st, high_st, labor_exp)
    prod_re = bt.exp_time_average(low_re, high_re, labor_exp)
    mh_st = bt.exp_time_average(high_st, cap, labor_exp)
    mh_re = bt.exp_time_average(high_re, cap, labor_exp)
    mh_plain = bt.exp_time_average(high_re, cap)

    def claim(name: str, text: str, half: float, unit: str, *checks: tuple[str, float]) -> Claim:
        return Claim(name, text, stated[name], half, unit, tuple(Check(a, v) for a, v in checks))

    return [
        claim(
            "safety_accel_at_itai",
            f"Safety acceleration at ITAI, from {x_itai:g}x AI R&D acceleration at exponent {k:g}",
            0.05,
            "x",
            (f"{x_itai:g} ** {k:g}", low_re),
        ),
        claim(
            "safety_accel_at_superhuman_coder",
            f"Safety acceleration at superhuman coder, from {x_sc:g}x at exponent {k:g}",
            0.05,
            "x",
            (f"{x_sc:g} ** {k:g}", high_re),
        ),
        claim(
            "avg_accel_itai_to_sc_rough",
            "Average safety acceleration ITAI to superhuman coder (stated as roughly 3x)",
            0.5,
            "x",
            ("exponential-in-time average of the recomputed endpoints", rough_re),
            ("exponential-in-time average of the stated endpoints", rough_st),
            ("stated endpoints, production function labor ** 0.75", prod_st),
        ),
        claim(
            "avg_accel_itai_to_sc_production",
            "Average with production function labor ** 0.75 * compute ** 0.25 (compute fixed)",
            0.05,
            "x",
            ("stated endpoints 2.2 and 6.7, exponential-in-time average", prod_st),
            ("recomputed endpoints, exponential-in-time average", prod_re),
        ),
        claim(
            "extra_years_itai_to_sc",
            "Extra years of safety progress between ITAI and superhuman coder (about 1 year)",
            0.5,
            "years",
            (
                "(stated rough average 3 - 1) x years",
                bt.extra_years(stated["avg_accel_itai_to_sc_rough"], years_1),
            ),
            (
                "(production average from the stated endpoints - 1) x years",
                bt.extra_years(prod_st, years_1),
            ),
        ),
        claim(
            "safety_accel_at_min_h",
            f"Safety acceleration of Min-H, from {min_h:g}x labor acceleration, exponent {k_min:g}",
            0.5,
            "x",
            (f"{min_h:g} ** {k_min:g}", cap),
        ),
        claim(
            "avg_accel_sc_to_min_h",
            "Average safety acceleration between superhuman coder and Min-H",
            0.05,
            "x",
            ("stated superhuman-coder value 6.7 to 10, labor ** 0.75", mh_st),
            ("text-labelled 15 ** 0.6 to 10, labor ** 0.75", mh_re),
            ("text-labelled 15 ** 0.6 to 10, no production exponent", mh_plain),
        ),
        claim(
            "extra_years_sc_to_min_h",
            "Extra years of safety progress between superhuman coder and Min-H",
            0.05,
            "years",
            (
                "(stated average 4.8 - 1) x years",
                bt.extra_years(stated["avg_accel_sc_to_min_h"], years_2),
            ),
            ("(recomputed average from 6.7 to 10 - 1) x years", bt.extra_years(mh_st, years_2)),
            (
                "(recomputed average from 15 ** 0.6 to 10 - 1) x years",
                bt.extra_years(mh_re, years_2),
            ),
        ),
        claim(
            "harness_equivalent_years",
            "Years of safety R&D from fully harnessing Min-H for six months",
            0.5,
            "years",
            (
                f"{months:g} months x {min_h:g} ** {labor_exp:g}",
                months / 12 * bt.production_acceleration(min_h, 1.0, labor_exp),
            ),
            (f"{months:g} months x {min_h:g} ** {k_min:g}", months / 12 * cap),
            (f"{months:g} months x {min_h:g} (no bottleneck)", months / 12 * min_h),
        ),
        claim(
            "years_equivalent_itai_to_sc",
            "Calendar-equivalent years between ITAI and superhuman coder",
            0.5,
            "years",
            (
                "stated rough average 3 x years",
                bt.equivalent_years(stated["avg_accel_itai_to_sc_rough"], years_1),
            ),
            (
                "production average from the stated endpoints x years",
                bt.equivalent_years(prod_st, years_1),
            ),
        ),
        claim(
            "years_equivalent_sc_to_min_h",
            "Calendar-equivalent years between superhuman coder and Min-H",
            0.5,
            "years",
            (
                "stated average 4.8 x years",
                bt.equivalent_years(stated["avg_accel_sc_to_min_h"], years_2),
            ),
            ("recomputed average from 6.7 to 10 x years", bt.equivalent_years(mh_st, years_2)),
        ),
    ]


def reproduce_portfolios(data: RoadmapData) -> list[Claim]:
    """Do the stated percentages add up? (Exact integer arithmetic; no tolerance.)"""
    claims: list[Claim] = []
    for name, portfolio in (("phase1", data.phase1), ("phase2", data.phase2)):
        total = float(sum(a.pct for a in portfolio.areas))
        claims.append(
            Claim(
                f"{name}_areas_sum",
                f"{name}: top-level areas sum to 100%",
                100.0,
                0.0,
                "%",
                (Check("sum of area percentages", total),),
                exact=True,
            )
        )
        for area in portfolio.areas:
            if area.children:
                got = float(sum(c.pct for c in area.children))
                claims.append(
                    Claim(
                        f"{name}_{area.id}_children_sum",
                        f"{name}: sub-areas of '{area.label}' sum to {area.pct}%",
                        float(area.pct),
                        0.0,
                        "%",
                        (Check("sum of sub-area percentages", got),),
                        exact=True,
                    )
                )
    split = float(sum(data.analogies_value_split.values()))
    claims.append(
        Claim(
            "analogies_value_split_sum",
            "Value split among kinds of analogies sums to 1",
            1.0,
            0.0,
            "",
            (Check("3/6 + 1/6 + 2/6", split),),
            exact=True,
        )
    )
    return claims


def reproduce_all(data: RoadmapData) -> list[Claim]:
    return reproduce_botec(data) + reproduce_portfolios(data)


def implied_inputs(data: RoadmapData) -> tuple[float, float]:
    """AI R&D accelerations that would give the stated endpoints at the stated exponent."""
    k = float(data.botec.safety_exponent_itai_to_sc)
    low = float(data.botec.stated["safety_accel_at_itai"])
    high = float(data.botec.stated["safety_accel_at_superhuman_coder"])
    return bt.implied_input(low, k), bt.implied_input(high, k)


def counts(claims: Sequence[Claim]) -> dict[str, int]:
    result = {"reproduced": 0, "approximately_reproduced": 0, "not_reproduced": 0}
    for c in claims:
        result[c.status] += 1
    return result


def render_table(claims: Sequence[Claim]) -> str:
    header = ("claim", "stated", "recomputed", "diff", "status")
    rows = [
        (c.id, f"{c.stated:g}", f"{c.best.value:.4g}", f"{c.difference:+.3g}", c.status)
        for c in claims
    ]
    widths = [max(len(header[i]), *(len(r[i]) for r in rows)) for i in range(5)]
    lines = ["  ".join(h.ljust(w) for h, w in zip(header, widths, strict=True))]
    lines.append("  ".join("-" * w for w in widths))
    lines.extend("  ".join(v.ljust(w) for v, w in zip(r, widths, strict=True)) for r in rows)
    return "\n".join(lines)


_UNIT_TEXT = {"x": "x", "%": "%", "years": " years", "": ""}


def render_markdown(claims: Sequence[Claim]) -> str:
    lines = ["| Claim | Stated | Best recomputation | Value | Status |", "|---|---|---|---|---|"]
    for c in claims:
        stated = f"{c.stated:g}{_UNIT_TEXT[c.unit]}"
        lines.append(
            f"| `{c.id}` — {c.description} | {stated} | {c.best.assumption} "
            f"| {c.best.value:.4g} | {c.status.replace('_', ' ')} |"
        )
    return "\n".join(lines)


def to_json(claims: Sequence[Claim]) -> list[dict[str, Any]]:
    return [
        {
            "id": c.id,
            "description": c.description,
            "stated": c.stated,
            "unit": c.unit,
            "status": c.status,
            "best_assumption": c.best.assumption,
            "best_value": c.best.value,
            "checks": [{"assumption": k.assumption, "value": k.value} for k in c.checks],
        }
        for c in claims
    ]


def dumps(claims: Sequence[Claim]) -> str:
    return json.dumps(to_json(claims), indent=2, sort_keys=True)
