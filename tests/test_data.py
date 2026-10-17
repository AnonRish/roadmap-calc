from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
from conftest import del_path, raw_data, set_path

from roadmap_calc import DataError, check_data, load_data, parse_data
from roadmap_calc.data import Bound, parse_number

# Double-entry transcription: these literals were typed separately from the data file, from
# the roadmap page, so an accidental edit to either side is caught.
TABLE = [
    ("1.15", "<", "1", "<", "1"),
    ("1.5", "=", "1", "=", "3"),
    ("3", "=", "3", "=", "8"),
    ("10", "=", "7", "=", "14"),
    ("22", "=", "12", "=", "18"),
]
PHASE1 = {
    "control": (33, [21, 4, 6, 2]),
    "analogies": (15, [10, 2, 2, 1]),
    "usefulness_and_deference": (17, [6, 5, 3, 2, 1]),
    "misc_science": (29, [6, 5, 4, 4, 3, 3, 4]),
    "evals_and_demos": (6, [4, 2]),
}
PHASE2 = {
    "control": (15, [7, 5, 1, 2]),
    "analogies": (21, [16, 1, 4]),
    "usefulness_and_deference": (20, [9, 5, 5, 1]),
    "buying_time_with_usg": (17, []),
    "dacc": (3, []),
    "neuralese_decoding": (5, []),
    "misc_science": (10, [2, 1, 2, 3, 2]),
    "evals_and_demos": (9, [7, 2]),
}


def test_the_bundled_data_is_consistent() -> None:
    assert check_data(load_data()) == []


def test_risk_table_matches_the_page() -> None:
    data = load_data()
    got = [
        (
            str(float(r.speedup)).rstrip("0").rstrip("."),
            r.marginal_risk.op,
            f"{float(r.marginal_risk.pct):g}",
            r.p_scheming.op,
            f"{float(r.p_scheming.pct):g}",
        )
        for r in data.risk_table
    ]
    assert got == TABLE
    assert data.risk_table[0].speedup == Fraction(23, 20)  # exact, not a binary float


def test_modifiers_botec_and_split_match_the_page() -> None:
    data = load_data()
    assert {m.id: m.factor for m in data.risk_modifiers} == {
        "garbled_cot": Fraction(3, 2),
        "neuralese": Fraction(2),
        "cot_incentivized_to_look_nice": Fraction(3, 2),
    }
    b = data.botec
    assert (b.itai_ai_rd_accel, b.superhuman_coder_ai_rd_accel, b.min_h_safety_labor_accel) == (
        3,
        15,
        100,
    )
    assert (b.safety_exponent_itai_to_sc, b.safety_exponent_min_h) == (
        Fraction(3, 5),
        Fraction(1, 2),
    )
    assert (b.production_labor_exponent, b.production_compute_exponent) == (
        Fraction(3, 4),
        Fraction(1, 4),
    )
    assert (b.years_itai_to_sc, b.years_sc_to_min_h, b.harness_months) == (1, 1, 6)
    assert b.stated == {
        "safety_accel_at_itai": Fraction("2.2"),
        "safety_accel_at_superhuman_coder": Fraction("6.7"),
        "avg_accel_itai_to_sc_rough": 3,
        "avg_accel_itai_to_sc_production": Fraction("2.8"),
        "extra_years_itai_to_sc": 2,
        "safety_accel_at_min_h": 10,
        "avg_accel_sc_to_min_h": Fraction("4.8"),
        "extra_years_sc_to_min_h": Fraction("3.8"),
        "harness_equivalent_years": 15,
        "years_equivalent_itai_to_sc": 3,
        "years_equivalent_sc_to_min_h": 5,
    }
    assert data.analogies_value_split == {
        "natural_schemers": Fraction(1, 2),
        "trained_in_scheming": Fraction(1, 6),
        "abstract_analogies": Fraction(1, 3),
    }
    assert [rank for rank, _ in data.phase3_priorities] == ["P0", "P1", "P2", "P2", "P3"]


@pytest.mark.parametrize("phase,expected", [("phase1", PHASE1), ("phase2", PHASE2)])
def test_portfolios_match_the_page(phase: str, expected: dict[str, tuple[int, list[int]]]) -> None:
    portfolio = getattr(load_data(), phase)
    got = {a.id: (a.pct, [c.pct for c in a.children]) for a in portfolio.areas}
    assert got == expected
    assert [a.id for a in portfolio.areas] == list(expected)


def test_parse_number() -> None:
    assert parse_number("1.15") == Fraction(23, 20)
    assert parse_number("3/6") == Fraction(1, 2)
    assert parse_number("10") == 10
    for bad in ("1e3", "-1", "", "1.5.2", "1/0", "abc", " 1", 5, None, 1.5):
        with pytest.raises(DataError):
            parse_number(bad)


def test_bound_formatting() -> None:
    assert str(Bound("<", Fraction(1))) == "<1%"
    assert str(Bound("=", Fraction(3))) == "3%"


