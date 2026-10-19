# research/ — experiments for the partition-safe IBD rule

Lab notebook for the "100 blocks at current difficulty" idea. The polished
write-up is in [`../README.md`](../README.md); this folder is where the numbers came
from.

## Question

A node ships a trusted Bitcoin spine to a compile-time checkpoint `t0`, wakes up
at `t_now` possibly partitioned, estimates the work of one block now, `ŵ`, from
the spine, and finalises a candidate only if its work since `t0` is at least
`THETA·ŵ` (`THETA=100`). How often does that deny the honest chain, and how often
does it let a fork through?

## Model (`model.py`)

* `Chain`: a sampled header spine; difficulty is a step function per 2016-block
  period. `work(a,b)` is realised chainwork in hashes (O(log n) via prefix sums)
  and `w(t)` is the work of one block, `D(t)·2³²`.
* `ESTIMATORS`: ways to guess the work of one block `T` ahead from `t ≤ t0` —
  `flat`, `exp-1y`, `exp-2y`, `exp-2y-cap2x`, `ols-4y`, `ols-4y+2sd`, and the
  recommended `plaw-4y` (power law anchored at `w0`, fitted over a trailing 4 y,
  lifted one-sided by its own max past residual). `flatbar` is not an estimator:
  expressed as `ŵ` it reproduces the age-proportional bar `w0·T/600`.
  `FIRST = 5 y` scopes the tests to 2014+ (post-ASIC).
* `plaw_window_rows` / `plaw_fit`: the one anchored power-law fit, shared by
  `plaw-4y` and the exp6/exp7 sweeps.
* `bar`, `phi`, `finalize_time`: the rule, the dimensionless ratio
  `Phi = bar/W_honest`, and the first staleness a candidate clears it.

Everything turns on `s < Phi ≤ 1`: honest finalises iff `Phi ≤ 1`, an `s`-fork
is kept out iff `Phi > s`.

## Experiments

| file | figure | gist |
|---|---|---|
| `exp1_window.py` | `window.png` | `Phi(T)` decreases; the safe set is a window `[T_lo, T_hi)`, ratio ≈ `1/s` |
| `exp2_estimator.py` | (table only) | error of `ŵ/w_true` vs `T`, the §4 table |
| `exp3_backtest.py` | `availability/security/phi_heatmap.png` | honest-denial rate and fork-pass rate over `(t0,T)` |
| `exp4_horizon.py` | `horizon.png` | protection horizon `T_hi(s)` |
| `exp5_bars.py` | `concept.png`, `bars.png` | schematics |
| `exp6_band.py` | `plaw_band.png` | the self-calibrated residual band, projected forward from several checkpoints |
| `exp7_window.py` | `plaw_window.png` | trend and error vs fit window (2 y … all history) |

`run_all.py` runs everything. Requires matplotlib + numpy (`../.venv`).

## Raw observations

* Work per block is a power law, not an exponential: log-log fit R² 0.96 over
  2014–2026 vs 0.83 for a straight line; the realised growth rate decays with
  age (a power-law signature), which the exponential over-shoots.
* Recommended estimator `plaw-4y` (2014+ checkpoints): `log10(what/wtrue)` 5th
  percentile is **+0.12 / +0.13 / +0.12 / +0.02** dex at 30 d / 90 d / 1 y / 2 y
  — **never under-shoots** — with median +0.33 / +0.35 / +0.52 / +0.76 (`exp-3y`
  for comparison: p5 −0.04 / −0.08 / −0.19 / −0.18, median +0.01 / +0.03 / +0.20
  / +0.51). The band is what removes the under-shoot, at the price of a heavier
  over-shoot (p95 to ~2.6 dex).
* Why 2014+: a fit to 2012–13 history badly under-predicts the ASIC transition
  (2013-05 → 2500× difficulty in 2 y), e.g. plaw-4y −2.4 dex at 2 y from 2013-01.
  The trailing-growth exponential *over*-shoots there (+0.2 to +1.3 dex) — it
  absorbs the boom — so pre-2014 is a real robustness edge for the exponential,
  paid for by its heavier over-shoot in the modern era.
* Window sweep (`exp7`, 2014+, 2 y ahead, p5 / median): 2 y −0.34/+0.27, 3 y
  −0.06/+0.57, 4 y +0.02/+0.76, 5 y +0.15/+0.88, 6 y +0.35/+1.28, 8 y +0.49/+1.64,
  all history +1.32/+1.75, all ≥2014 −0.01/+0.76. Longer window = safer low tail
  but more over-shoot; every window is inside the 34% tolerance. 4 y is where the
  low tail first clears zero; 3 y is the lower-delay option.
* Alternative power-law designs all lost to `exp-3y` on the full 2011+ sample —
  flat ×50 factor, global (whole-history) fit, statistical +2 sd band, and the
  `max(power law, exponential)` hybrid (identical to the exponential). The
  self-calibrated band on 4 y, evaluated 2014+, is the one that wins.

## Dead ends / notes

* **`max(100, flat)` is just the flat bar.** The 100-block floor only binds for
  `T < 17 h`, where it adds no security (the flat bar is already safe) and merely
  delays the honest chain. Recorded so it is not re-tried.
* **`min` is wrong**: it would let a fork through at short `T`.
* **Why not "100 blocks" with a bigger constant?** A larger `THETA` scales
  `T_hi` linearly, but any constant is still overtaken; only growth with `T`
  works. The required `m(T) ≈ s·T/600` blocks is the exact statement.
* The unanchored OLS trend is noisy *at zero staleness*: the fitted trend at
  `t0` need not equal actual `w(t0)`. Anchoring the fit at `w0` is what makes the
  power law usable.

## Data

`data/BTC.json` (481 rows, one per 2016 blocks, genesis→2026-09) is the only
data file; `BTC.work` reproduces the parent `fetch.py`/`finality.py` convention.
The figures written to `figures/` are what `../README.md` links to directly.
