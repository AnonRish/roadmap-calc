"""Command-line interface (``roadmap-calc``)."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from fractions import Fraction
from importlib import resources

from . import __version__
from .data import DataError, check_data, load_data
from .portfolio import Level, allocate, entries, interpolate, shifts
from .reproduce import (
    Claim,
    counts,
    dumps,
    implied_inputs,
    render_markdown,
    render_table,
    reproduce_all,
    reproduce_botec,
    reproduce_portfolios,
)
from .risk import Estimate, OutOfRange, apply_modifiers, latest_threshold_within, lookup


def _describe(label: str, estimate: Estimate) -> str:
    tag = {"row": "table row", "interpolated": "interpolated", "upper_bound": "upper bound"}[
        estimate.kind
    ]
    return f"{label}: {estimate.pct:.2f}%  [{tag}: {estimate.detail}]"


def _cmd_risk(args: argparse.Namespace) -> int:
    data = load_data()
    fields = ("marginal_risk", "p_scheming") if args.field == "both" else (args.field,)
    payload: dict[str, object] = {"speedup": args.speedup, "mode": args.mode}
    for field in fields:
        estimate = lookup(data.risk_table, args.speedup, field, args.mode)  # type: ignore[arg-type]
        adjusted = apply_modifiers(
            estimate.pct, args.modifier or [], data.risk_modifiers, args.combine
        )
        payload[field] = {
            "pct": estimate.pct,
            "kind": estimate.kind,
            "detail": estimate.detail,
            "after_modifiers_pct": adjusted,
        }
        if not args.json:
            print(_describe(f"{field} at {args.speedup}x", estimate))
            if args.modifier:
                names = ", ".join(args.modifier)
                print(f"  after modifiers ({names}; combine={args.combine}): {adjusted:.2f}%")
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("Values between table rows are this tool's convention, not numbers from the source.")
    return 0


def _cmd_tolerance(args: argparse.Namespace) -> int:
    table = load_data().risk_table
    row = latest_threshold_within(table, args.max_risk)
    if row is None:
        print(f"no table row is guaranteed to stay within {args.max_risk}% marginal risk")
        return 1
    speedup = f"{float(row.speedup):g}x"
    if row is table[-1]:
        print(f"every table row stays within {args.max_risk}% (highest: {speedup})")
    else:
        print(
            f"waiting until {speedup} costs a marginal risk of {row.marginal_risk} "
            f"(within {args.max_risk}%); the next row up exceeds it"
        )
    return 0


def _claims(which: str) -> list[Claim]:
    data = load_data()
    if which == "botec":
        return reproduce_botec(data)
    if which == "portfolio":
        return reproduce_portfolios(data)
    return reproduce_all(data)


def _cmd_reproduce(args: argparse.Namespace) -> int:
    claims = _claims(args.only)
    if args.format == "json":
        print(dumps(claims))
    elif args.format == "markdown":
        print(render_markdown(claims))
    else:
        print(render_table(claims))
        summary = counts(claims)
        print(
            f"\n{summary['reproduced']} reproduced, {summary['approximately_reproduced']} "
            f"approximately reproduced, {summary['not_reproduced']} not reproduced"
        )
        low, high = implied_inputs(load_data())
        print(
            f"The stated safety-acceleration endpoints would follow from AI R&D accelerations of "
            f"about {low:.1f}x and {high:.1f}x at the stated exponent."
        )
    return 0


def _cmd_botec(args: argparse.Namespace) -> int:
    args.only = "botec"
    return _cmd_reproduce(args)


def _cmd_portfolio(args: argparse.Namespace) -> int:
    data = load_data()
    level: Level = "leaves" if args.leaves else "areas"
    if args.compare:
        print(f"{'area':<28}{'phase 1':>9}{'phase 2':>9}")
        for name, before, after in shifts(data.phase1, data.phase2):
            print(f"{name:<28}{before:>8}%{after:>8}%")
        return 0
    if args.interpolate is not None:
        weights = interpolate(data.phase1, data.phase2, Fraction(args.interpolate))
        for name, weight in weights:
            print(f"{name:<28}{float(weight):>8.2f}%")
        return 0
    portfolio = data.phase1 if args.phase == 1 else data.phase2
    print(portfolio.label)
    if args.fte is None:
        for name, pct in entries(portfolio, level):
            print(f"{name:<44}{pct:>4}%")
    else:
        for name, count in allocate(portfolio, args.fte, level):
            print(f"{name:<44}{count:>5}")
    return 0


def _cmd_validate(_: argparse.Namespace) -> int:
    problems = check_data(load_data())
    for problem in problems:
        print(f"PROBLEM  {problem}")
    print("data OK" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


def _cmd_data(_: argparse.Namespace) -> int:
    print(
        resources.files("roadmap_calc").joinpath("data/roadmap-2026.json").read_text("utf-8"),
        end="",
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="roadmap-calc",
        description="Calculators and consistency checks for the AI 2040 alignment roadmap.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    risk = sub.add_parser("risk", help="marginal risk / P(scheming) at an AI R&D speedup")
    risk.add_argument("--speedup", required=True)
    risk.add_argument(
        "--field", choices=("marginal_risk", "p_scheming", "both"), default="marginal_risk"
    )
    risk.add_argument(
        "--mode", choices=("loglinear", "conservative", "previous"), default="loglinear"
    )
    risk.add_argument(
        "--modifier",
        action="append",
        help="garbled_cot | neuralese | cot_incentivized_to_look_nice",
    )
    risk.add_argument("--combine", choices=("max", "multiply"), default="max")
    risk.add_argument("--json", action="store_true")
    risk.set_defaults(func=_cmd_risk)

    tol = sub.add_parser(
        "tolerance", help="latest table row whose marginal risk stays within a limit"
    )
    tol.add_argument("--max-risk", required=True, help="percent, e.g. 3")
    tol.set_defaults(func=_cmd_tolerance)

    for name, handler, text in (
        ("reproduce", _cmd_reproduce, "recompute every checkable figure from its stated inputs"),
        ("botec", _cmd_botec, "recompute only the safety-acceleration BOTEC"),
    ):
        p = sub.add_parser(name, help=text)
        p.add_argument("--format", choices=("table", "json", "markdown"), default="table")
        if name == "reproduce":
            p.add_argument("--only", choices=("all", "botec", "portfolio"), default="all")
        p.set_defaults(func=handler)

    pf = sub.add_parser(
        "portfolio", help="effort split by phase; headcount allocation; interpolation"
    )
    pf.add_argument("--phase", type=int, choices=(1, 2), default=1)
    pf.add_argument("--fte", type=int, help="allocate this many people (largest-remainder)")
    pf.add_argument(
        "--leaves", action="store_true", help="use sub-areas where the source gives them"
    )
    pf.add_argument("--compare", action="store_true", help="show phase 1 vs phase 2")
    pf.add_argument("--interpolate", help="blend phase 1 -> phase 2 at t in [0, 1]")
    pf.set_defaults(func=_cmd_portfolio)

    sub.add_parser("validate", help="check the bundled data for internal consistency").set_defaults(
        func=_cmd_validate
    )
    sub.add_parser("data", help="print the bundled source data (JSON)").set_defaults(func=_cmd_data)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point: 0 ok, 1 a check failed, 2 usage or input error."""
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except (ValueError, KeyError, OutOfRange, DataError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
