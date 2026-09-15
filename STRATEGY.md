# VEGA Strategy Card (one page)

**Name:** VEGA — Cross-Venue Net-of-Carry Dislocation
**Track:** Alpha Factory → Arbitrage · **Status:** frozen protocol v1.0, forward test pending

## Edge (one sentence)
Thin retail liquidity clears the same US-stock perp independently on three
venues; the resulting carry-adjusted dislocations mean-revert with ~1h
half-life, and the trade is market-neutral by construction.

## Signal
z = (venue's log-price gap vs 3-venue consensus, minus 6h-forward signed
funding differential to venue-mean, ÷ EWMA σ of its changes).
|z| ≥ 2 → fade.

## Portfolio
Short rich leg (sell its bid) + long cheap leg (buy its ask), 500 USDT per
leg, 1x, paired entry same second, exit paired 6h later. Up to 2 concurrent
episodes/symbol; 13 symbols pre-declared.

## Risk & failure modes (pre-declared)
- **Spread inversion:** if recorded weekend spreads > gross edge (TSLA
  gross ~78 bps; needs round-trip spread+fees < 54 bps) → dead. This is
  the #1 killer; forward tape decides.
- Funding spike legs: carry subtracted at actual settlements only.
- Venue outage at exit: paired fill missing → FAILURE row, kept in
  denominator, position assumed held to next fill (worst-case mark).
- SPY negative control outperforming strong names → suspect methodology
  contamination, halt claims.
- Simultaneous same-direction episodes across symbols = factor shock, not
  13 independent bets → day-clustered inference only.

## Metrics that matter
Net bps/episode (4-way itemized), t_cluster, hit%, episodes/week,
worst-leg drawdown, SPY-control margin.
