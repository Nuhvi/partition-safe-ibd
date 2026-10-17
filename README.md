# partition-safe-ibd

Trend-based chain justification for header-compatible SHA256d chains.  A node
that is **network-partitioned** (e.g. it can only reach Bitcoin Cash peers)
should be able to tell that it *cannot yet finalize* blocks, rather than
silently following a minority chain.  This repo explores doing that from
**difficulty (hash rate) history alone**, using a trusted header history as a
reference trend.

The idea: over any multi-year window, the dominant chain's difficulty grows
along a fairly stable power law.  A minority fork does not — its hash rate
fraction erodes, so its difficulty falls ever further *below* that trend.  Judging
an incoming chain therefore reduces to measuring how far below the trusted trend
its difficulty sits, compared with the uncertainty band of the trend itself.

> Companion: the same problem also has a *work-share* solution (`fork_work.py`
> in the project this was extracted from, `partition` mode), which compares
> cumulative chainwork against a live anchor.
> The trend approach here is different in one important way: it needs **no live
> connection to the dominant chain**, so it keeps working *while you are
> partitioned*.  That is exactly the scenario this is for.

---

## 1. Which chains are comparable

Only chains that share Bitcoin's 80-byte header layout and SHA256d proof of work
have directly comparable difficulty / `chainwork`:

| chain | name | split from | fork height | fork date |
|-------|------|-----------|-------------|-----------|
| **BTC** | Bitcoin | — | — | 2009-01-03 (genesis) |
| **BCH** | Bitcoin Cash | BTC | 478558 | 2017-08-01 |
| **BSV** | Bitcoin SV | BCH (shares the BTC prefix) | 556766 | 2018-11-15 |
| **XEC** | eCash (BCHA) | BCH | 661648 | 2020-11-15 |

Merged-mined chains (e.g. Namecoin) are **excluded**: their SHA256d work is
shared with Bitcoin rather than independent, so their difficulty is not an
independent hash-rate measurement.  Scrypt/X11 chains (Litecoin, Dogecoin, Dash)
are excluded for a different reason — different PoW, so `chainwork` is not
comparable.

## 2. Data

* **BTC** — the checkpoint spine `checkpoints.txt`, copied into this repo from
  the parent repo's `crates/core/data/checkpoints.txt`: one header every 2016
  blocks, full history, offline.  (Difficulty is read straight from the `bits`
  field.)
* **BCH, XEC** — the [Blockchair](https://blockchair.com/api/docs) API, one
  request per sampled height (free tier ≤ 30 requests / 60 s, so the fetcher
  throttles itself).
* **BSV** — a public Bitcoin SV JSON-RPC node (`getblockheader`).

`fetch.py` caches everything to `data/<chain>.json` as
`[[height, unix_time, difficulty], ...]`.

> A caution discovered while building this: `bch.mempool.space` and
> `xec.mempool.space` both currently serve **Bitcoin mainnet** data (identical
> block hashes to `mempool.space`), so they are unusable for BCH/XEC.

## 3. Method

Fit, in log–log space, a power law to the trusted chain over a trailing window of
`W` years:

```
log10 difficulty = a + b · log10( t )        t = years since genesis
```

Then judge any chain by its **residual** at time `x`:

```
r(x) = log10 difficulty_chain(x) − (a + b · log10 x)
```

The uncertainty of the fitted line is the OLS **prediction interval**:

```
band(x) = m · s · sqrt( 1 + 1/n + (log10 x − x̄)² / Sxx )
```

where `s` is the fit's residual standard error, `n` the number of points, and
`(log10 x − x̄)²/Sxx` the **extrapolation penalty** — zero inside the fit window,
growing as you predict further outside it.  This automatically does what a node
should do: demand a tighter fit when it has more history, and widen its
expectations the older its trusted checkpoints are.

**`m` must be calibrated.**  Bitcoin difficulty is autocorrelated and
regime-shifting, so the raw OLS interval (m = 2) *under-covers*: measured
coverage of the true chain is only 30–90 % depending on window and staleness.
`calibrate()` measures the empirical 95th-percentile inflation factor `m(W, h)`
from BTC's own history, where `h` is the staleness (years since the fit window
ended).  `m` is forced monotone non-decreasing in `h` (a band cannot shrink as a
model ages).

### Decision rule

