# Partition-safe IBD — resisting network partitioning during initial block download

## TL;DR

Finalize the downloaded chain only once its chainwork since the checkpoint clears

    C  ≥  max( 100 · w ,  w0 · T/600 )

    C   =  the candidate's chainwork since the checkpoint t0
    D̂   =  estimated difficulty now, from the spine (see below)
    w   =  D̂ · 2³²     work of one block at that difficulty
    w0  =  D0 · 2³²     work of one block at the checkpoint difficulty D0
    T   =  t_now − t0   the checkpoint's age, from the node's clock

Estimate `D̂` from a trailing **3-year** growth rate (uncapped — over-estimating
only delays finalization). The bar holds for roughly **3 years** against a ~1%
attacker (median checkpoint; ~1.5 years at 34%, and shorter for some
checkpoints). Past that a node must adopt a newer checkpoint (upgrade) or fail
closed rather than finalize.

## The idea

A node doing initial block download has no independent way to know that the
chain it is pulling is the chain the network is on. It trusts its peers — so an
eclipse, or a network partition that leaves it talking only to a fork's peers,
can feed it a chain that looks valid but is not the best chain. The node finds
out too late, when it reorgs out of transactions it had already treated as
settled.

Partition-safe IBD removes that trust **for finality** — the node still fetches
the chain, but never asks its peers whether it is the best one. The node ships
with a **trusted header spine**: Bitcoin's real headers, hard-coded up to a
checkpoint `t0`. From the spine it knows the network's historical **work rate**,
and so can estimate how much work the network is doing *now*. It then refuses to
finalize the chain it is downloading until that chain proves it carried
comparable work — at least the work of `THETA = 100` blocks at the **estimated
current** difficulty:

```
C  ≥  THETA · w          w = the work of one block at the estimated current difficulty D̂
```

This is the **coinbase-maturity assumption applied to sync**: the network already
treats producing 100 blocks at the current difficulty as out of reach, which is
why a coinbase may be spent after 100 confirmations. We estimate the current
difficulty on the high side, so the bar never under-counts, and anyone able to
clear it could equally have reverted Bitcoin's last 100 blocks — a strictly more
damaging attack we take to be practically impossible. The node needs only the
spine and its own clock.

Two properties do the work:

* the spine is **fixed at compile time**, so a partition cannot rewrite it;
* the bar is denominated in **current** difficulty, which the spine lets the node
  *estimate* but an attacker cannot *forge* — work has to be hashed.

The one real design question is how far a *fixed* bar holds as the checkpoint
ages. The reorg-equivalence argument above says nothing about time, and a fork's
accumulated work grows with the elapsed time `T` while the 100-block bar stands
still — so the constant is eventually overtaken. The fix is to let the bar grow
with `T`, which is the statistical argument of §2 and adds the second term to the
rule. Overshoot only delays finalization, but the guarantee still cannot last
forever.

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
  may come in at most `1/s` low — ~100× for a 1% attacker, but only ~3× for 34%
  ([`estimator.png`](diagrams/estimator.png)).

---

## 1. The setup

![setup](diagrams/concept.png)

The node holds a spine of real headers to `t0` (one per retarget period is
enough). A candidate that descends from the spine is accepted iff its work since
`t0` clears the bar. The node sees only one chain, so the honest chain and an
`s`-share fork are indistinguishable except through their work.

Work is measured in hashes: a block at difficulty `D` contributes `D · 2³²`. Write
`W_cand` for the candidate's chainwork since `t0`, `w = D̂ · 2³²` for one block at
the estimated current difficulty, `w0 = D0 · 2³²` for one block at the checkpoint
difficulty, and `THETA = 100` for the block bound. The node's test is
`W_cand ≥ THETA · w`. Everything turns on the ratio of the bar to what the honest
chain would have done (`W_honest`), a single dimensionless number:

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
raises `Phi`: it costs availability, never safety.

## 2. Why a fixed bar is overtaken

![why the bar must grow](diagrams/bars.png)

