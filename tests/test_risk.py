from __future__ import annotations

import math
from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

from roadmap_calc import OutOfRange, apply_modifiers, latest_threshold_within, load_data, lookup

DATA = load_data()
TABLE = DATA.risk_table


@pytest.mark.parametrize(
    "speedup,field,pct,kind",
    [
        ("1.15", "marginal_risk", 1.0, "upper_bound"),
        ("1.5", "marginal_risk", 1.0, "row"),
        ("3", "marginal_risk", 3.0, "row"),
        ("10", "marginal_risk", 7.0, "row"),
        ("22", "marginal_risk", 12.0, "row"),
        ("1.15", "p_scheming", 1.0, "upper_bound"),
        ("1.5", "p_scheming", 3.0, "row"),
        ("3", "p_scheming", 8.0, "row"),
        ("10", "p_scheming", 14.0, "row"),
        ("22", "p_scheming", 18.0, "row"),
    ],
)
def test_table_rows_are_returned_exactly(speedup: str, field: str, pct: float, kind: str) -> None:
    estimate = lookup(TABLE, speedup, field)  # type: ignore[arg-type]
    assert (estimate.pct, estimate.kind) == (pct, kind)
    assert "table row" in estimate.detail


def test_inputs_are_read_as_written_not_as_binary_floats() -> None:
    for value in (1.15, "1.15", Fraction(23, 20)):
        assert lookup(TABLE, value).kind == "upper_bound"  # exactly the 1.15 row
    assert lookup(TABLE, 3).pct == lookup(TABLE, 3.0).pct == lookup(TABLE, "3").pct == 3.0


def test_below_the_first_row_the_table_only_gives_an_upper_bound() -> None:
    estimate = lookup(TABLE, 1.0)
    assert (estimate.pct, estimate.kind) == (1.0, "upper_bound")
    assert "below the first row" in estimate.detail


def test_out_of_range_inputs() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        lookup(TABLE, 0.9)
    with pytest.raises(OutOfRange, match="22x"):
        lookup(TABLE, 22.5)


def test_loglinear_interpolation_matches_an_independent_calculation() -> None:
    t = math.log(5 / 3) / math.log(10 / 3)
    estimate = lookup(TABLE, 5)
    assert estimate.kind == "interpolated"
    assert estimate.pct == pytest.approx(3 + 4 * t, abs=1e-12)
    assert "between 3x and 10x" in estimate.detail
    t2 = math.log(2 / 1.5) / math.log(3 / 1.5)
    assert lookup(TABLE, 2, "p_scheming").pct == pytest.approx(3 + 5 * t2, abs=1e-12)


def test_between_the_first_two_rows_the_result_stays_an_upper_bound() -> None:
    estimate = lookup(TABLE, 1.3)
    assert estimate.kind == "upper_bound" and estimate.pct == pytest.approx(1.0)


def test_conservative_and_previous_modes() -> None:
    up = lookup(TABLE, 5, mode="conservative")
    down = lookup(TABLE, 5, mode="previous")
    assert (up.pct, up.kind) == (7.0, "row") and "next row up" in up.detail
    assert (down.pct, down.kind) == (3.0, "row") and "previous row" in down.detail
    assert lookup(TABLE, 1.3, mode="previous").kind == "upper_bound"
    assert lookup(TABLE, 1.3, mode="conservative").pct == 1.0


speedups = st.fractions(min_value=Fraction(1), max_value=Fraction(22), max_denominator=1000)


@given(speedups, speedups, st.sampled_from(["marginal_risk", "p_scheming"]))
def test_risk_never_decreases_with_speedup(a: Fraction, b: Fraction, field: str) -> None:
    low, high = min(a, b), max(a, b)
    for mode in ("loglinear", "conservative", "previous"):
        assert lookup(TABLE, low, field, mode).pct <= lookup(TABLE, high, field, mode).pct + 1e-12  # type: ignore[arg-type]


@given(speedups, st.sampled_from(["marginal_risk", "p_scheming"]))
def test_modes_are_ordered_and_bounded(s: Fraction, field: str) -> None:
    previous = lookup(TABLE, s, field, "previous").pct  # type: ignore[arg-type]
    middle = lookup(TABLE, s, field, "loglinear").pct  # type: ignore[arg-type]
    upper = lookup(TABLE, s, field, "conservative").pct  # type: ignore[arg-type]
    assert previous - 1e-12 <= middle <= upper + 1e-12
    assert previous >= 0 and upper <= 100


def test_interpolation_is_continuous_at_the_rows() -> None:
    for row in TABLE[1:-1]:
        below = lookup(TABLE, row.speedup - Fraction(1, 10**9)).pct
        above = lookup(TABLE, row.speedup + Fraction(1, 10**9)).pct
        exact = lookup(TABLE, row.speedup).pct
        assert below == pytest.approx(exact, abs=1e-6) and above == pytest.approx(exact, abs=1e-6)


# ---- modifiers ---------------------------------------------------------------------------


def test_modifiers() -> None:
    mods = DATA.risk_modifiers
    assert apply_modifiers(7.0, [], mods) == 7.0
    assert apply_modifiers(7.0, ["neuralese"], mods) == 14.0
    assert apply_modifiers(7.0, ["garbled_cot"], mods) == pytest.approx(10.5)
    assert apply_modifiers(7.0, ["garbled_cot", "neuralese"], mods, "max") == 14.0
    assert apply_modifiers(7.0, ["garbled_cot", "neuralese"], mods, "multiply") == pytest.approx(
        21.0
    )
    assert apply_modifiers(
        7.0, ["garbled_cot", "cot_incentivized_to_look_nice"], mods, "multiply"
    ) == pytest.approx(15.75)
    assert apply_modifiers(60.0, ["neuralese"], mods) == 100.0  # capped
    assert apply_modifiers(150.0, [], mods) == 100.0
    with pytest.raises(KeyError, match="unknown modifier"):
        apply_modifiers(7.0, ["telepathy"], mods)


@given(
    st.floats(0, 100),
    st.lists(
        st.sampled_from(["garbled_cot", "neuralese", "cot_incentivized_to_look_nice"]), max_size=3
    ),
)
def test_modifiers_never_reduce_risk_and_never_exceed_100(pct: float, ids: list[str]) -> None:
    for combine in ("max", "multiply"):
        out = apply_modifiers(pct, ids, DATA.risk_modifiers, combine)  # type: ignore[arg-type]
        assert pct <= out <= 100.0


# ---- thresholds --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "limit,expected",
    [
        (0.5, None),
        (0.99, None),
        (1, "1.5"),
        (2.9, "1.5"),
        (3, "3"),
        (6.99, "3"),
        (7, "10"),
        (11.9, "10"),
        (12, "22"),
        (100, "22"),
    ],
)
def test_latest_threshold_within(limit: float, expected: str | None) -> None:
    row = latest_threshold_within(TABLE, limit)
    assert (None if row is None else f"{float(row.speedup):g}") == expected
