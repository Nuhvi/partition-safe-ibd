# partition-safe-ibd

A node that is network-partitioned (say, it can only reach Bitcoin Cash peers)
should know that it *cannot yet finalize* blocks, instead of silently following a
minority chain.  This repo asks whether difficulty (hash-rate) history alone can
tell it, using a trusted Bitcoin header history as the reference trend.

## Bottom line

**Don't grade the tip's difficulty.  Grade the work the candidate has done since
the trusted checkpoints, against the work the trend says it should have done in
the time the node has been waiting.**

* The tip-difficulty rule looks fine in-sample and fails in practice.  Its
  walk-forward coverage is 18–76 % (nominal 95 %), and it flags **real Bitcoin
  today** once its checkpoints are 6–12 months old.
* The work rule fixes that.  The live chain is accepted at every staleness
  tested, walk-forward coverage is 92–100 %, and a forged chain sitting at the
  band edge costs **$0.5–3.9 B** (14–102 network-days) instead of one block.
* **Recommended operating point: W = 4 years, checkpoints at most 1 year old**
  (band 0.93 dex; 3.5 years if you accept a 1.54 dex band).  The tip-difficulty
  rule has no valid operating point at all.
* Still hard: near-even splits (a 50 % fork escapes 86 % of 7-day traces) and
  very stale checkpoints.  Cap staleness; the band is the attacker's budget.

| | tip-difficulty rule | work-since-anchor rule |
|---|---|---|
| live BTC accepted today? | **no** at 6–12 months | yes |
| walk-forward coverage (W = 4) | 18–76 % | 92–100 % |
| forged chain at the band edge | not passable under real retarget | $0.5–3.9 B (h ≤ 4y) |
| valid operating envelope | none | W = 4, h ≤ 1 y |

## 1. What this is

Only chains sharing Bitcoin's 80-byte header and SHA256d proof of work have
directly comparable difficulty: **BTC, BCH, BSV, XEC**.  Merged-mined chains
(shared PoW) and scrypt/X11 chains are excluded.

`checkpoints.txt` is the trusted BTC spine — one header every 2016 blocks, full
history, offline.  BCH/XEC difficulty comes from the Blockchair API and BSV from
a public node; everything is cached in `data/<chain>.json` as
`[[height, unix_time, difficulty], ...]`.

## 2. The rule

Fit a power law to trusted BTC difficulty over a trailing window of `W` years.
For a candidate tip, with the anchor at the last trusted checkpoint:

```
T   = t_now − t0                     elapsed, from the NODE's clock
dC  = C1 − C0                        candidate work since the anchor
Wtr = ∫ D_tr(t) · 2³²/600 dt         trend work over [t0, t_now]
q   = log10(dC) − log10(Wtr)
```

Finalize only if **all** of:

```
dC ≥ 2³² · D0            the chain has actually grown
q ≥ −band(W, h)          h = T in years; band is one-sided
tip age ≤ τ              τ ≈ a few block intervals
```

Elapsed time is the node's clock, so header timestamps cannot shorten the
interval — they only certify work.  `band` is calibrated on `q` for the true
chain and made non-decreasing in `h` by isotonic regression.  `finality.py` is
the canonical implementation; `chainwork.py` reports on it.

## 3. Results

### Forks are caught, and the real chain passes — `diagrams/chainwork_grid.png`

![chainwork grid](diagrams/chainwork_grid.png)

Worst-case fork margin over BCH/BSV/XEC.  Forks are caught out to ~2 years of
staleness; the right panel shows the real chain inside its own band everywhere
shown.  Beyond ~2 years the band is so wide that the forks pass too — staleness,
not a property of the forks.

### Bands and coverage

| W | h=0.5 | h=1 | h=2 | h=4 | h=10 |
|---|-------|-----|-----|-----|------|
| 2y | 1.07 | 1.66 | 1.89 | 2.51 | 8.56 |
| 4y | 0.65 | 0.69 | 0.94 | 1.73 | 3.98 |
| 8y | 0.65 | 0.78 | 1.02 | 1.40 | n/a |

Walk-forward coverage at W = 4 (band fixed on tests before the cutoff, scored
after; nominal 95 %): **100 / 100 / 94 %** at h = 0.5 / 1 / 2 (cutoff 2018) and
**92 %** at h = 4 (cutoff 2020).  Ten-year numbers rest on 6 windows and are
flagged thin by the script.

### Attacker cost

At the band edge the forger must produce `Wtr / 10^band` work across the whole
interval, not one block:

| h | chainwork interval | ≈ network-days |
|---|--------------------|----------------|
| 0.5y | $2.3 B | 59 |
| 1y | $3.9 B | 102 |
| 2y | $3.1 B | 81 |
| 4y | $0.52 B | 14 |