STRUCTURAL: list[tuple[str, Any]] = [
    ("meta", [1]),
    ("risk_table", {}),
    ("risk_table.0.note", ""),
    ("risk_table.0.speedup", "1e3"),
    ("risk_table.0.speedup", 1.15),
    ("risk_table.0.marginal_risk.op", "<="),
    ("risk_table.0.marginal_risk.pct", "-1"),
    ("risk_table.0.marginal_risk", "<1"),
    ("risk_modifiers", {}),
    ("risk_modifiers.0.id", "Bad Id"),
    ("risk_modifiers.0.factor", "x"),
    ("botec.itai_ai_rd_accel", "abc"),
    ("botec.stated", []),
    ("analogies_value_split", {"natural_schemers": "1/2"}),
    ("portfolios.phase1.areas", {}),
    ("portfolios.phase1.label", ""),
    ("portfolios.phase1.areas.0.pct", 33.5),
    ("portfolios.phase1.areas.0.pct", True),
    ("portfolios.phase1.areas.0.id", "Control"),
    ("portfolios.phase1.areas.0.children", {}),
    ("portfolios.phase1.areas.0.children.0.children", []),
    ("portfolios.phase1.areas.0.children.0.pct", "21"),
    ("phase3_priorities", {}),
    ("phase3_priorities.0.rank", ""),
]


@pytest.mark.parametrize("path,value", STRUCTURAL, ids=[f"{p}={v!r}" for p, v in STRUCTURAL])
def test_structural_errors_are_rejected(raw: dict[str, Any], path: str, value: Any) -> None:
    set_path(raw, path, value)
    with pytest.raises(DataError):
        parse_data(raw)


@pytest.mark.parametrize(
    "path",
    [
        "botec",
        "meta",
        "risk_table.0.note",
        "portfolios.phase2",
        "botec.stated.safety_accel_at_itai",
    ],
)
def test_missing_fields_are_rejected(raw: dict[str, Any], path: str) -> None:
    del_path(raw, path)
    with pytest.raises(DataError, match="wrong fields"):
        parse_data(raw)


def test_unknown_fields_are_rejected(raw: dict[str, Any]) -> None:
    raw["surprise"] = 1
    with pytest.raises(DataError, match="unexpected"):
        parse_data(raw)
    del raw["surprise"]
    raw["risk_table"][0]["extra"] = 1
    with pytest.raises(DataError, match="unexpected"):
        parse_data(raw)


def _problems(raw: dict[str, Any]) -> list[str]:
    return check_data(parse_data(raw))


def _swap_rows(r: dict[str, Any]) -> None:
    r["risk_table"][0], r["risk_table"][1] = r["risk_table"][1], r["risk_table"][0]


SEMANTIC: list[tuple[str, Any, str]] = [
    ("speedups out of order", _swap_rows, "strictly increasing"),
    (
        "marginal risk decreasing",
        lambda r: set_path(r, "risk_table.2.marginal_risk.pct", "0.5"),
        "marginal risk must not decrease",
    ),
    (
        "p(scheming) decreasing",
        lambda r: set_path(r, "risk_table.3.p_scheming.pct", "1"),
        "P(scheming) must not decrease",
    ),
    ("speedup below 1", lambda r: set_path(r, "risk_table.0.speedup", "0.5"), "below 1"),
    (
        "percentage above 100",
        lambda r: set_path(r, "risk_table.4.marginal_risk.pct", "150"),
        "outside 0-100",
    ),
    (
        "duplicate modifier ids",
        lambda r: set_path(r, "risk_modifiers.1.id", "garbled_cot"),
        "modifier ids must be unique",
    ),
    ("modifier below 1", lambda r: set_path(r, "risk_modifiers.0.factor", "0.5"), "at least 1"),
    (
        "split does not sum to 1",
        lambda r: set_path(r, "analogies_value_split.abstract_analogies", "1/6"),
        "sum to 1",
    ),
    (
        "phase 1 areas do not sum",
        lambda r: set_path(r, "portfolios.phase1.areas.4.pct", 7),
        "phase1: top-level areas must sum to 100%",
    ),
    (
        "phase 2 areas do not sum",
        lambda r: set_path(r, "portfolios.phase2.areas.4.pct", 4),
        "phase2: top-level areas must sum to 100%",
    ),
    (
        "children do not sum",
        lambda r: set_path(r, "portfolios.phase1.areas.0.children.0.pct", 20),
        "sub-areas must sum to 33%",
    ),
    (
        "duplicate area ids",
        lambda r: set_path(r, "portfolios.phase1.areas.1.id", "control"),
        "area ids must be unique",
    ),
    (
        "duplicate child ids",
        lambda r: set_path(r, "portfolios.phase1.areas.0.children.1.id", "misc_ml_control"),
        "child ids must be unique",
    ),
    (
        "area pct out of range",
        lambda r: set_path(r, "portfolios.phase2.areas.3.pct", 101),
        "outside 0-100",
    ),
]


@pytest.mark.parametrize("name,mutate,expected", SEMANTIC, ids=[c[0] for c in SEMANTIC])
def test_semantic_problems_are_found(
    raw: dict[str, Any], name: str, mutate: Any, expected: str
) -> None:
    mutate(raw)
    assert any(expected in p for p in _problems(raw)), (name, _problems(raw))


def test_load_data_from_a_file_and_error_handling(tmp_path: Path) -> None:
    path = tmp_path / "copy.json"
    import json

    path.write_text(json.dumps(raw_data()))
    assert load_data(path) == load_data()
    path.write_text("{")
    with pytest.raises(DataError, match="invalid JSON"):
        load_data(path)
    with pytest.raises(FileNotFoundError):
        load_data(tmp_path / "missing.json")
