# research/ — experiments for the partition-safe IBD rule

Lab notebook for the "100 blocks at current difficulty" idea. The polished
write-up is in [`../final`](../final); this folder is where the numbers came
from.

## Question

A node ships a trusted Bitcoin spine to a compile-time checkpoint `t0`, wakes up
at `t_now` possibly partitioned, estimates current difficulty `D̂` from the
spine, and finalises a candidate only if its work since `t0` is at least
`THETA·D̂·2³²` (`THETA=100`). How often does that deny the honest chain, and how
often does it let a fork through?

## Model (`model.py`)

* `Chain`: a sampled header spine; difficulty is a step function per 2016-block
  period. `work(a,b)` is realised chainwork in hashes (O(log n) via prefix sums).
* `ESTIMATORS`: ways to guess difficulty `T` ahead from `t ≤ t0` —
  `flat`, `exp-1y`, `exp-2y`, `exp-2y-cap2x`, `ols-4y`, `ols-4y+2sd`.
  `flatbar` is not an estimator: expressed as `D̂` it reproduces the
  age-proportional bar `D0·T/600·2³²`.
* `bar`, `phi`, `finalize_time`: the rule, the dimensionless ratio
  `Phi = bar/W_honest`, and the first staleness a candidate clears it.

Everything turns on `s < Phi ≤ 1`: honest finalises iff `Phi ≤ 1`, an `s`-fork
is kept out iff `Phi > s`.

## Experiments

| file | figure | gist |
|---|---|---|
| `exp1_window.py` | `window.png` | `Phi(T)` decreases; the safe set is a window `[T_lo, T_hi)`, ratio ≈ `1/s` |
| `exp2_estimator.py` | `estimator.png` | error of `D̂/D_true` vs `T`; tolerance lanes `±log10(1/s)` |
| `exp3_backtest.py` | `availability/security/phi_heatmap.png` | honest-denial rate and fork-pass rate over `(t0,T)` |
| `exp4_forks.py` | `horizon.png` | protection horizon `T_hi(s)`; BCH/BSV/XEC vs the bar |
| `exp5_bars.py` | `concept.png`, `bars.png` | schematics |

`run_all.py` runs everything. Requires matplotlib (`../.venv`).

## Raw observations

* Window ends (`exp-2y-cap2x`): `T_lo ≈ 13–17 h`, `T_hi(1%) ≈ 44–75 d`,
  `T_hi(34%) ≈ 39–51 h`; `T_hi/T_lo ≈ 80–113 ≈ 1/s`.
* Estimator spreads (5–95%) at 90 d / 2 y: flat 0.70/3.76, cap2x 0.67/3.71,
  ols-4y 2.25/4.49, ols-4y+2sd 2.12/2.67. Tolerance is 2.00 dex (1%) /
  0.47 dex (34%).
* Availability: fixed/capped never denies; the flat bar denies 29% at 1–7 d
  (drawdowns + block-count variance), 7% at 1 y, 0% at 2 y.
* Security at 1 y: fixed `cap2x` passes a 1% fork on ~100% of checkpoints; the
  flat bar on ~3%. At 34%: 100% vs ~22%.
* Real forks: from a 2017-08 BCH checkpoint the fork is 0.44× the flat bar
  (caught) but 2.1e3× the fixed bar (passes). XEC from 2020-01: 0.16× / 554×.

## Dead ends / notes

* **`max(100, flat)` is just the flat bar.** The 100-block floor only binds for
  `T < 17 h`, where it changes nothing (the flat bar already denies ~29%). It is
  harmless and intuitive but adds no security — recorded so it is not re-tried.
* **`min` is wrong**: it would let a fork through at short `T`.
* **Why not "100 blocks" with a bigger constant?** A larger `THETA` scales
  `T_hi` linearly, but any constant is still overtaken; only growth with `T`
  works. The required `m(T) ≈ s·T/600` blocks is the exact statement.
* The OLS trend estimator is surprisingly noisy *at zero staleness* (2.4 dex at
  1 day): the fitted trend at `t0` need not equal actual `D(t0)`. Prefer a
  trailing-window growth rate, not a global trend.

## Data

`data/BTC.json` (481 rows, one per 2016 blocks, genesis→2026-09) and
`data/{BCH,BSV,XEC}.json` (25/25/16 rows), copied from the parent repo's cache;
`data/checkpoints.txt` is the header spine. `BTC.work` reproduces the parent
`fetch.py`/`finality.py` convention.
