# roadmap-calc

Exact, tested calculators and consistency checks for the numbers in the
[AI 2040 *Alignment Roadmap*](https://ai-2040.com/supplements/alignment-roadmap)
(Ryan Greenblatt and Thomas Larsen, AI Futures Project): the risk-vs-speedup table, the
safety-acceleration back-of-envelope calculation, and the Phase 1 / Phase 2 effort portfolios.

It does three things:

1. **Encodes the roadmap's numbers as data** with provenance (source URL, retrieval date), parsed
   as exact fractions.
2. **Calculators** you can script: risk at an arbitrary speedup, the effect of the roadmap's
   conditional risk adjustments, the latest threshold within a risk tolerance, whole-person
   allocation of a team according to a portfolio, and interpolation between phases.
3. **Recomputes every checkable figure from the page's own stated inputs** and reports which
   reproduce — so readers can see which numbers are derived, which are consistent, and where the
   page's arithmetic would benefit from a second look.

Zero runtime dependencies (standard library only).

> The roadmap calls itself a very rough draft of in-progress thinking, and several of its numbers
> are explicitly best guesses. This package does not improve the quality of those guesses; it makes
> them easy to use, and checks that the arithmetic around them holds together. It is independent of
> the authors. If you are one of them and see a mistake in the reproduction, please open an issue.

## Install

```bash
pip install git+https://github.com/AnonRish/roadmap-calc      # or: pip install -e .
roadmap-calc --version
```

Python 3.10+.

## What the reproduction found

Of 24 checkable figures, **20 reproduce, 2 reproduce approximately, 2 do not** (full table:
[`docs/REPRODUCTION.md`](docs/REPRODUCTION.md)):

```text
$ roadmap-calc reproduce
claim                                         stated  recomputed  diff     status
--------------------------------------------  ------  ----------  -------  ------------------------
safety_accel_at_itai                          2.2     1.933       -0.267   not_reproduced
safety_accel_at_superhuman_coder              6.7     5.078       -1.62    not_reproduced
avg_accel_itai_to_sc_rough                    3       2.823       -0.177   reproduced
avg_accel_itai_to_sc_production               2.8     2.823       +0.0232  reproduced
extra_years_itai_to_sc                        2       2           +0       reproduced
safety_accel_at_min_h                         10      10          +0       reproduced
avg_accel_sc_to_min_h                         4.8     4.857       +0.0575  approximately_reproduced
extra_years_sc_to_min_h                       3.8     3.8         +0       reproduced
harness_equivalent_years                      15      15.81       +0.811   approximately_reproduced
years_equivalent_itai_to_sc                   3       3           +0       reproduced
years_equivalent_sc_to_min_h                  5       4.857       -0.143   reproduced
phase1_areas_sum                              100     100         +0       reproduced
... (all percentage sums reproduce exactly)

20 reproduced, 2 approximately reproduced, 2 not reproduced
The stated safety-acceleration endpoints would follow from AI R&D accelerations of about 3.7x and 23.8x at the stated exponent.
```

The one clear discrepancy: the page models safety R&D acceleration as
(AI R&D acceleration)^0.6 and uses AI R&D accelerations of about 3x (ITAI) and 15x (superhuman
coder). Those inputs give 1.93x and 5.08x, but the page states 2.2x and 6.7x. Everything *downstream*
(the 2.8x and 4.8x averages, the extra-year estimates) is consistent with the stated 2.2x/6.7x, so
the likeliest explanation is that the inputs were meant to be about 3.7x and 24x (or the exponent or
definitions differ from what the page spells out) rather than an error that propagates. Only the
authors can say which.

All effort-portfolio percentages (Phase 1 and Phase 2, every sub-bullet) add up exactly.

## Calculators

```text
$ roadmap-calc risk --speedup 7 --field both --modifier neuralese
marginal_risk at 7x: 5.82%  [interpolated: log-linear interpolation between 3x and 10x]
  after modifiers (neuralese; combine=max): 11.63%
p_scheming at 7x: 12.22%  [interpolated: log-linear interpolation between 3x and 10x]
  after modifiers (neuralese; combine=max): 24.45%
Values between table rows are this tool's convention, not numbers from the source.

$ roadmap-calc tolerance --max-risk 3
waiting until 3x costs a marginal risk of 3% (within 3%); the next row up exceeds it

$ roadmap-calc portfolio --phase 1 --fte 12          # largest-remainder allocation of 12 people
control                                         4
analogies                                       2
usefulness_and_deference                        2
misc_science                                    3
evals_and_demos                                 1

$ roadmap-calc portfolio --interpolate 0.5           # halfway between Phase 1 and Phase 2
control                          24.00%
analogies                        18.00%
...
```

```python
from roadmap_calc import load_data, lookup, apply_modifiers, allocate

data = load_data()
estimate = lookup(data.risk_table, 7)               # Estimate(pct=5.82, kind='interpolated', ...)
apply_modifiers(estimate.pct, ["neuralese"], data.risk_modifiers)   # 11.63
allocate(data.phase2, 40, level="leaves")           # whole-person split of 40 people
```

### What is the source and what is convention

| From the page | The tool's convention (always labelled as such in output) |
|---|---|
| The five table rows (1.15x, 1.5x, 3x, 10x, 22x) and their marginal risk and P(scheming) | Anything *between* rows: log-linear interpolation by default, or `--mode conservative` (next row up) / `previous` |
| "<1%" at 1.15x | Treated as an *upper bound*: results derived from it say so (`kind = upper_bound`) |
| One adjustment factor per observation (garbled chain of thought ×1.5, neuralese ×2, CoT trained to look nice ×1.5) | How several adjustments combine: `max` (default) applies only the largest; `multiply` compounds them; results are capped at 100% |
| The two portfolios' percentages | Whole-person allocation (largest-remainder rounding); interpolation between phases by area id, a missing area counting as 0% |

Speedups above 22x are rejected: the table does not extend there.

## Data and provenance

[`src/roadmap_calc/data/roadmap-2026.json`](src/roadmap_calc/data/roadmap-2026.json) holds the
transcription (retrieved 2026-10-10), with every number as a string so it parses exactly. The
tests check it against a second, separately typed copy of the table and both portfolios (double
entry), validate its internal consistency (monotone risk columns, sums, unique ids), and fail if
`docs/REPRODUCTION.md` is out of date. If the page changes, edit the JSON, run
`python scripts/make_reproduction.py`, and the tests tell you what else moved.

## How it is verified

[`docs/ASSURANCE.md`](docs/ASSURANCE.md) maps claims to evidence;
[`docs/VERIFICATION_REPORT.md`](docs/VERIFICATION_REPORT.md) is the output of the last full run
(lint, strict type checking, tests with 100% line and branch coverage, wheel build, clean-venv
install and CLI smoke test, Python 3.10–3.13). Highlights: the closed-form time-average is checked
against Simpson integration with Hypothesis (which found, and the tests now pin, a catastrophic-
cancellation bug for nearly equal endpoints); apportionment is checked for exact totals and
within-one-unit shares; risk look-ups are checked for monotonicity and continuity; and the key
reproduction verdicts are pinned. Reproduce with `scripts/verify.sh`.

## Limits

- A transcription as of the retrieval date; the page may have changed since.
- Risk numbers are the authors' best guesses under stated assumptions (roughly current
  architectures, un-garbled text outputs); nothing here validates them.
- "Reproduced" means the page's figure follows from the page's stated inputs under a plausible
  reading; it is not a statement about whether the model is right.
- Interpolation and combination rules are conventions, not source content.
- Research-grade software; independent of the roadmap's authors.

## Development

```bash
python -m pip install -e ".[dev]"
scripts/verify.sh "roadmap-calc validate"
python scripts/make_reproduction.py
```

## License

MIT — see [LICENSE](LICENSE).