Two independent gates, both required before finalizing:

```
stale tip / low work rate       → do NOT finalize; the chain is not keeping up
r(x) ≥ −band(x)                 → consistent with the dominant chain; may finalize
r(x) <  −band(x), sustained     → minority / partitioned; do NOT finalize,
                                  keep looking for peers that extend the anchor
```

The first gate is what covers a fork that does **not** change its difficulty
algorithm.  Such a chain inherits the parent's target, so its difficulty — and
therefore its residual — still matches the trend; but with a small hash-rate
share its blocks arrive hours or days apart.  The August 2026 BIP-110 split is
the clean example: it left Bitcoin at height 961 632 (an exact retarget
boundary), inherited the new epoch's difficulty, produced two blocks, then
stalled, while its difficulty residual stayed at zero.  Only tip age / work rate
distinguishes it.  (That fork left no usable series, so this is the shape of the
case, not a backtest — see §8.)

The residual gate covers the opposite case: a fork with a per-block DAA keeps a
fresh tip by cutting difficulty, which appears as a large negative residual.

The two gates are complementary.  Apply freshness to a trailing window rather
than a single block — a stalled chain can produce one lucky block with a current
timestamp, but `Δchainwork / Δt` over the window still exposes the gap — and
take `τ` as a small multiple of the target block interval.  A quarter of the
hash rate, the case that used to read as "days–weeks of latency", shows up
either as a ~4× lower target or as ~40-minute blocks, and a window of headers
resolves it in hours — in principle; this part is analytic and not yet
backtested (§8).  A chain that is merely behind because it is still syncing
is handled by *not finalizing yet*, not by calling it invalid.

`band` should also be inflated by the time-elapsed-since-last-refit (staleness),
which is exactly what the `h` axis of `tightness_vs_staleness.png` shows.  Every
band in §4–§6 uses `m_band()`, which applies the monotone guard (§4).

## 4. Results

### Difficulty, log–log — `diagrams/difficulty_loglog.png`

![difficulty](diagrams/difficulty_loglog.png)

All four chains share history until their respective forks, then diverge.  By
2026-08:

| chain | difficulty | BTC / chain | residual vs BTC trend |
|-------|-----------|-------------|-----------------------|
| BTC | 1.33 × 10¹⁴ | 1× | 0 (reference) |
| BCH | 4.30 × 10¹¹ | 309× | ≈ −2.5 dex |
| BSV | 3.17 × 10¹⁰ | 4196× | ≈ −3.6 dex |
| XEC | 6.34 × 10⁹ | 20 900× | ≈ −4.3 dex |

### Residuals vs a rolling 4-year BTC trend — `diagrams/residual_rolling.png`

![residuals](diagrams/residual_rolling.png)

This is the key picture.  The **true chain's residual is bounded** — it wanders
inside the shaded band (and through the 2011–2015 era is *outside* it, which is
why the band must be calibrated, not assumed), then hugs zero in the modern era.
The **forks' residuals are unbounded and monotone**: once a fork exists they fall
away from the trend without limit.

That asymmetry — bounded vs unbounded — is what makes the method robust to an
imperfect or somewhat stale model: you are not asking "does this match exactly",
you are asking "does this diverge without bound".

### The fork examples are illustrative, not clean controls

BCH, BSV and XEC show the long-run end state — a minority chain far below the
trend — but none of them is a clean test of a fork that simply *keeps going
slowly*:

* **BCH** launched in Aug 2017 with an Emergency Difficulty Adjustment (20 %
  cuts when blocks were slow), replaced in Nov 2017 by a per-block DAA.
* **BSV** forked from BCH in Nov 2018 already carrying BCH's per-block DAA.
* **XEC** forked from BCH in Nov 2020 with ASERT (`aserti3-2d`).

Their difficulty therefore falls quickly after the split **by design**, and their
early residuals measure that policy as much as hash-rate share.  Their long-run
hash rate also tracks market price, so a low residual is not purely a partition
effect.  The cleaner natural experiment is the opposite case: a fork that keeps
inherited difficulty and goes slow — see the BIP-110 split under the decision
rule, where the residual stays on the trend and only tip age / work rate exposes
the chain.  That fork stalled after two blocks, so it is not in `data/` (there is
no series to fit), but it is exactly the case the difficulty-only view would
miss.