The honest chain and an `s`-fork both accumulate work in proportion to the
elapsed interval,

```
W_honest(T) ≈ (T/600) · G · w0            (T/600 = target blocks in the interval)
W_fork(T)   =  s · W_honest(T)
```

so a **constant** bar `100·w` is crossed by the fork once its work reaches it,
`s · W_honest(T) ≥ 100 · w`.

The protection horizon is finite and shrinks with the attacker's share (median
over checkpoints since 2011):

| rule | s=0.1% | s=1% | s=10% | s=34% |
|---|---|---|---|---|
| fixed 100 blocks (`100·w`) | 1.7 y | 0.2 y | 6 d | 2 d |
| **age bar (flat bar)** | **5.2 y** | **3.4 y** | **2.4 y** | **1.5 y** |
| log-log trend fit (OLS) + 2 sd | 2.5 y | 0.3 y | 15 d | 4 d |

The spread across checkpoints is wide: for the age bar, the worst tenth of
checkpoints hold only 2.0 y at `s=1%` and 0.3 y at 34%, so read these as medians,
not guarantees.

![protection horizon](diagrams/horizon.png)

Solving `Phi > s` gives the horizon

```
T_hi(s) ≈ 600 · THETA · rho / (G · s),
```

i.e. a fork of share `s` clears a constant bar once it has mined for that long.
Because `T` sits in the numerator, **no constant bar can hold** — the margin is
forced to scale with `T`, which is exactly why the second term (`w0·T/600`)
exists. A constant bar of 100 blocks survives only to `T ≤ 60000 · rho/(G·s)`.

## 3. The age bar is far stronger, and what it costs

The second term, `w0 · T/600`, is `T/600` blocks at the checkpoint difficulty
`D0` — the work a chain running at `D0` would have done. It asks `T/60000` times
more than 100 current-difficulty blocks — 43× at 30 days, 526× at a year.

![security](diagrams/security.png)

| fraction of historical checkpoints a fork PASSES | 1% fork | 34% fork |
|---|---|---|
| fixed 100 (`100·w`), at 90 d | **95%** | 100% |
| fixed 100 (`100·w`), at 1 y | **100%** | 100% |
| age bar, at 90 d | 0% | 5% |
| age bar, at 1 y | 3% | 22% |
| age bar, at 2 y | 13% | 51% |

The cost is availability — the flat bar denies the true chain in drawdowns
(`G<1`) and under short-interval block-count variance:

![availability](diagrams/availability.png)

| fraction of checkpoints that DENY the true chain | 1–7 d | 30 d | 90 d | 1 y | 2 y |
|---|---|---|---|---|---|
| fixed 100 (`100·w`) | 0% | 0% | 0% | 0% | 0% |
| age bar (flat) | 29% | 27% | 16% | 7% | 0% |

(The recommended `max(100·w, w0·T/600)` differs from the pure flat bar only for
`T ≲ 17 h`, where the 100-block floor delays the honest chain by design; it adds
no security there, since the flat bar is already safe at short staleness.)

So it is a clean trade: **the fixed bar buys availability at all staleness by
giving up security after days-to-weeks; the age bar gives up a little
availability early and stays secure for years.** Because delayed finalization is
acceptable (§1), the age bar is the better operating point, and the 100-block
rule is best used as its floor:

```
bar(T) = max( 100 · w ,  w0 · T/600 )
```

## 4. The estimate must not under-shoot by more than `1/s`

Whatever the bar's shape, `rho` enters `Phi` directly. The bar must sit between
the fork's work (`s·W_honest`) and the honest chain's (`W_honest`), a window of
width `1/s`, and `rho` scales the bar. Over-shooting `rho` only delays
finalization; the danger is under-shooting — the bar sinks toward the fork. So the
estimate may come in at most `1/s` **low**: 100× for a 1% attacker, only ~3× for
34%.