($0.04/TH/day; one day of Bitcoin's present hash rate ≈ $38 M.)  A block-level
attacker under the real retarget path confirms the closed form: **$2.27 B
simulated vs $2.26 B closed-form** at a 30 % hash share, h = 0.5.

### Detection latency

![detection latency](diagrams/detection_latency.png)

Below the rate edge `10^−band`, the work gate fires at the first check (~τ ≈ 1 h)
in every trace.  A genuine 50/50 split is the residual case: it escapes 86 % of
7-day traces at a 0.94 dex band.

### Operating envelope

| W | band ≤ 1.0 dex | band ≤ 2.0 dex |
|---|----------------|----------------|
| 2y | none | h ≤ 1y (1.85) |
| 4y | **h ≤ 1y (0.93)** | **h ≤ 3.5y (1.54)** |
| 8y | none | none |

The tip-difficulty statistic has no valid envelope at any `W`.

## 4. Why the obvious approach fails

The natural rule — compare the tip's difficulty with the trend — is a point
sample, and it is worse than it looks:

* **The calibration is in-sample.**  Scoring the same overlapping windows that
  produced the 95th percentile gives 95 % by construction.  Walk-forward, the
  difficulty band covers only 76/53/35/18 % (h = 0–3), and the true chain is
  flagged in ~2 of every 24–26 windows.
* **There is a live false positive.**  BTC difficulty peaked at 1.56 × 10¹⁴ in
  October 2025 and is 1.33 × 10¹⁴ now — 0.22 dex below a 1-year-stale trend
  against a ~0.1 dex band.  A node with 6–12-month-old checkpoints would reject
  real Bitcoin today.
* **"One block clears it" was an artifact.**  The closed form let the attacker
  pick the tip difficulty.  Under Bitcoin's real retarget (2016 blocks, 4×
  clamp) a fork's difficulty converges to its hash share, so at small `h` no
  sub-dominant fork passes the tip test at all — the rule is broken in both
  directions.  The work rule's closed form, by contrast, matches simulation.

BCH, BSV and XEC are useful illustrations of long-run divergence but not clean
controls: all three changed difficulty policy at or near the fork (BCH's EDA in
2017, BSV inheriting BCH's DAA, XEC with ASERT), and their hash rate tracks
market price.

## 5. Limitations

* **Same PoW only.**  Cross-PoW `chainwork` is meaningless.
* **Near-even splits.**  A 50/50 fork is the same ambiguity as any work-based
  rule; asymmetric splits are caught in about `τ`.
* **Staleness.**  Bands grow without bound and the attack gets cheaper.  Cap
  checkpoint age (W = 4, ≤ 1 year) — this is a requirement, not a caveat.
* **Clock trust root.**  Freshness uses the node's clock; header timestamps are
  attacker-chosen within MTP and `now + 2 h`, and an eclipsed node's clock is
  attackable.
* **Regime shifts.**  BTC has drawdowns where even the true chain leaves a tight
  band; that is why the band is empirical and the rule is one-sided.
* **It ranks security share, not legitimacy.**  A valid minority chain is still
  a valid chain.

## 6. Repo and running

```
fetch.py             # cache difficulty series -> data/<chain>.json
analyze.py           # original tip-difficulty fit and its four diagrams
attack_cost.py       # closed-form forged-chain cost at a given staleness
calibration_audit.py # in-sample vs walk-forward, false positives, margins
chainwork.py         # work-since-anchor report + diagrams
finality.py          # canonical rule: statistic, isotonic band, decide()
attack_sim.py        # block-level attacker under real retarget
simulate.py          # Poisson backtest of the freshness/work gate
checkpoints.txt      # trusted BTC header spine
data/  diagrams/     # cached series and generated PNGs
```

```sh
python3 fetch.py            # BTC offline; BCH/XEC Blockchair; BSV a public node
python3 finality.py         # rule, live decision, operating envelope
python3 chainwork.py        # bands, coverage, attack cost, grid figures
python3 simulate.py         # detection-latency backtest
python3 attack_sim.py       # attacker under the retarget path
python3 analyze.py          # the original (superseded) diagrams
python3 calibration_audit.py
python3 attack_cost.py
```

Install: `python3 -m venv .venv && . .venv/bin/activate && pip install matplotlib`.
Scripts print their reports without matplotlib and skip only `savefig`.

## 7. Open questions

* A trailing-window "sustained" variant, calibrated separately from the
  whole-interval rule.
* A full walk-forward band table with confidence intervals across every `W`,
  and an upper-confidence rather than point band.
* Wiring `finality.py` into a node's header validation alongside checkpoint
  handling, and testing near-even splits at the confirmation depth the node
  actually uses.
