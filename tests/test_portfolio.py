from __future__ import annotations

from fractions import Fraction
from itertools import pairwise

import pytest
from hypothesis import given
from hypothesis import strategies as st

from roadmap_calc import allocate, apportion, interpolate, load_data
from roadmap_calc.portfolio import entries, shifts

DATA = load_data()


def test_apportion_known_cases() -> None:
    assert apportion([50, 50], 3) == [2, 1]  # the tie goes to the earlier entry
    assert apportion([33, 33, 34], 10) == [3, 3, 4]  # the largest remainder gets the spare unit
    assert apportion([100], 7) == [7]
    assert apportion([25, 25, 25, 25], 0) == [0, 0, 0, 0]
    assert apportion([70, 20, 10], 10) == [7, 2, 1]
    assert apportion([Fraction(1, 3) * 100, Fraction(2, 3) * 100], 4) == [1, 3]


def test_apportion_validation() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        apportion([50, 50], -1)
    with pytest.raises(ValueError, match="non-negative"):
        apportion([120, -20], 5)
    with pytest.raises(ValueError, match="sum to exactly 100"):
        apportion([50, 49], 5)


@st.composite
def split_of_100(draw: st.DrawFn) -> list[int]:
    cuts = sorted(draw(st.lists(st.integers(0, 100), min_size=1, max_size=9)))
    points = [0, *cuts, 100]
    return [b - a for a, b in pairwise(points)]


@given(split_of_100(), st.integers(0, 5000))
def test_apportionment_properties(percents: list[int], total: int) -> None:
    result = apportion(percents, total)
    assert sum(result) == total and all(r >= 0 for r in result)
    for p, r in zip(percents, result, strict=True):
        exact = Fraction(total * p, 100)
        assert abs(r - exact) < 1  # never more than one unit away from the exact share
        assert r in (exact.__floor__(), exact.__ceil__())
    assert apportion(percents, total) == result  # deterministic


@given(split_of_100(), st.integers(0, 2000))
def test_a_larger_total_never_takes_a_unit_from_any_area_by_more_than_one_rounding(
    percents: list[int], total: int
) -> None:
    small, large = apportion(percents, total), apportion(percents, total + 1)
    assert sum(large) - sum(small) == 1
    assert all(abs(b - a) <= 1 for a, b in zip(small, large, strict=True))


def test_entries_and_allocation_on_the_real_portfolios() -> None:
    p1, p2 = DATA.phase1, DATA.phase2
    assert [n for n, _ in entries(p1)] == [
        "control",
        "analogies",
        "usefulness_and_deference",
        "misc_science",
        "evals_and_demos",
    ]
    leaves = entries(p2, "leaves")
    assert sum(pct for _, pct in leaves) == 100
    assert ("buying_time_with_usg", 17) in leaves and ("control/misc_ml_control", 7) in leaves
    areas = dict(allocate(p1, 100))
    assert areas == {
        "control": 33,
        "analogies": 15,
        "usefulness_and_deference": 17,
        "misc_science": 29,
        "evals_and_demos": 6,
    }
    twelve = dict(allocate(p1, 12))
    assert sum(twelve.values()) == 12 and twelve["control"] == 4
    assert sum(c for _, c in allocate(p2, 37, "leaves")) == 37


def test_interpolation() -> None:
    p1, p2 = DATA.phase1, DATA.phase2
    start = dict(interpolate(p1, p2, 0))
    end = dict(interpolate(p1, p2, 1))
    assert start["control"] == 33 and start["buying_time_with_usg"] == 0
    assert end["control"] == 15 and end["buying_time_with_usg"] == 17
    half = dict(interpolate(p1, p2, Fraction(1, 2)))
    assert half["control"] == 24 and half["dacc"] == Fraction(3, 2)
    for t in (0, Fraction(1, 7), Fraction(1, 2), Fraction(9, 10), 1):
        weights = interpolate(p1, p2, t)
        assert sum(w for _, w in weights) == 100
        assert [n for n, _ in weights][:5] == [a.id for a in p1.areas]
    with pytest.raises(ValueError, match="between 0 and 1"):
        interpolate(p1, p2, Fraction(3, 2))
    with pytest.raises(ValueError):
        interpolate(p1, p2, -1)


def test_shifts_between_phases() -> None:
    table = {name: (a, b) for name, a, b in shifts(DATA.phase1, DATA.phase2)}
    assert table["control"] == (33, 15)
    assert table["analogies"] == (15, 21)
    assert table["neuralese_decoding"] == (0, 5)
    assert table["evals_and_demos"] == (6, 9)
    assert sum(a for a, _ in table.values()) == 100 and sum(b for _, b in table.values()) == 100
