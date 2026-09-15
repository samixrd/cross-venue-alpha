# VEGA — Cross-Venue Net-of-Carry Dislocation
**Flagship · Alpha Factory → Arbitrage · Bitget AI Hackathon S2**

Same US-stock perpetual, three exchanges. When they disagree, one of them
is wrong — VEGA trades the disagreement, never the direction.

```
D_{v,t} = log P_v − ⅓ Σ log P        venue dislocation vs 3-venue consensus
Ḑ       = D − carry(funding, actual settlements, signed)
z        = Ḑ / EWMA_σ(ΔḐ)
|z| ≥ 2 → paired fade: SHORT rich venue (its bid) / LONG cheap venue (its ask)
          exit 6h, both legs real quotes, 500 USDT/leg
PnL_net = spread − 24bps fees − funding − slippage − impact
```

Universe: **13 common symbols, pre-declared** (no cherry-picking).
SPY = declared negative control. Trigger |z|≥2 is pre-specified, not
"optimal". Formula frozen in `PROTOCOL.md` before any executable tape
existed.

## Evidence state (honest, as of 2026-09-16)

| Layer | Status |
|---|---|
| Mid-price convergence, 42–120d history | **STRONG** — cluster-robust t 7.0–9.5 (TSLA/NVDA/AAPL), placebo negative, sign-shuffle ≈ 0, half-life ≈ 1h |
| Net-of-carry (actual settlement rates) | **STRONG** (funding differentials subtracted, not assumed) |
| Historical executable bid/ask | **UNAVAILABLE** — no venue stores it. Anyone who says otherwise backtested a fantasy |
| Forward executable (real 3-venue quotes) | **PENDING** — collector running now; verdict pre-declared: net>0 AND ≥5 weekend pair episodes AND SPY control behaving |

**VEGA claims no alpha until the tape says so.** The mid-mode backtest
(48 bps fee+spread floor) already shows −15 to −44 bps: *if spreads are
wide, this dies* — that's the falsifier, published in advance.

## Layout
```
data/          venue_index.json (13 syms x 3 venues, 1h bars + funding) + tape/
research/      index_build, lead-lag, dislocation, battery, cluster inference
strategy/      signal.py (frozen §1) · execution.py (§3) · backtest.py (mid mode)
tape/          hash-chain collector output (bid/ask/depth, 5-min weekends)
verification/  root manifests, verify scripts
PROTOCOL.md    frozen research protocol v1.0 (hash-locked)
STRATEGY.md    one-page strategy card
```

Baseline A (Weekend Desk, directional after-hours): github.com/samixrd/weekend-desk
— independent evidence stream, neither result explains the other post-hoc.

All public data, no API keys — every number re-computable from `research/`.
