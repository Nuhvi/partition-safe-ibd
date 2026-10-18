# Partition-safe IBD — resisting network partitioning during initial block download

## TL;DR

A node can safely finalize a proposed best chain despite possibility of network partitioning,
once its chainwork since the checkpoint clears

    C  ≥  max( 100 · w ,  w0 · T/600 )

    C  =  candidate chainwork since the checkpoint
    w  =  D̂ · 2³²   one block at current difficulty; estimate D̂ from the spine
                     via the trailing 3-year growth rate (no cap — over-estimating
                     only delays finalization)
    w0 =  D0 · 2³²   one block at the checkpoint difficulty
    T  =  t_now − t0   staleness (the node's clock)

Good for roughly **3 years** against a ~1% attacker, or ~1.5 years against 34% attacker;
beyond that a node must adopt a newer checkpoint (upgrade) or fail closed rather
than finalize.

## The idea

A node doing initial block download has no independent way to know that the
chain it is pulling is the chain the network is on. It trusts its peers — so an
eclipse, or a network partition that leaves it talking only to a fork's peers,
can feed it a chain that looks valid but is not the best chain. The node finds
out too late, when it reorgs out of transactions it had already treated as
settled.

Partition-safe IBD removes that trust **without needing the network**. The node
ships with a **trusted header spine**: Bitcoin's real headers, up to a
compile-time checkpoint `t0`. From that spine it knows the network's historical
**work rate**, and can therefore estimate how much work the network is doing
*now*. It then refuses to finalize the chain it is downloading until that chain
proves it carried comparable work — at least the work of 100 blocks at the
**current** difficulty since `t0`.

With

    C  =  the candidate's chainwork since the checkpoint (the sum of its blocks' work)
    w  =  the work of one block at the estimated current difficulty D̂  =  D̂ · 2³² hashes
    THETA  =  100 blocks — the coinbase-maturity bound

the node accepts the candidate iff  `C ≥ THETA · w`.

This is the **coinbase-maturity assumption applied to sync**. We set the bar to
the work of the last 100 blocks at current difficulty — and estimate that
difficulty on the high side, so the bar never under-counts. Anyone able to clear
it could equally have reverted Bitcoin's most recent 100 blocks, a strictly more
damaging attack we already take to be practically impossible; so is this one.
The node needs only the spine and its own clock — no live data, no peer trust.

Two properties do the work:

* the spine is **fixed at compile time**, so a partition cannot rewrite it;
* the bar is denominated in **current** difficulty, which the spine lets the node
  *estimate* but an attacker cannot *forge* — work has to be hashed.

The one real design question is how far this holds as the checkpoint ages. The
bar is deliberately conservative — we over-estimate difficulty, which can only
delay finalization — but a fork's accumulated work grows with the elapsed time
`T` while difficulty, and so the bar, may not keep up, so the guarantee cannot
last forever.

A node whose spine is older than that limit must either **upgrade** — trusting a
newer, subjective checkpoint shipped in the new binary — or **fail closed**,
refusing to finalize rather than settle a chain it cannot vouch for. A horizon of
a few years is only usable if nodes upgrade on roughly that cadence; that is a
deployment assumption, not something this study measured.

The rest of this note finds that limit and backtests it on Bitcoin's real
history. (Experiments and lab notebook: [`../research`](../research).)

## What the study showed

* A **fixed** 100-block bar is overtaken with age: a minority fork keeps mining,
  so its work grows hour by hour while the bar stands still. It holds a 1%
  attacker for only ~70 days and a 34% attacker for ~2 days
  ([`horizon.png`](diagrams/horizon.png)).
* So the bar must grow too. Keep 100 blocks as a **floor** and add the work a
  chain at the checkpoint difficulty would have done over the checkpoint's age
  `T = t_now − t0` — that is `T/600` blocks (`600` seconds per block, so ~17 h
  buys 100). The bar is the larger of the two, `max(100·w, w0·T/600)`; past
  ~17 h the age term wins and forks stay out for **years instead of days**
  ([`bars.png`](diagrams/bars.png), [`security.png`](diagrams/security.png)).
* The fragile part is guessing *today's* difficulty. Over-estimating is safe — it
  only delays finalization. Under-estimating is what hurts: the bar sinks toward
  the fork's work, which is a share `s` of the honest chain's, so the estimate
  may come in at most `1/s` low — ~100× for a 1% attacker, but only ~3× for 34%.
  On real history a trailing 3-year growth rate stays inside that for a few
  months (5–95% error ≈1.7× at 30 days, ≈5× at 90); a plain log-log trend is off
  by ~200× even at one day ([`estimator.png`](diagrams/estimator.png)).

---

## 1. The setup

![setup](diagrams/concept.png)

The node holds a spine of real headers to `t0` (one per retarget period is
enough). A candidate that descends from the spine is accepted iff its work since
`t0` clears the bar. The node sees only one chain, so the honest chain and an
`s`-share fork are indistinguishable except through their work.

