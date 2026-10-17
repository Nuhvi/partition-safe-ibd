# partition-safe-ibd

A node that is network-partitioned (say, it can only reach Bitcoin Cash peers)
should know that it *cannot yet finalize* blocks, instead of silently following a
minority chain.  This repo measures whether a trusted Bitcoin header history is
enough for it to tell, using difficulty (hash-rate) history alone.

## The rule

Fit a power law to trusted BTC difficulty over a trailing window of `W` years
ending at the last trusted checkpoint.  For a candidate tip:

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
the implementation.

## Findings

**Forks are caught out to about two years of staleness.**  Worst-case margin over
BCH, BSV and XEC at W = 4:

![chainwork grid](diagrams/chainwork_grid.png)

**The real chain passes.**  At W = 4 the live BTC chain sits at `q` = −0.17 …
+0.15 dex against bands of 0.65, 0.69, 0.94 and 1.73 dex for staleness h = 0.5,
1, 2 and 4 years.

**Walk-forward coverage** (band fixed on tests before the cutoff, scored after;
nominal 95 %), W = 4: 100, 100, 94 % at h = 0.5, 1, 2 (cutoff 2018); 92 % at
h = 4 (cutoff 2020).

**Bands (dex)**

| W | h=0.5 | h=1 | h=2 | h=4 | h=10 |
|---|-------|-----|-----|-----|------|
| 2y | 1.07 | 1.66 | 1.89 | 2.51 | 8.56 |
| 4y | 0.65 | 0.69 | 0.94 | 1.73 | 3.98 |
| 8y | 0.65 | 0.78 | 1.02 | 1.40 | n/a |

At W = 4 the band stays ≤ 1 dex to one year of staleness and ≤ 2 dex to three and
a half; W = 2 holds ≤ 2 dex to one year; W = 8 has no window reaching ten years.
The ten-year numbers rest on six windows.

**Attack cost at the band edge.**  A forger must produce `Wtr / 10^band` work
across the whole interval, not one block:

| h (W = 4) | cost | ≈ network-days |
|-----------|------|----------------|
| 0.5y | $2.3 B | 59 |
| 1y | $3.9 B | 102 |
| 2y | $3.1 B | 81 |
| 4y | $0.52 B | 14 |

($0.04/TH/day; one day of Bitcoin's present hash rate ≈ $38 M.)  A block-level
attacker under Bitcoin's real retarget path reproduces the closed form: $2.27 B
simulated against $2.26 B at a 30 % hash share, h = 0.5.

**Detection latency.**  Below the rate edge `10^−band` the gate fires at the
first check, about one hour:

![detection latency](diagrams/detection_latency.png)

A 50 % fork escapes 86 % of 7-day traces at a 0.94 dex band.

**Attack budget.**  A fork can accumulate at most its own hash over the elapsed
interval.  Using the collective non-BTC SHA256d hash (BCH + BSV + XEC; median
≈ 1 % of Bitcoin, 2018 peak ≈ 30 %, ≈ 0.4 % today):

![fork hash share](diagrams/fork_hash_share.png)

With `M = log10(attacker work / trend work) + band`, `M ≥ 0` means a fork with
that era's non-BTC hash would pass.  Over every historical window:

![attack budget](diagrams/attack_budget.png)

* The median window is safe to ≈ 5 years of staleness; from ≈ 4–5 years the
  median margin crosses zero.
* The most attacker-favourable window (2018–2020, when the non-BTC share was
  10–78 % work-weighted) passes at every staleness.
* An upward break of the real chain lowers the bar (`g > 0`); a downward break
  raises it, so it costs availability — refusing to finalize — rather than
  safety.

Anchoring on the trusted chain's own recent work instead of a fit — accept iff
the work since the checkpoint is at least `10^−k`× the work in the equal period
before it, with `k` set so the true chain keeps 95 % — removes the extrapolation
blow-up entirely and is safe against the historical collective for staleness
≤ 3 years (margin below zero on every window); it turns positive from ≈ 4 years.

## Limitations

* **Same PoW only.**  Cross-PoW `chainwork` is not comparable.
* **Near-even splits.**  A 50/50 fork is the same ambiguity as any work-based
  rule; asymmetric splits are caught in about `τ`.
* **Staleness.**  The band grows with checkpoint age and the attack cost falls
  with it — 1.73 dex and $0.52 B at four years, 3.98 dex at ten.
* **Clock trust root.**  Freshness uses the node's clock; header timestamps are
  attacker-chosen within MTP and `now + 2 h`.
* **Regime shifts.**  BTC has drawdowns in which the true chain leaves a tight
  band; the band is empirical for this reason.
* **Security share, not legitimacy.**  A valid minority chain is still a valid
  chain.
* **The historical fork chains are not clean controls.**  BCH, BSV and XEC each
  changed difficulty policy at or near their fork, so their post-fork difficulty
  is not purely a hash-rate measurement.

## Repo and running

```
fetch.py             # cache difficulty series -> data/<chain>.json
finality.py          # the rule: statistic, isotonic band, decide()
chainwork.py         # report and figures for the rule
forks.py             # non-BTC SHA256d hash share of Bitcoin
budget.py            # attack budget: can the non-BTC hash fool the rule
simulate.py          # detection-latency backtest
attack_sim.py        # block-level attacker under the real retarget path
checkpoints.txt      # trusted BTC header spine
data/  diagrams/     # cached series and generated PNGs
```

```sh
python3 fetch.py            # BTC offline; BCH/XEC Blockchair; BSV a public node
python3 finality.py         # bands, live decision, envelopes
python3 chainwork.py        # bands, coverage, attack cost, grid figure
python3 forks.py            # non-BTC hash share + figure
python3 budget.py           # attack-budget margins over historical windows
python3 simulate.py         # detection-latency backtest
python3 attack_sim.py       # attacker under the retarget path
```

Install: `python3 -m venv .venv && . .venv/bin/activate && pip install matplotlib`.
Scripts print their reports without matplotlib and skip only `savefig`.
