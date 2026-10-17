from __future__ import annotations

import json
import subprocess
import sys

import pytest

from roadmap_calc import __version__
from roadmap_calc.cli import main


def run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0 and __version__ in capsys.readouterr().out


def test_module_entry_point() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "roadmap_calc.cli", "validate"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "data OK" in result.stdout


def test_risk(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "risk", "--speedup", "10")
    assert code == 0 and "marginal_risk at 10x: 7.00%" in out and "table row" in out
    assert "this tool's convention" in out
    code, out, _ = run(
        capsys, "risk", "--speedup", "7", "--field", "both", "--modifier", "neuralese"
    )
    assert (
        "interpolated" in out
        and "p_scheming at 7x" in out
        and "after modifiers (neuralese; combine=max)" in out
    )
    code, out, _ = run(capsys, "risk", "--speedup", "5", "--mode", "conservative", "--json")
    payload = json.loads(out)
    assert (
        code == 0 and payload["marginal_risk"]["pct"] == 7.0 and payload["mode"] == "conservative"
    )
    code, out, _ = run(
        capsys,
        "risk",
        "--speedup",
        "3",
        "--modifier",
        "garbled_cot",
        "--modifier",
        "neuralese",
        "--combine",
        "multiply",
        "--json",
    )
    assert json.loads(out)["marginal_risk"]["after_modifiers_pct"] == pytest.approx(9.0)


def test_risk_errors(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = run(capsys, "risk", "--speedup", "30")
    assert code == 2 and "table ends at 22x" in err
    code, _, err = run(capsys, "risk", "--speedup", "0.5")
    assert code == 2 and "at least 1" in err
    code, _, err = run(capsys, "risk", "--speedup", "abc")
    assert code == 2
    code, _, err = run(capsys, "risk", "--speedup", "5", "--modifier", "telepathy")
    assert code == 2 and "unknown modifier" in err


def test_tolerance(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "tolerance", "--max-risk", "3")
    assert code == 0 and "waiting until 3x costs a marginal risk of 3%" in out
    code, out, _ = run(capsys, "tolerance", "--max-risk", "50")
    assert code == 0 and "every table row stays within 50%" in out and "22x" in out
    code, out, _ = run(capsys, "tolerance", "--max-risk", "0.5")
    assert code == 1 and "no table row is guaranteed" in out


def test_reproduce_and_botec(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "reproduce")
    assert code == 0
    assert "safety_accel_at_itai" in out and "not_reproduced" in out
    assert "20 reproduced, 2 approximately reproduced, 2 not reproduced" in out
    assert "about 3.7x and 23.8x" in out
    code, out, _ = run(capsys, "reproduce", "--only", "portfolio")
    assert "phase1_areas_sum" in out and "safety_accel" not in out
    code, out, _ = run(capsys, "botec")
    assert "avg_accel_sc_to_min_h" in out and "phase1" not in out
    code, out, _ = run(capsys, "reproduce", "--format", "json")
    assert len(json.loads(out)) == 24
    code, out, _ = run(capsys, "botec", "--format", "markdown")
    assert out.startswith("| Claim |")


def test_portfolio(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "portfolio", "--phase", "2")
    assert code == 0 and "Phase 2" in out and "neuralese_decoding" in out and "5%" in out
    code, out, _ = run(capsys, "portfolio", "--phase", "1", "--fte", "12")
    lines = [line.split() for line in out.splitlines()[1:]]
    assert sum(int(count) for _, count in lines) == 12
    code, out, _ = run(capsys, "portfolio", "--phase", "2", "--leaves")
    assert "control/misc_ml_control" in out and "buying_time_with_usg" in out
    code, out, _ = run(capsys, "portfolio", "--compare")
    assert "control" in out and "33%" in out and "15%" in out
    code, out, _ = run(capsys, "portfolio", "--interpolate", "0.5")
    assert "control" in out and "24.00%" in out
    code, _, err = run(capsys, "portfolio", "--interpolate", "2")
    assert code == 2 and "between 0 and 1" in err


def test_validate_and_data(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    code, out, _ = run(capsys, "validate")
    assert code == 0 and "data OK" in out
    code, out, _ = run(capsys, "data")
    assert code == 0 and json.loads(out)["meta"]["retrieved"] == "2026-10-10"

    import roadmap_calc.cli as cli_module

    real = cli_module.check_data
    monkeypatch.setattr(cli_module, "check_data", lambda data: [*real(data), "synthetic problem"])
    code, out, _ = run(capsys, "validate")
    assert code == 1 and "PROBLEM  synthetic problem" in out and "1 problem(s)" in out
