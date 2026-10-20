# Partition-safe IBD

**Finalizing a downloaded chain without asking peers whether it is the best one.**

A node that bootstraps from scratch trusts its peers, because it has no local
history to check them against. An eclipse, or a partition that leaves it talking
only to a fork's peers, can feed it a chain that is valid but not the best one.

This removes that trust for **finality**. The node ships with a trusted header
spine up to a checkpoint $t_0$. It finalizes a downloaded chain only once that
chain proves it carried enough work since $t_0$. Work has to be hashed, so a
partition cannot forge it. The only other input is the node's clock.

## The setup

```text
spine (trusted)        t0 ──────────── T = now − t0 ───────────► now
 ━━━━━━━━━━━━━━━━━━━━━━━━●
                         │ honest  ▕██████████████████████▏ W_h        ✔ ≥ bar
                         │ bar     ▕┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄▏ r₀·ĥ(T)    ◄ threshold
                         │ fork    ▕████▏                   s·W_h      ✘ < bar
```

The diagram is schematic and not to scale. The trusted spine ends at $t_0$. After $t_0$ the honest network produces work
$W_h$, while a fork with share $s$ produces $s\,W_h$. The node knows
$T=t_{\text{now}}-t_0$ from its clock. The bar is a threshold on the work since
$t_0$.

## Estimate the work

The rule needs an estimate of the honest work over the anchor's age. The
estimate comes from a published Bitcoin price power law, converted to hashrate
with the `dbtc` relation:

$$
P(d)=10^{-17.432}d^{5.834},
\qquad
D=D_0\left(\frac{P}{P_0}\right)^{1/b},
\qquad b=0.673473.
$$

