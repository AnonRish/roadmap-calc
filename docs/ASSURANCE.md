# Assurance case

| # | Claim | Evidence |
|---|---|---|
| 1 | The bundled data equals the page: the risk table, modifiers, BOTEC inputs and stated results, value split, both portfolios (every sub-bullet) and phase-3 priorities were typed twice, separately, and agree. | `tests/test_data.py` (double-entry literals). |
| 2 | The data is structurally strict (exact field sets, types, identifiers, exact numeric strings) and internally consistent (monotone risk columns, percentages in range, unique ids, every percentage sum). Each rule has a test that breaks it. | `tests/test_data.py` (24 structural and 14 semantic mutation cases). |
| 3 | Risk look-ups return table rows exactly, label bounds as bounds, reject speedups outside the table, read inputs as written (1.15 is 23/20), are monotone in the speedup in every mode, continuous at the rows, and ordered `previous ≤ log-linear ≤ conservative`. Interpolation matches an independent calculation. | `tests/test_risk.py` (Hypothesis). |
| 4 | Risk modifiers never lower risk, never exceed 100%, and combine as documented. | `tests/test_risk.py`. |
| 5 | The BOTEC arithmetic is correct: the closed-form exponential-time average equals Simpson integration across the parameter space, stays accurate for nearly equal endpoints (a bug Hypothesis found and the tests now pin), reports overflow instead of returning garbage, and lies between its endpoint values. | `tests/test_botec.py`. |
| 6 | Every checkable figure is recomputed from the page's stated inputs; the verdict of each is pinned (20 reproduced, 2 approximate, 2 not), including the implied inputs (3.7x, 23.8x); editing the data changes the verdicts as it should. | `tests/test_reproduce.py`. |
| 7 | Largest-remainder apportionment always sums exactly to the headcount, keeps every share within one unit of exact, is deterministic, and changes by at most one unit per area when the total grows by one; interpolation is linear, hits both phases at the ends and always sums to exactly 100. | `tests/test_portfolio.py` (Hypothesis, exact `Fraction` arithmetic). |
| 8 | The committed reproduction report is regenerated from the data and matches. | `tests/test_docs.py`. |
| 9 | The CLI behaves as documented and the package installs from a wheel into a clean virtualenv and runs. | `tests/test_cli.py`; `scripts/verify.sh`. |

## What this does *not* establish

- That any of the roadmap's estimates is correct, only that its arithmetic is consistent with its
  stated inputs.
- That the page has not changed since the retrieval date.
- Anything about the authors' intent where the page does not state a definition.

## Reproduce

```bash
python -m pip install -e ".[dev]"
scripts/verify.sh "roadmap-calc validate"
```