### Fit tightness required vs staleness — `diagrams/tightness_vs_staleness.png`

![tightness](diagrams/tightness_vs_staleness.png)

The 95 % band you need, as a function of how old the trusted checkpoints are, for
history windows `W` = 2, 4, 8 years.  Two competing effects:

* **More history → smaller `σ` and slower band growth** (W=8 stays under ~1 dex
  even after 6 years of staleness), but a slightly wider band at zero staleness.
* **Less history → tiny `σ` but fast growth** (W=2 is tight now, ~1.5 dex after
  5 years).

Practical sweet spot: **W = 4–8 years**.  Reference points: ×10 = 1.0 dex,
×100 = 2.0 dex.  Beyond ~5 years of staleness the calibration is thin (few fit
windows in BTC's history reach that far), so treat those values as indicative.

### A node booting at (start year, checkpoint staleness) — `diagrams/start_grid.png`

![start grid](diagrams/start_grid.png)

This is the answer to *"what if a new node starts at some point in history with
`S` years of stale checkpoints before its first sync?"*  For each cell we fit the
trend to BTC up to `start − S` and ask (a) how wide the 95 % band is, and (b)
whether the fork chains that exist by then fall outside it.

Reading it (W = 4y):

* **Left** — required band half-width in dex.  A node starting in 2020+ with
  ≤2 years of staleness needs only ~0.2–0.8 dex; one starting in 2018 with 6
  stale years needs ~6 dex.
* **Right** — detection margin = fork divergence − band.  Green (>0) means the
  minority chain would have been flagged; red means it would have been mistaken
  for consistent.
  * Starting 2020 or later with ≤2y staleness: **every fork caught**.
  * Starting 2018 with 3–6y staleness (fit lands on the 2012–13 ramp): **missed**
    — those windows extrapolate badly.
  * The row for staleness 8 at 2026 is looser than its neighbours because the
    specific `[2014, 2018]` fit window happens to be unusually smooth; this
    variability is real and is why a single scalar threshold should be derived
    per-fit, not assumed.

Two caveats on this figure.  The right panel takes the **best** case over the
three forks (`max`); the worst-case (`min`) margins are smaller — the thinnest
claimed cell, start 2020 with 2y staleness, is +0.46 dex best-case but +0.38
worst-case.  And the grid only asks whether *forks* fall outside the band; it
never checks whether the **true** chain stays inside it, which it does not in
every window (see below).

### Calibration is weaker than it looks — `calibration_audit.py`

Every "95 %" in this section is **in-sample**: `calibrate()` takes the 95th
percentile of the same overlapping fit windows it then scores, so coverage is
true by construction, and the monotone guard extrapolates a noisy in-sample tail.
Fixing `m` on windows before a cutoff and scoring after it gives, for W = 4
(nominal 95 %):

| staleness h | 0 | 1 | 2 | 3 |
|-------------|---|---|---|---|
| coverage after 2018 | 76 % | 53 % | 35 % | 18 % |

Support is thin at the top end too: 26 windows at h = 0 but 14 at h = 6 and 10 at
h = 8 for W = 4 (18 / 6 / 2 for W = 8).  And the true chain is flagged in about
2 of every 24–26 windows at each staleness — one of them is live.  BTC difficulty
peaked at 1.56 × 10¹⁴ on 2025-10-29 and is 1.33 × 10¹⁴ now; that is 0.22 dex
below a 1-year-stale trend against a 0.09 dex band, so **a node whose checkpoints
are 6–12 months old would flag real Bitcoin today** (W = 4 at h = 0.5–1, W = 2 at
h = 1).  The band is therefore both too tight in-sample and too optimistic out of
sample; the fix is walk-forward calibration with reported coverage, not a
percentile of the scoring set.  `calibration_audit.py` prints all of it: support
counts (A), walk-forward coverage (B), false positives including the live tip (C),
and worst-case fork margins (D).

## 5. Limitations

* **Same PoW only.**  The comparison is meaningless across different PoW.
* **Near-even splits.**  Right after a split *every* fork's residual is small by
  construction (it shares the trend), but that is only a latency for the
  difficulty channel.  A chain with a small hash-rate share is caught quickly by
  the tip-age / work-rate gate: it must either cut difficulty (large negative
  residual) or keep inherited difficulty and produce blocks hours apart (stale
  tip).  What remains genuinely ambiguous is a fork holding a large share of the
  hash rate — a near-50/50 split, where both chains produce recent tips at
  similar difficulty.  That is the same 50/50 problem as any work-based rule.
  The "hours" figure here is analytic, not yet backtested (§8).
* **Staleness.**  Confidence in the *difficulty* band is a decreasing function of
  years since the last trusted checkpoint: beyond ~2 years a small fork can hide
  inside it, and beyond ~5 years the calibration itself is thin.  The tip-age /
  work-rate gate does not decay with staleness — but its trust root is the
  **node's clock**, not the candidate's headers: header timestamps are
  attacker-chosen within MTP and `now + 2 h`, so an eclipsed node with a skewed
  clock is attackable through it.  That is why the two gates age differently.  At
  ten years the band stops being the defender's margin and becomes the forger's
  budget: see §6.
* **Regime shifts.**  BTC difficulty has drawn-downs (2011, 2015, 2018, 2022)
  where the true chain also leaves a tight band; this is why the band is
  calibrated empirically and why "sustained" divergence is required.
* **It ranks security share, not legitimacy.**  A heavy-but-minority chain is
  still a valid chain; this only measures whether it holds a dominant share of
  hash rate.

## 6. Attack cost at 10-year staleness

What if the trusted checkpoints are 10 years old?  `attack_cost.py` answers that,
and the answer is uncomfortable: the band that protects against a stale model is
also the forger's budget.  A chain passes if its difficulty is no more than
`band` dex below the trend, so the forger only has to sit at the **bottom edge**
of the band and does not need to approach Bitcoin's hash rate at all.

Setup: checkpoints end 2016-09-12 (height 429 408), candidate tip 2026-09-19
(height 967 680; BTC difficulty 1.33 × 10¹⁴, network ≈ 950 EH/s).  Prices are at
$0.04 per TH/s per day (≈ $40/PH/day), i.e. rented SHA-256 hash, and scale
linearly with it.

Bands go through `m_band()` (§3), which applies the monotone guard over the full
staleness grid.  That detail changes the answer: `calibrate()` only enforces "a
band cannot shrink as the model ages" across the `h` values it is handed, so
asking it for a single `h` skips the guard.  The guarded value is the running
maximum of the raw percentile over all smaller `h`, so at 10 years it is set by
whichever staleness estimated widest (raw → guarded: 17 → 21 for W = 2, 7 → 11
for W = 4).

| W | band (raw → guarded) | `D_min` / BTC tip | H for 10-min tips | 1 block | 1 day | cumulative work |
|---|----------------------|-------------------|-------------------|---------|-------|-----------------|
| 2y | 2.89 → **3.62** dex | 0.015 % | 0.14 EH/s (0.015 %) | $39 | $5.6 k | $4.4 M |
| 3y | 3.35 → **4.56** dex | 0.19 % | 1.8 EH/s (0.19 %) | $510 | $73 k | $37 M |
| 4y | 3.81 → **5.94** dex | 2.9 % | 27 EH/s (2.9 %) | $7.6 k | $1.1 M | $377 M |
| 5y | 1.42 → **4.90** dex | 2.1 % | 20 EH/s (2.1 %) | $5.6 k | $810 k | $319 M |
| 8y | undefined | — | — | — | — | no calibration window reaches h = 10y |

With the guard applied, **every** W = 2–5 keeps the true chain inside its own
band, so there is no "usable window" left to hide behind: a forger needs only
0.015–3 % of Bitcoin's hash rate.  (An earlier version of this section reported
W = 4–5 failing their own test and only W = 2–3 being usable; that was the
unguarded single-`h` artifact and is withdrawn.)