$d$ is days since genesis, $P$ is USD/BTC, and $D_0,P_0,b$ are the frozen
`dbtc` constants. The price-to-difficulty conversion follows
[dbtc](https://github.com/Nuhvi/dbtc). The resulting estimate is compared with
the realised hashrate from the spine:

![estimated hashrate](research/figures/estimated_hashrate.png)

The estimate is a trend, not a precise forecast. It is above the realised
hashrate before 2014, below it in 2015–2021; the **median** law (orange) is
close after 2022, while the **bottom** law (green) remains 2.5–4× low. On 2016+ checkpoints the bottom estimate is $0.08/0.22/0.34$ of
actual (p5/median/p95); the median is $0.21/0.60/0.90$.

Let $\hat h(T)$ be the cumulative power-law work since $t_0$, in checkpoint
blocks, and let

$$
r_0=\frac{H_{\text{est}}(t_0)}{H_{\text{actual}}(t_0)}.
$$

The **estimated-work bar** is

$$
\boxed{\;\text{bar}(T)=\max\!\left(100,\ r_0\,\hat h(T)\right)\;}.
$$

The $100$-block floor is the coinbase-maturity buffer; below about 17 hours it
binds, so the checkpoint instant is not a zero-work hole. $r_0$ is the
power-law level at the checkpoint, **not** a calibration to the actual
checkpoint hashrate: the bar is the absolute power-law work. Dropping $r_0$
would anchor the path to the actual checkpoint ($\text{bar}=\hat h$) and raise
the bar. The 5% test below uses the lower raw level. $r_0$ is a checkpoint
constant and can be shipped with the spine.

## The 5% rule

Let

$$
\Phi(T)=\frac{\text{bar}(T)}{\text{honest work}(T)}.
$$

The honest chain finalizes iff $\Phi\le 1$. A fork with **network** share $s$
holds $s/(1-s)$ of the honest work, so it finalizes iff

$$
\Phi\le \frac{s}{1-s}.
$$

The 5%-network line is $0.0526$; the 10%-network line is $0.1111$. A 5%
attacker is kept out when

$$
0.0526<\Phi\le 1.
$$

The estimated-work rule over the 2016–2024 checkpoints, with the worst sampled
anchor and the median-law version of it:

![estimated-work history](research/figures/estimated_work_history.png)

The all-checkpoint scan covers 285 sampled 2016+ checkpoints. Under the bottom
law the minimum is $\Phi=0.0546$ at 2018.53, so the maximum safe **network**
share is 5.18%; 5% is safe with a 3.7% margin. **6% is not safe.** The 10%
network line is crossed in 2016–20 under the bottom law. Under the median law
the minimum is $\Phi=0.150$, so 10% is safe, and the 2024 anchor's observed
2.7-year endpoint is $\Phi\approx1.03$ (marginal). The 5% result is therefore
bottom-law, in-sample, and thin; it is not an absolute “conservative” claim.
5% is simply the largest round network share below the sampled 5.18% edge.

## The cost of 5%

A 5% attacker is a 5% share of the network. It has two costs per year:

* **energy cost** — 5% of the network's energy at 25 J/TH and \$0.05/kWh;
* **opportunity cost** — the block rewards it gives up by not mining the real
  chain.

![5% cost](research/figures/cost_5pct.png)

| year | energy cost | rewards foregone | profit foregone |
|---:|---:|---:|---:|
| 2016 | \$1M | \$26M | \$26M |
| 2017 | \$3M | \$125M | \$121M |
| 2018 | \$20M | \$249M | \$229M |
| 2019 | \$36M | \$240M | \$204M |
| 2020 | \$65M | \$229M | \$164M |
| 2021 | \$80M | \$778M | \$698M |
| 2022 | \$121M | \$456M | \$335M |
| 2023 | \$210M | \$473M | \$263M |
| 2024 | \$349M | \$682M | \$333M |
| 2025 | \$508M | \$837M | \$329M |
| **2016–25** | **\$1.40B** | **\$4.10B** | **\$2.70B** |

The figure stacks energy cost plus foregone profit; their sum is the rewards
foregone. Capex is excluded; this is an energy/opportunity estimate, not a
rental or acquisition quote. The 5% share is below the bar (the bar requires
more than 5% of network work), so this spend cannot create the bar. The table
prices the 5% share, not the bar; the bar's share is the $\Phi$ above.

## Limits

* **The estimate is in-sample and not exact.** The price law is fitted on the
  same history used for the backtest; the bottom law is the security worst case
  (lowest bar), not a liveness guarantee. The median law already gives
  $\Phi\approx1.03$ at the 2024 observed endpoint.
* **5% is thin, not a wide margin.** The sampled edge is 5.18% network; 5% has a
  3.7% margin. 6% is not safe. The claim is “5% passes the sampled bottom-law
  backtest,” not “5% is conservative.”
* **The honest chain has to stay live.** The rule is useful only while
  $\Phi\le1$. There is no 5-year extrapolation in the figure or the table; the
  2024 observed 2.7-year endpoint is 0.386 under the bottom law and 1.03 under
  the median.
* **The $T=0$ floor and re-anchoring.** The 100-block floor prevents a
  zero-work finalization at $T=0$. Re-anchoring resets $T$ but not the floor.
* **The clock and the checkpoint header.** The node must check that the
  candidate's header at $t_0$ matches the spine, and must treat its clock as a
  trust input; a backward clock skew lowers the bar.
* **The cost is not the bar's cost.** The 5% attacker spends 5% of the network;
  the bar demands more. That gap is the security.
* **No consensus change.** The bar is a local finality policy; nodes must share
  the same spine and $r_0$ to agree.

## Deployment

1. Ship a spine to $t_0$; this is the trust root.
2. Ship $r_0$ (or the checkpoint price and hashrate) with the spine.
3. Read $T=t_{\text{now}}-t_0$ from the clock.
4. Compute $\text{bar}(T)=\max(100, r_0\,\hat h(T))$ checkpoint blocks.
5. Check that the candidate's header at $t_0$ matches the spine; compare its
   chainwork since $t_0$, divided by $w(t_0)$ (or multiplied by $w(t_0)$), with
   the bar.
6. Finalize iff it is at least the bar. Re-anchor on each cleared batch; $T$
   resets but the 100-block floor remains.

## Reproduce

```sh
python3 -m venv .venv
.venv/bin/pip install matplotlib numpy
cd research
../.venv/bin/python run_all.py
```

The scripts are `estimated_hashrate.py`, `estimated_work_history.py`,
`estimated_work_backtest.py`, and `cost_5pct.py`; `model.py` is the spine and
the estimated-work bar. Data is in `research/data/`.