The estimators compared are a **flat** guess (`D̂ = D0`), a **growth** guess that
extrapolates the trailing window's growth rate, and a **log-log trend** — a
straight-line fit of `log10(difficulty)` against `log10(age since genesis)` over a
trailing window (i.e. an ordinary-least-squares, OLS, regression) extrapolated to
`t0+T`; the `+2 sd` variant adds two standard errors of slack to bias it high.
The table ladders `D̂/D_true` (estimate against the difficulty it is trying to
predict); §1's `rho = D̂/D0` is relative to the checkpoint, and the two differ by
the growth factor `G`.

![estimator](diagrams/estimator.png)

| 5–95% range of `log10(D̂/D_true)` (dex; 2.0 = 100×) | 30 d | 90 d | 1 y | 2 y |
|---|---|---|---|---|
| flat (no growth) | 0.2 | 0.7 | 2.5 | 3.8 |
| growth, 2 y window | 0.3 | 0.9 | 3.8 | 5.0 |
| growth, 3 y window | 0.2 | 0.7 | 2.1 | 2.2 |
| growth, 4 y window | 0.2 | 0.7 | 2.2 | 3.6 |
| growth, 2 y capped 2×/yr | 0.2 | 0.7 | 2.5 | 3.7 |
| log-log trend (OLS), 4 y | 2.5 | 2.3 | 3.1 | 4.5 |
| log-log trend (OLS), 4 y + 2 sd | 2.1 | 2.1 | 2.3 | 2.7 |

Reading: the **flat** estimate under-shoots whenever difficulty grows (the only
unsafe direction); the **growth** windows keep the error to a factor of ~100 out
to two years, with **3 years the sweet spot**; the **log-log trend (OLS)** is poor
even at one day because the fit's value at `t0` can sit far from actual
difficulty. Note that **capping growth is counter-productive**: it forces
under-shoot at long staleness (the unsafe direction) to buy availability the
design does not need, since over-shoot only delays finalization. A plain window,
uncapped, is better.

The number that matters is the low tail of the error, not the spread. For the
3-year estimator the 5th percentile is only ~1.9× low at 90 days — inside the
34% tolerance (2.9×) — and ~4.6× low at a year, still inside the 1% tolerance
(100×). The table's "spread" is a two-sided summary; only its lower end bears on
safety.

## 5. Real forks, and the late-split bound

BCH/BSV/XEC carry Bitcoin's genuine prefix work, then their own. "shared prefix"
is the fraction of the candidate's own work that is Bitcoin's (mined before the
fork's split); each cell is candidate work / bar, so `<1` = caught.

| fork, checkpoint | shared prefix | age bar | fixed 100 |
|---|---|---|---|
| BCH, 2017-03 | 6% | **0.86** | 4.3e3 |
| BCH, 2017-08 (at split) | 0% | **0.44** | 2.1e3 |
| BCH, 2018-01 | 0% | **0.22** | 996 |
| XEC, 2020-01 | 98% | **0.16** | 554 |

The age bar catches every real fork from a checkpoint near or after the split;
the fixed 100-block bar never does. But that is not sufficient: if the checkpoint
predates the split, the shared prefix hands the fork genuine work, and when the
prefix spans most of the interval it alone can clear the bar (BCH at a 2014-12
checkpoint = 8.95× the age bar). The closer the split sits to the checkpoint, the
smaller that head start — XEC at 2020-01 is only ten months before its split and
is caught (0.16×). So a sound checkpoint must post-date any live fork, and by a
wide margin.

## 6. Recommended rule

1. Ship a spine to `t0`; anchor `D0`.
2. Estimate current difficulty from the **trailing 3-year growth rate** `g`,
   uncapped: `D̂ = D0 · g^(T/1 year)`. Over-estimating is safe, so do **not** cap
   growth — a cap forces under-estimation at long staleness.
3. Finalize iff

   ```
   W_cand(t0 → tip)  ≥  max( 100 · w ,  w0 · T/600 )
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
  timestamps only certify work. A fixed bar at *checkpoint* difficulty
  (`100·w0`, i.e. `D̂ = D0`) is clock-free — its one genuine advantage over the
  rule here.
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
