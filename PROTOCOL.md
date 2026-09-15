# VEGA — Cross-Venue Net-of-Carry Dislocation
## Research Protocol v1.0 — FROZEN 2026-09-16 (before any executable observation)

Track: Bitget AI Hackathon S2 · Alpha Factory → **Arbitrage** (cross-platform
spread / same-underlying different-venue structure, per handbook).

---

## 0. The anomaly (market structure first, strategy derived)

The same US-stock perpetual trades on ≥3 venues around the clock. Venues
disagree by tens of basis points for hours at a time. There is an
identifiable reason this must exist: stock-perp liquidity is retail-thin,
each venue clears its own order flow, and funding mechanics differ. If
those disagreements revert to a common value, venue-relative value is a
mechanical, directional-free trading object.

**Research question:** Does the carry-adjusted, volatility-normalized
dislocation of a venue's price from the 3-venue consensus predict its
convergence to that consensus within 6 hours, on executable quotes, net
of all costs?

## 1. Frozen formula (v1 — no estimator changes until a NEW fold)

For symbol i, hour t, venues v ∈ {bitget, binance, bybit}:

```
F_t    = (1/3) Σ_v log P_{v,t}                    # consensus fair price (ARITHMETIC MEAN
                                                  # frozen for fold 1; weighted/median
                                                  # estimators are future folds, not edits)
D_{v,t}= log P_{v,t} − F_t                        # venue dislocation
Carry_{v,t} = Σ_{h=1..6} (fund_{ref,t+h} − fund_{v,t+h})   # signed settlement convention,
Ḑ_{v,t}= D_{v,t} − Carry_{v,t}                    # actual funding timestamps only; missing
                                                  # => row flagged, carry not invented
z_{v,t}= Ḑ_{v,t} / EWMA_σ(ΔḐ, λ=0.97)             # shock units
TRIGGER: |z_{v,t}| ≥ 2                            # PRE-SPECIFIED RESEARCH TRIGGER —
                                                  # "2" is not claimed optimal
ACTION:  fade the pair — short rich leg, long cheap leg, PAIRED ENTRY
         (both fills same timestamp, market-neutral; never naked legs)
HOLD:    6 hours, exit paired at opposite quotes
SIZE:    500 USDT per leg (frozen; smallest venue book must absorb it)
```

**Universe = all 13 common stock-perp symbols, pre-declared** (TSLA, AAPL,
NVDA, MSFT, GOOGL, AMZN, META, SPY, QQQ, COIN, MSTR, HOOD, CRCL).
TSLA/NVDA/AAPL = exploratory strong-effect subset; SPY = declared negative
control (gross ≈ 7 bps < fees ⇒ expected FAIL; if it "wins," suspect
contamination). Selection never collapses the claimed universe.

## 2. Evidence states (the only claims allowed, verbatim)

- Historical mid-price convergence: **STRONG** (cluster t 7–9.5, 3 names,
  placebo −, shuffle ~0, capture 46–68%)
- Historical net-of-carry: **STRONG** (formula §1 with settlement records)
- Historical executable (bid/ask): **UNAVAILABLE — no venue stores it**
- Forward executable: **PENDING — first verdict after Sep 20 weekend tape**

**Forbidden words until forward PASS:** "proved", "risk-free", "optimal",
"alpha realized". This strategy is a *candidate* until real spreads pay.

## 3. Execution accounting (every row, no shortcuts)

```
pair PnL = (entry_rich_bid − exit_rich_bid)/entry + (exit_cheap_ask − entry_cheap_ask)/exit
           − fees 24 bps (4× 0.06% taker)
           − funding actually settled in-window per leg (signed)
           − slippage = 50% recorded spread per fill
           − impact: 10 bps if leg size > 2× displayed top depth at entry
gross → net, itemized; failed pairs (missing venue fill, gate trips) =
FAILURE observations kept in denominators. No rescue, no reruns.
```

## 4. Validation

- Backtest window: venue_index 1h bars, ~42–120 days, ≥60d ✓; OOS =
  walk-forward over weeks (fit EWMA/sigma strictly causal, ≥30d ✓).
- Inference: **day-clustered episode means** (round9 method), naive t
  reported separately. n_rows ≠ n_bets: cooldown = horizon enforced.
- Controls: placebo (random hours, same fade), sign-shuffle, SPY negative
  control, BTC/ETH pair as crypto-baseline sanity.
- Forward executable test (the real one): hourly-grid samples inside
  weekend 5-min tape; PASS = net mean > 0 AND ≥5 weekend pair episodes
  AND SPY control not outperforming the strong subset. Pre-declared in
  strategy/backtest.py; no post-hoc re-cuts.

## 5. Immutables

1. §1 formula frozen for fold 1 (estimator change = new fold, new doc)
2. universe 13, no collapse
3. trigger = "pre-specified", never "optimal"
4. paired entry always
5. costs from recorded quotes + settlement records only; missing = flagged
6. weekend 5-min tape is the executable evidence; hourly history is the
   research evidence; they are never conflated
7. no ML, no PCA, no OI/regime filters, no horizon tuning this fold
8. forward verdict published unedited, pass or fail
9. Weekend Desk = Baseline A, cited as directional predecessor; results of
   one never "explain" the other post-hoc
10. this file immutable after Sun 17:00 UTC Sep 20 root commit

## 6. Relationship to Weekend Desk (Baseline A)

WD: sign(weekend SPY-perp return) → Monday native open. Directional,
after-hours-information object, frozen Sep 14, auto-settling Sep 21.
VEGA: venue-relative value, market-neutral, 24/7. **A PASS for VEGA is
validated only against §3 costs — not by WD's story, and WD's forward
result neither rescues nor cancels VEGA.** The two are independent
evidence streams from the same tape infrastructure.