Work is measured in hashes. Write **`w = D̂ · 2³²`** for the work of one block at
the estimated current difficulty, **`w0 = D0 · 2³²`** for one block at the
checkpoint difficulty, `THETA = 100` for the block bound, and `W_honest` for the
candidate's chainwork since `t0`. The bar is `THETA · w`. Everything reduces to a
single dimensionless number,

```
Phi(t0,T) = bar / W_honest = THETA · w / W_honest(t0, t0+T)
          = 600 · THETA · rho / (G · T)                     T in seconds

G(T)   = mean difficulty over [t0,t0+T] / D0      (how much difficulty grew)
rho    = D̂ / D0                                   (the node's estimate vs its start)
```

* the **honest** chain finalizes iff `Phi ≤ 1`;
* a fork of hash share `s` is kept out iff `Phi > s`.

So the rule is correct exactly on the band

```
s  <  Phi(t0,T)  ≤  1                  (safe band)
```

Too small and a fork slips through; too large and even the honest chain is
denied. `Phi` falls as `T` grows, so the band is a **window in staleness**
([`window.png`](diagrams/window.png)). Controlled overshoot of `D̂` (`rho>1`)
raises `Phi`: it costs availability, never safety — as the brief says.

## 2. Why a fixed bar is overtaken

![why the bar must grow](diagrams/bars.png)

The honest chain and an `s`-fork both accumulate work in proportion to the
elapsed interval,

```
W_honest(T) ≈ (T/600) · G · w0            (T/600 = target blocks in the interval)
W_fork(T)   =  s · W_honest(T)
```

so a **constant** bar `100·w` is crossed by the fork once

```
s · W_honest(T) ≥ 100 · w     ⟺     T ≥ T_hi(s) ≈ 600 · THETA · rho / (G · s).
```

The protection horizon is finite and shrinks with the attacker's share (median
over checkpoints since 2011):

| rule | s=0.1% | s=1% | s=10% | s=34% |
|---|---|---|---|---|
| fixed 100-block | 1.7 y | 0.2 y | 6 d | 2 d |
| **age bar (flat bar)** | **5.2 y** | **3.4 y** | **2.4 y** | **1.5 y** |
| conservative OLS + 2 sd | 2.5 y | 0.3 y | 15 d | 4 d |

The spread across checkpoints is wide: for the age bar the unluckiest tenth hold
only 2.0 y at `s=1%` and 0.3 y at 34%, so read these as medians, not guarantees.

![protection horizon](diagrams/horizon.png)

Equivalently, solving `Phi > s` for the demanded number of blocks `m`:

> **To exclude a share-`s` fork at staleness `T`, the node must demand at least
> `m(T) ≥ s · G · T / (600 · rho) ≈ s · T/600` blocks of current-difficulty
> work — a fraction `s` of the blocks mined in the interval.**

A constant `m = 100` satisfies this only for `T ≤ 60000 · rho/(G s)`. The
principle the brief calls "adjust the margin based on how far in the past"
is therefore not optional: **the margin has to scale with `T`.**

## 3. The age bar is far stronger, and what it costs

Set `m(T) = T/600` (the "flat bar": work at checkpoint difficulty). It asks
`T/60000` times more work than 100 fixed blocks — 43× at 30 days, 526× at a year.

![security](diagrams/security.png)

| fraction of historical checkpoints a fork PASSES | 1% fork | 34% fork |
|---|---|---|
| fixed 100-block, at 90 d | **95%** | 100% |
| fixed 100-block, at 1 y | **100%** | 100% |
| age bar, at 90 d | 0% | 5% |
| age bar, at 1 y | 3% | 22% |
| age bar, at 2 y | 13% | 51% |

The cost is availability — the flat bar denies the true chain in drawdowns
(`G<1`) and under short-interval block-count variance:

![availability](diagrams/availability.png)

| fraction of checkpoints that DENY the true chain | 1–7 d | 30 d | 90 d | 1 y | 2 y |
|---|---|---|---|---|---|
| fixed 100-block | 0% | 0% | 0% | 0% | 0% |
| age bar (flat) | 29% | 27% | 16% | 7% | 0% |

So it is a clean trade: **the fixed bar buys availability at all staleness by
giving up security after days-to-weeks; the age bar gives up a little
availability early and stays secure for years.** Because delayed finalization is
acceptable (§1), the age bar is the better operating point, and the 100-block
rule is best used as its floor:

```
bar(T) = max( 100 · w ,  w0 · T/600 )
```

## 4. The estimator may under-shoot by at most `1/s`

