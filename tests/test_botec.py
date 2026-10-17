from __future__ import annotations

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from roadmap_calc import (
    equivalent_years,
    exp_time_average,
    extra_years,
    implied_input,
    numeric_exp_time_average,
    production_acceleration,
    safety_acceleration,
)


def test_safety_acceleration_known_values() -> None:
    assert safety_acceleration(3, 0.6) == pytest.approx(1.9331820449317627)
    assert safety_acceleration(15, 0.6) == pytest.approx(5.0775, abs=1e-4)
    assert safety_acceleration(100, 0.5) == pytest.approx(10.0)
    assert safety_acceleration(1, 0.6) == 1.0


def test_implied_input_inverts_the_exponent() -> None:
    assert implied_input(2.2, 0.6) == pytest.approx(3.7, abs=0.05)
    assert implied_input(6.7, 0.6) == pytest.approx(23.8, abs=0.05)
    assert safety_acceleration(implied_input(6.7, 0.6), 0.6) == pytest.approx(6.7)
    with pytest.raises(ValueError):
        implied_input(2.0, 0.0)


def test_exponential_time_average_special_cases() -> None:
    assert exp_time_average(1.0, math.e) == pytest.approx(math.e - 1)  # (e - 1) / ln(e)
    assert exp_time_average(2.0, 2.0, 3.0) == 8.0  # no growth
    assert exp_time_average(2.0, 9.0, 0.0) == 1.0  # A ** 0 == 1
    assert exp_time_average(1.0, 4.0, 0.5) == pytest.approx((2.0 - 1.0) / (0.5 * math.log(4)))


positive = st.floats(min_value=0.1, max_value=200.0)
powers = st.floats(min_value=-2.0, max_value=2.0).filter(lambda p: abs(p) > 1e-3)


def test_nearly_equal_endpoints_do_not_lose_precision() -> None:
    """Regression: the textbook form returned 0.0625 here (catastrophic cancellation)."""
    assert exp_time_average(0.1, 0.10000000000000002, 1.0) == pytest.approx(0.1, rel=1e-12)
    for power in (-2.0, -0.5, 0.75, 3.0):
        for eps in (1e-16, 1e-12, 1e-8):
            average = exp_time_average(7.0, 7.0 * (1 + eps), power)
            assert average == pytest.approx(7.0**power, rel=1e-6)


def test_absurdly_wide_ranges_are_reported_not_overflowed() -> None:
    with pytest.raises(ValueError, match="too large"):
        exp_time_average(1e-300, 1e300, 2.0)


@given(positive, positive, powers)
def test_closed_form_matches_numerical_integration(a: float, b: float, power: float) -> None:
    assert exp_time_average(a, b, power) == pytest.approx(
        numeric_exp_time_average(a, b, power), rel=1e-8
    )


@given(positive, positive, powers)
def test_the_average_lies_between_the_endpoint_values(a: float, b: float, power: float) -> None:
    low, high = sorted((a**power, b**power))
    assert low * (1 - 1e-9) <= exp_time_average(a, b, power) <= high * (1 + 1e-9)


def test_numeric_integration_requires_an_even_step_count() -> None:
    for bad in (1, 3, 5):
        with pytest.raises(ValueError, match="even"):
            numeric_exp_time_average(1.0, 2.0, 1.0, steps=bad)
    assert numeric_exp_time_average(1.0, 4.0, 1.0, steps=2) == pytest.approx(
        exp_time_average(1.0, 4.0, 1.0), rel=0.02
    )


def test_production_function() -> None:
    assert production_acceleration(8.0) == pytest.approx(8**0.75)
    assert production_acceleration(8.0, 16.0) == pytest.approx(8**0.75 * 2.0)
    assert production_acceleration(1.0, 1.0) == 1.0
    assert production_acceleration(100.0) == pytest.approx(31.6227766, abs=1e-6)


def test_year_arithmetic() -> None:
    assert extra_years(3.0, 1.0) == 2.0
    assert extra_years(4.8, 1.0) == pytest.approx(3.8)
    assert extra_years(1.0, 5.0) == 0.0
    assert equivalent_years(4.8, 2.0) == pytest.approx(9.6)


@pytest.mark.parametrize("bad", [0.0, -1.0, math.inf, math.nan])
def test_inputs_must_be_positive_and_finite(bad: float) -> None:
    for call in (
        lambda: safety_acceleration(bad, 0.6),
        lambda: implied_input(bad, 0.6),
        lambda: exp_time_average(bad, 2.0),
        lambda: exp_time_average(2.0, bad),
        lambda: numeric_exp_time_average(bad, 2.0),
        lambda: numeric_exp_time_average(2.0, bad),
        lambda: production_acceleration(bad),
        lambda: production_acceleration(2.0, bad),
    ):
        with pytest.raises(ValueError):
            call()