The cost depends on how much of the chain the node actually checks:

| what is checked | W = 2 | W = 3 |
|-----------------|-------|-------|
| tip difficulty + tip age only | ~$39 (one block) | ~$510 |
| sustained work rate, 1-day window | ~$5.6 k/day | ~$73 k/day |
| cumulative work from the anchor | ~$4.4 M | ~$37 M |
| — reference: Bitcoin's real 10-year work | ~$47 B | ~$47 B |

(W = 4 sits between the columns at $7.6 k / $1.1 M/day / $377 M.)  A forger needs
neither ten years nor Bitcoin's hash rate: if the rule looks only at the tip's
difficulty and freshness, a single block at the band edge — tens of dollars of
rented hash at W = 2 — clears both.  Requiring cumulative work since the anchor
raises the bar by the band factor (×4170 at W = 2), but does not remove it: at
ten years even that is single-digit millions, because the band is what sets the
price.  All of these are far below the ~$47 B that Bitcoin's own ten-year
chainwork would cost.

Two changes follow:

* **Cap staleness or absolute band width.**  Refuse to finalize once the band
  exceeds some absolute width, instead of letting it grow without bound.  A
  ten-year-old model is not a weak model; it is a different problem, and the
  cheap single-block attack is the symptom.
* **Require work, not just difficulty.**  Compare cumulative `chainwork` since
  the anchor with the trend's integral.  Difficulty is a point sample the forger
  can meet with one block; work is the quantity they cannot fake cheaply.