Whatever the bar's shape, `rho` enters `Phi` directly. The bar must sit between
the fork's work (`s·W_h`) and the honest chain's (`W_h`), a window of width `1/s`,
and `rho` scales the bar. Over-shooting `rho` only delays finalization; the danger
is under-shooting — the bar sinks toward the fork. So the estimate may come in at
most `1/s` **low**: 100× for a 1% attacker, only ~3× for 34%.

![estimator](diagrams/estimator.png)

| 5–95% spread of `log10(D̂/D_true)` | 30 d | 90 d | 1 y | 2 y |
|---|---|---|---|---|
| flat (no growth) | 0.2 | 0.7 | 2.5 | 3.8 |
| growth, 2 y window | 0.3 | 0.9 | 3.8 | 5.0 |
| growth, 3 y window | 0.2 | 0.7 | 2.1 | 2.2 |
| growth, 4 y window | 0.2 | 0.7 | 2.2 | 3.6 |
| growth, 2 y capped 2×/yr | 0.2 | 0.7 | 2.5 | 3.7 |
| OLS log-log, 4 y | 2.5 | 2.3 | 3.1 | 4.5 |
| OLS log-log, 4 y + 2 sd | 2.1 | 2.1 | 2.3 | 2.7 |

Reading: the **flat** estimate under-shoots whenever difficulty grows (the only
unsafe direction); the **growth** windows keep the error to ~2 decades out to two
years, with **3 years the sweet spot**; the **OLS trend** is poor even at one day
because the fit's value at `t0` can sit far from actual difficulty. Note that
**capping growth is counter-productive**: it forces under-shoot at long staleness
(the unsafe direction) to buy availability the design does not need, since
over-shoot only delays finalization. A plain window, uncapped, is better.

## 5. Real forks, and the late-split bound

BCH/BSV/XEC carry Bitcoin's genuine prefix work, then their own. (candidate work / bar; `<1` = caught)

| fork, checkpoint | shared prefix | age bar | fixed 100 |
|---|---|---|---|
| BCH, 2017-03 | 6% | **0.86** | 4.3e3 |
| BCH, 2017-08 (at split) | 0% | **0.44** | 2.1e3 |
| BCH, 2018-01 | 0% | **0.22** | 996 |
| XEC, 2020-01 | 98% | **0.16** | 554 |

The age bar catches every real fork from a checkpoint near or after the split;
the fixed 100-block bar never does. But **if the checkpoint predates the split**,
the shared prefix alone clears either bar (BCH at a 2014-12 checkpoint = 8.95×
the age bar) — the late-split bound of the prior analysis. A sound checkpoint
must post-date any live fork.

## 6. Recommended rule

1. Ship a spine to `t0`; anchor `D0`.
2. Estimate current difficulty from the **trailing 3-year growth rate** `g`,
   uncapped: `D̂ = D0 · g^(T/1 year)`. Over-estimating is safe, so do **not** cap
   growth — a cap forces under-estimation at long staleness.
3. Finalize iff

   ```
   W_candidate(t0 → tip)  ≥  max( 100 · w ,  w0 · T/600 )
   ```

   i.e. **100 current blocks and at least the work a checkpoint-difficulty chain
   would have done.** For `T > ~17 h` the second term dominates: the rule is the
   flat bar, with the 100-block term as the first-hours floor.
4. Refresh the checkpoint. The protection horizon is finite (`T_hi(s)` above);
   a stale binary is only safe because it *also* demands more work, and no
   work-since-`t0` rule survives an arbitrarily long staleness.

## Caveats

* **Late split.** A checkpoint older than a fork split hands the fork its prefix
  for free; no work-since-`t0` rule can help. Checkpoint freshness is the fix.
* **The clock.** `T` and any tip-age gate come from the node's clock; header
  timestamps only certify work. The pure fixed bar with `D̂=D0` is clock-free —
  its one genuine advantage.
* **`THETA`.** 100 is a *reversal* cost, not a *partition* cost; the two do not
  scale the same way in `T`. Treat 100 as a floor, not the whole bar.
* **Data.** 481 two-week BTC samples; fork series are 25/25/16 points, so the
  fork table is illustrative.
* **`1/s` floor.** Even a perfect bar cannot separate a fork once `s ≥ Phi`; the
  accuracy requirement makes very small `s` at long staleness unattainable.

## Reproduce

```sh
python3 -m venv .venv && .venv/bin/pip install matplotlib
cd research && ../.venv/bin/python run_all.py     # writes research/figures/*.png
```

| script | what it shows |
|---|---|
| `research/model.py` | spine, work, estimators, `bar`, `Phi`, `finalize_time` |
| `research/exp1_window.py` | `Phi(T)`, the safe band, the staleness window |
| `research/exp2_estimator.py` | estimator error vs staleness, tolerance lanes |
| `research/exp3_backtest.py` | availability + security rates, `Phi` heatmap |
| `research/exp4_forks.py` | protection horizon, real forks, late splits |
| `research/exp5_bars.py` | concept and "why the bar must grow" diagrams |
