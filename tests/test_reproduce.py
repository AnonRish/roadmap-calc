from __future__ import annotations

import copy
import json
import math
from typing import Any

import pytest
from conftest import raw_data, set_path

from roadmap_calc import (
    Claim,
    load_data,
    parse_data,
    reproduce_all,
    reproduce_botec,
    reproduce_portfolios,
)
from roadmap_calc.reproduce import (
    Check,
    counts,
    dumps,
    implied_inputs,
    render_markdown,
    render_table,
    to_json,
)

DATA = load_data()
BY_ID = {c.id: c for c in reproduce_all(DATA)}

EXPECTED_STATUS = {
    "safety_accel_at_itai": "not_reproduced",
    "safety_accel_at_superhuman_coder": "not_reproduced",
    "avg_accel_itai_to_sc_rough": "reproduced",
    "avg_accel_itai_to_sc_production": "reproduced",
    "extra_years_itai_to_sc": "reproduced",
    "safety_accel_at_min_h": "reproduced",
    "avg_accel_sc_to_min_h": "approximately_reproduced",
    "extra_years_sc_to_min_h": "reproduced",
    "harness_equivalent_years": "approximately_reproduced",
    "years_equivalent_itai_to_sc": "reproduced",
    "years_equivalent_sc_to_min_h": "reproduced",
}


def test_the_statuses_of_the_botec_claims_are_pinned() -> None:
    assert {c.id: c.status for c in reproduce_botec(DATA)} == EXPECTED_STATUS


def test_every_percentage_sum_reproduces_exactly() -> None:
    sums = reproduce_portfolios(DATA)
    assert len(sums) == 2 + 5 + 5 + 1  # two phase totals, 5+5 areas with sub-areas, the value split
    assert all(c.status == "reproduced" and c.exact for c in sums)


def test_summary_counts() -> None:
    assert counts(reproduce_all(DATA)) == {
        "reproduced": 20,
        "approximately_reproduced": 2,
        "not_reproduced": 2,
    }


def test_the_headline_numbers_against_direct_arithmetic() -> None:
    itai, coder = BY_ID["safety_accel_at_itai"], BY_ID["safety_accel_at_superhuman_coder"]
    assert itai.best.value == pytest.approx(3**0.6) and itai.stated == 2.2
    assert coder.best.value == pytest.approx(15**0.6) and coder.stated == 6.7
    assert BY_ID["safety_accel_at_min_h"].best.value == pytest.approx(10.0)
    # the 4.8x average only follows when the superhuman-coder value is 6.7 (not 15 ** 0.6)
    sc = BY_ID["avg_accel_sc_to_min_h"]
    by_assumption = {c.assumption: c.value for c in sc.checks}
    from roadmap_calc import exp_time_average

    assert by_assumption["stated superhuman-coder value 6.7 to 10, labor ** 0.75"] == pytest.approx(
        exp_time_average(6.7, 10.0, 0.75)
    )
    assert by_assumption["text-labelled 15 ** 0.6 to 10, labor ** 0.75"] == pytest.approx(
        exp_time_average(15**0.6, 10.0, 0.75)
    )
    assert sc.best.assumption.startswith("stated superhuman-coder value")
    # 6 months of Min-H labour at 100x with exponent 0.75 is about 15.8 years
    assert BY_ID["harness_equivalent_years"].best.value == pytest.approx(0.5 * 100**0.75)


def test_implied_inputs() -> None:
    low, high = implied_inputs(DATA)
    assert low == pytest.approx(2.2 ** (1 / 0.6)) and high == pytest.approx(6.7 ** (1 / 0.6))
    assert (round(low, 1), round(high, 1)) == (3.7, 23.8)


def test_matching_and_best_semantics() -> None:
    claim = Claim(
        "c", "d", 2.8, 0.05, "x", (Check("far", 4.0), Check("near", 2.82), Check("mid", 2.9))
    )
    assert claim.best.assumption == "near"
    assert [c.assumption for c in claim.matching] == ["near"]
    assert claim.status == "reproduced"
    approx = Claim("c", "d", 2.8, 0.05, "x", (Check("a", 2.95),))
    assert approx.status == "approximately_reproduced" and not approx.matching
    far = Claim("c", "d", 2.8, 0.05, "x", (Check("a", 4.0),))
    assert far.status == "not_reproduced"
    exact_ok = Claim("c", "d", 100.0, 0.0, "%", (Check("sum", 100.0),), exact=True)
    exact_bad = Claim("c", "d", 100.0, 0.0, "%", (Check("sum", 99.0),), exact=True)
    assert (
        exact_ok.status == "reproduced" and exact_bad.status == "not_reproduced"
    )  # no 10% leniency
    zero = Claim("c", "d", 0.0, 0.0, "", (Check("a", 0.3),))
    assert zero.relative_difference == pytest.approx(0.3)


def test_editing_the_data_changes_the_verdicts(raw: dict[str, Any]) -> None:
    # If the page had stated 1.9 and 5.1 for the endpoints, they would reproduce.
    set_path(raw, "botec.stated.safety_accel_at_itai", "1.9")
    set_path(raw, "botec.stated.safety_accel_at_superhuman_coder", "5.1")
    statuses = {c.id: c.status for c in reproduce_botec(parse_data(raw))}
    assert statuses["safety_accel_at_itai"] == "reproduced"
    assert statuses["safety_accel_at_superhuman_coder"] == "reproduced"
    # A percentage that does not add up is caught, exactly.
    other = copy.deepcopy(raw_data())
    set_path(other, "portfolios.phase1.areas.4.pct", 7)
    bad = [c for c in reproduce_portfolios(parse_data(other)) if c.status != "reproduced"]
    assert {c.id for c in bad} == {"phase1_areas_sum", "phase1_evals_and_demos_children_sum"}


def test_renderers() -> None:
    claims = reproduce_all(DATA)
    table = render_table(claims)
    assert table.splitlines()[0].split() == ["claim", "stated", "recomputed", "diff", "status"]
    assert "safety_accel_at_itai" in table and "not_reproduced" in table
    markdown = render_markdown(claims)
    assert markdown.splitlines()[0].startswith("| Claim |")
    assert "| 2 years |" in markdown and "| 2.2x |" in markdown and "| 100% |" in markdown
    payload = json.loads(dumps(claims))
    assert payload == to_json(claims) and len(payload) == 24
    assert payload[0]["checks"][0]["assumption"] == "3 ** 0.6"
    assert math.isclose(payload[0]["best_value"], 3**0.6)
