"""Loading and checking the source data (numbers transcribed from the roadmap page).

All numbers are stored as strings and parsed as exact fractions, so a table row such as
``1.15`` is exactly 23/20 and never a binary float.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from fractions import Fraction
from importlib import resources
from itertools import pairwise
from pathlib import Path
from typing import Any, Literal

_NUMBER = re.compile(r"^\d+(\.\d+)?(/\d+)?$")
_ID = re.compile(r"^[a-z][a-z0-9_]*$")


class DataError(ValueError):
    """The data file does not have the expected structure."""


def parse_number(text: Any, what: str = "number") -> Fraction:
    """Parse a non-negative decimal (``"1.15"``) or ratio (``"3/6"``) exactly."""
    if not isinstance(text, str) or not _NUMBER.match(text):
        raise DataError(f"{what} must be a string like '1.15' or '3/6', got {text!r}")
    try:
        return Fraction(text)
    except ZeroDivisionError as exc:
        raise DataError(f"{what} {text!r} divides by zero") from exc


@dataclass(frozen=True)
class Bound:
    """A percentage that is either exact (``=``) or an upper bound (``<``)."""

    op: Literal["<", "="]
    pct: Fraction

    def __str__(self) -> str:
        value = f"{float(self.pct):g}%"
        return f"<{value}" if self.op == "<" else value


@dataclass(frozen=True)
class RiskRow:
    speedup: Fraction
    marginal_risk: Bound
    p_scheming: Bound
    note: str


@dataclass(frozen=True)
class RiskModifier:
    id: str
    factor: Fraction
    note: str


@dataclass(frozen=True)
class Botec:
    itai_ai_rd_accel: Fraction
    superhuman_coder_ai_rd_accel: Fraction
    min_h_safety_labor_accel: Fraction
    safety_exponent_itai_to_sc: Fraction
    safety_exponent_min_h: Fraction
    production_labor_exponent: Fraction
    production_compute_exponent: Fraction
    years_itai_to_sc: Fraction
    years_sc_to_min_h: Fraction
    harness_months: Fraction
    stated: dict[str, Fraction]


@dataclass(frozen=True)
class Area:
    id: str
    label: str
    pct: int
    children: tuple[Area, ...] = ()


@dataclass(frozen=True)
class Portfolio:
    label: str
    areas: tuple[Area, ...]


@dataclass(frozen=True)
class RoadmapData:
    meta: dict[str, Any]
    risk_table: tuple[RiskRow, ...]
    risk_modifiers: tuple[RiskModifier, ...]
    botec: Botec
    analogies_value_split: dict[str, Fraction]
    phase1: Portfolio
    phase2: Portfolio
    phase3_priorities: tuple[tuple[str, str], ...]


def _keys(obj: Any, keys: set[str], what: str) -> dict[str, Any]:
    if not isinstance(obj, dict):
        raise DataError(f"{what} must be an object")
    if set(obj) != keys:
        raise DataError(
            f"{what} has wrong fields (missing {sorted(keys - set(obj))}, "
            f"unexpected {sorted(set(obj) - keys)})"
        )
    return obj


def _text(value: Any, what: str) -> str:
    if not isinstance(value, str) or not value:
        raise DataError(f"{what} must be a non-empty string")
    return value


def _ident(value: Any, what: str) -> str:
    if not isinstance(value, str) or not _ID.match(value):
        raise DataError(f"{what} must be a lowercase identifier, got {value!r}")
    return value


def _bound(obj: Any, what: str) -> Bound:
    data = _keys(obj, {"op", "pct"}, what)
    if data["op"] not in ("<", "="):
        raise DataError(f"{what}.op must be '<' or '='")
    return Bound(data["op"], parse_number(data["pct"], f"{what}.pct"))


def _area(obj: Any, what: str, allow_children: bool) -> Area:
    keys = {"id", "label", "pct"} | ({"children"} if allow_children else set())
    data = _keys(obj, keys, what)
    pct = data["pct"]
    if isinstance(pct, bool) or not isinstance(pct, int):
        raise DataError(f"{what}.pct must be an integer")
    children: tuple[Area, ...] = ()
    if allow_children:
        if not isinstance(data["children"], list):
            raise DataError(f"{what}.children must be a list")
        children = tuple(_area(c, f"{what}.children[]", False) for c in data["children"])
    return Area(
        _ident(data["id"], f"{what}.id"), _text(data["label"], f"{what}.label"), pct, children
    )


def _portfolio(obj: Any, what: str) -> Portfolio:
    data = _keys(obj, {"label", "areas"}, what)
    if not isinstance(data["areas"], list):
        raise DataError(f"{what}.areas must be a list")
    return Portfolio(
        _text(data["label"], f"{what}.label"),
        tuple(_area(a, f"{what}.areas[]", True) for a in data["areas"]),
    )


_BOTEC_NUMBERS = (
    "itai_ai_rd_accel",
    "superhuman_coder_ai_rd_accel",
    "min_h_safety_labor_accel",
    "safety_exponent_itai_to_sc",
    "safety_exponent_min_h",
    "production_labor_exponent",
    "production_compute_exponent",
    "years_itai_to_sc",
    "years_sc_to_min_h",
    "harness_months",
)
_STATED_KEYS = {
    "safety_accel_at_itai",
    "safety_accel_at_superhuman_coder",
    "avg_accel_itai_to_sc_rough",
    "avg_accel_itai_to_sc_production",
    "extra_years_itai_to_sc",
    "safety_accel_at_min_h",
    "avg_accel_sc_to_min_h",
    "extra_years_sc_to_min_h",
    "harness_equivalent_years",
    "years_equivalent_itai_to_sc",
    "years_equivalent_sc_to_min_h",
}


def parse_data(raw: Any) -> RoadmapData:
    """Parse already-decoded JSON into :class:`RoadmapData` (structure only)."""
    root = _keys(
        raw,
        {
            "meta",
            "risk_table",
            "risk_modifiers",
            "botec",
            "analogies_value_split",
            "portfolios",
            "phase3_priorities",
        },
        "data",
    )
    if not isinstance(root["meta"], dict):
        raise DataError("meta must be an object")
    if not isinstance(root["risk_table"], list):
        raise DataError("risk_table must be a list")
    rows = []
    for item in root["risk_table"]:
        row = _keys(item, {"speedup", "marginal_risk", "p_scheming", "note"}, "risk row")
        rows.append(
            RiskRow(
                parse_number(row["speedup"], "risk row speedup"),
                _bound(row["marginal_risk"], "marginal_risk"),
                _bound(row["p_scheming"], "p_scheming"),
                _text(row["note"], "risk row note"),
            )
        )
    if not isinstance(root["risk_modifiers"], list):
        raise DataError("risk_modifiers must be a list")
    modifiers = []
    for item in root["risk_modifiers"]:
        mod = _keys(item, {"id", "factor", "note"}, "risk modifier")
        modifiers.append(
            RiskModifier(
                _ident(mod["id"], "modifier id"),
                parse_number(mod["factor"], "modifier factor"),
                _text(mod["note"], "modifier note"),
            )
        )
    botec_raw = _keys(root["botec"], {*_BOTEC_NUMBERS, "stated"}, "botec")
    stated_raw = _keys(botec_raw["stated"], _STATED_KEYS, "botec.stated")
    botec = Botec(
        **{k: parse_number(botec_raw[k], f"botec.{k}") for k in _BOTEC_NUMBERS},
        stated={k: parse_number(v, f"botec.stated.{k}") for k, v in stated_raw.items()},
    )
    split_raw = _keys(
        root["analogies_value_split"],
        {"natural_schemers", "trained_in_scheming", "abstract_analogies"},
        "analogies_value_split",
    )
    portfolios = _keys(root["portfolios"], {"phase1", "phase2"}, "portfolios")
    if not isinstance(root["phase3_priorities"], list):
        raise DataError("phase3_priorities must be a list")
    priorities = []
    for item in root["phase3_priorities"]:
        entry = _keys(item, {"rank", "item"}, "priority")
        priorities.append((_text(entry["rank"], "rank"), _text(entry["item"], "item")))
    return RoadmapData(
        meta=root["meta"],
        risk_table=tuple(rows),
        risk_modifiers=tuple(modifiers),
        botec=botec,
        analogies_value_split={k: parse_number(v, k) for k, v in split_raw.items()},
        phase1=_portfolio(portfolios["phase1"], "phase1"),
        phase2=_portfolio(portfolios["phase2"], "phase2"),
        phase3_priorities=tuple(priorities),
    )


def load_data(path: Path | str | None = None) -> RoadmapData:
    """Load the bundled data (or a file with the same structure)."""
    if path is None:
        text = resources.files("roadmap_calc").joinpath("data/roadmap-2026.json").read_text("utf-8")
    else:
        text = Path(path).read_text("utf-8")
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DataError(f"invalid JSON: {exc}") from exc
    return parse_data(raw)


def check_data(data: RoadmapData) -> list[str]:
    """Semantic checks on the transcribed numbers; returns problems (empty if all hold)."""
    problems: list[str] = []
    table = data.risk_table
    for earlier, later in pairwise(table):
        if later.speedup <= earlier.speedup:
            problems.append("risk table speedups must be strictly increasing")
        if later.marginal_risk.pct < earlier.marginal_risk.pct:
            problems.append("marginal risk must not decrease with speedup")
        if later.p_scheming.pct < earlier.p_scheming.pct:
            problems.append("P(scheming) must not decrease with speedup")
    for row in table:
        if row.speedup < 1:
            problems.append(f"speedup {row.speedup} is below 1")
        for bound in (row.marginal_risk, row.p_scheming):
            if not 0 <= bound.pct <= 100:
                problems.append(f"percentage {bound.pct} is outside 0-100")
    if len({m.id for m in data.risk_modifiers}) != len(data.risk_modifiers):
        problems.append("risk modifier ids must be unique")
    if any(m.factor < 1 for m in data.risk_modifiers):
        problems.append("risk modifier factors must be at least 1")
    if sum(data.analogies_value_split.values()) != 1:
        problems.append("analogies value split must sum to 1")
    for name, portfolio in (("phase1", data.phase1), ("phase2", data.phase2)):
        ids = [a.id for a in portfolio.areas]
        if len(set(ids)) != len(ids):
            problems.append(f"{name}: area ids must be unique")
        if sum(a.pct for a in portfolio.areas) != 100:
            problems.append(f"{name}: top-level areas must sum to 100%")
        for area in portfolio.areas:
            if not 0 <= area.pct <= 100:
                problems.append(f"{name}.{area.id}: pct outside 0-100")
            kids = [c.id for c in area.children]
            if len(set(kids)) != len(kids):
                problems.append(f"{name}.{area.id}: child ids must be unique")
            if area.children and sum(c.pct for c in area.children) != area.pct:
                problems.append(f"{name}.{area.id}: sub-areas must sum to {area.pct}%")
    return problems
