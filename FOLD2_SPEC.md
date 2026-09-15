# VEGA — Fold 2 Spec (DECLARED, NOT YET ACTIVE)
Status: written 2026-09-16, executable evaluation may not begin before Fold 1's
forward verdict is published. Fold 1 (frozen |z|≥2 fade) runs unchanged until
then and is judged only on its own pre-declared terms.

## The boundary sentence (hard rule)
> **The state estimator may measure, summarize, and forecast execution/convergence
> conditions using only information available before the test episode. It may not
> alter the frozen VEGA trigger, universe, holding period, or directional rule in
> Fold 1. Any state-conditioned trading modification constitutes a new declared
> fold.**

## What Fold 2 will test (prospectively, one candidate)
W38 monitoring produced one observable market-state relationship, labeled
**market-state observation, not alpha discovery**:

```
larger median dislocation (7.9 → 13.8 bps)  ⇒  lower convergence (90% → 61%)
```

Candidate hypothesis for a future fold:

> Convergence probability is decreasing in episode dislocation magnitude
> beyond some level; trading |z| in the extreme tail of the state
> distribution has negative expectancy.

Fold 2, if and when opened:
1. Signal: still |z|≥2 fade; the ONLY addition is a state-conditioned
   skip (no new direction, no new asset, no horizon change).
2. State inputs: strictly pre-episode snapshot values (weekly aggregates
   available ≥ 1 episode before decision — Tuesday-snapshot → upcoming-
   weekend timing makes this structurally true).
3. Validation: prospective walk-forward only; Fold 1's tape episodes stay
   Fold 1's; no re-scoring of sealed history.
4. Falsifier pre-declared: skip-rule that does not improve net bps/episode
   AND keeps ≥5 weekend episodes ⇒ close Fold 2, Fold 1 stays canonical.

## Convergence definition (shared, exact — metric name means one thing)
An episode converges iff paired gross PnL > 0:
`((D_rich,t − D_rich,t+h) + (D_cheap,t+h − D_cheap,t))/2 > 0` (log units) —
the average absolute leg dislocation shrank over the hold. NOT zero-crossing,
NOT 50% capture, NOT full normalization. conv% = share of episodes with
positive paired gross.

## Fold ladder
```
Fold 1  frozen VEGA            (active, verdict Mon 21:45 UTC)
Fold 2  state-conditioned VEGA (this spec, dormant)
Fold 3  execution-aware adaptive sizing — only if Fold 2 earns it
```
Each fold independently declared, independently falsified. ML only from
Fold 2 onward, only as cost/state forecasting, never as alpha generator.