The tip-age / work-rate gate is the one part whose sensitivity does not decay
with staleness (§5), though its trust root is the node's clock, not header
timestamps.  The attack above is what remains — a forger who *does* keep tips
fresh — and its price is the band.

## 7. Files

```
partition-safe-ibd/
  fetch.py             # download/cache difficulty series -> data/<chain>.json
  analyze.py           # fit, calibrate, and draw all four diagrams
  attack_cost.py       # cost of a forged chain at a given checkpoint staleness
  calibration_audit.py # support, walk-forward coverage, false positives, margins
  checkpoints.txt      # trusted BTC header spine (one header per 2016 blocks)
  data/                # cached series (BTC, BCH, BSV, XEC)
  diagrams/            # generated PNGs
  README.md            # this file
```

### Running

```sh
python3 -m venv .venv && . .venv/bin/activate
pip install matplotlib          # and numpy (pulled in by matplotlib)

python3 fetch.py                # BTC is offline; BCH/XEC hit Blockchair, BSV a public node
python3 analyze.py              # writes diagrams/*.png and prints the band table
python3 attack_cost.py          # forged-chain cost at 10y staleness; args: [years] [$/TH/day]
python3 calibration_audit.py    # calibration support, coverage and false positives
```

`fetch.py` caches: delete `data/<chain>.json` to refetch.

## 8. Where this could go next

* Move the reference model (`a, b, s, x̄, Sxx, n, fit_end`) into a node's header
  validation path, alongside its trusted-checkpoint handling, together with a
  `calibrate()`-derived `m(W, h)` table, so a node can self-assess a partition.
* Replace instantaneous difficulty with **observed work rate**,
  `Δchainwork / Δt` over a trailing window (derived from headers, no extra data).
  Unlike difficulty, this is invariant to the DAA: a fork that lowers difficulty
  to keep 10-minute blocks and one that keeps inherited difficulty and produces
  slow blocks both show the same low work rate.  It also makes the tip-age gate
  statistically robust rather than a single-block check.
* Quantify **detection latency** for both gates as a function of hash-rate share
  and staleness: hours until work rate resolves an asymmetric fork, versus the
  near-50/50 case that stays ambiguous for many blocks.
* Require **cumulative `chainwork` since the anchor**, not only a work rate at
  the tip, and compare it against the trend's integral over the stale interval.
  Without it a forger can clear the difficulty gate with a single block (§6);
  with it the price becomes the band-edge work for the whole interval.
* **Recalibrate out of sample.**  `calibration_audit.py` shows the in-sample "95 %"
  is not coverage (W = 4 falls from 76 % to 18 % out of sample, h = 0 → 3), that
  support is thin at the top end, and that the true chain is flagged today once
  checkpoints are 6–12 months old.  Fit `m(W, h)` walk-forward, report coverage
  with a confidence interval, refuse to emit below a support threshold, and
  replace the monotone guard — a running max of noisy percentiles — with a
  smooth or upper-confidence band.
* Run a **synthetic Poisson backtest** of the freshness gate: block arrivals at
  hash share `f`, inherited difficulty, and a trailing-window `Δchainwork / Δt`
  test.  That is the missing evidence for the BIP-110-style "hours" claim in §3.
* Build a **block-level generator** with real retarget code (≤4× per 2016 blocks,
  MTP and `now + 2 h` limits) to confirm the closed-form §6 costs.
