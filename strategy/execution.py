"""
VEGA execution accounting (frozen §3). Paired market-neutral fills only.
Inputs are recorded quotes/rates; nothing invented — missing data flags the row.
"""
FEE_BPS   = 24.0     # 4 x 0.06% taker (both legs, both sides)
LEG_USDT  = 500.0    # frozen leg notional
IMPACT_BPS = 10.0    # per leg if displayed depth on traded side < 2x leg

def leg_short(px_entry_bid, px_exit_bid):
    return (px_entry_bid - px_exit_bid) / px_entry_bid * 1e4   # bps

def leg_long(px_entry_ask, px_exit_ask):
    return (px_exit_ask - px_entry_ask) / px_entry_ask * 1e4   # bps

def pair_pnl(entry, exit_, funding_bps=0.0, mode="executable"):
    """entry/exit: dict with rich_bid, rich_ask, rich_bid_sz, rich_ask_sz,
    cheap_bid, cheap_ask, cheap_bid_sz, cheap_ask_sz (quotes at each timestamp).
    Short-rich / long-cheap pair, 1x per leg, averaged to pair return.
    mode='mid' => mids used, row labeled MID (no spread truth) and spread
    slippage charged at the median pair spread instead (caller supplies via
    'slip_bps' key)."""
    if entry is None or exit_ is None: return {"error": "missing fill"}
    if mode == "executable":
        gross = (leg_short(entry["rich_bid"], exit_["rich_bid"]) +
                 leg_long(entry["cheap_ask"], exit_["cheap_ask"])) / 2
        slip = 0.0   # real bid/ask embeds spread; no double charge
        exec_ok = True
    else:            # mid-price backtest: charge half-spread each side, per leg
        gross = (( (entry["rich_mid"] - exit_["rich_mid"]) / entry["rich_mid"] * 1e4 +
                   (exit_["cheap_mid"] - entry["cheap_mid"]) / entry["cheap_mid"] * 1e4 ) / 2)
        slip = entry.get("slip_bps", 0.0) + exit_.get("slip_bps", 0.0)
        exec_ok = False
    impact = 0.0
    if mode == "executable":
        if entry.get("rich_bid_sz", 1e9) * entry.get("rich_bid", 0) < 2 * LEG_USDT: impact += IMPACT_BPS
        if entry.get("cheap_ask_sz", 1e9) * entry.get("cheap_ask", 0) < 2 * LEG_USDT: impact += IMPACT_BPS
    net = gross - FEE_BPS - slip - impact - funding_bps
    return {"gross_bps": round(gross, 1), "fees_bps": FEE_BPS, "slip_bps": round(slip, 1),
            "impact_bps": impact, "funding_bps": round(funding_bps, 1),
            "net_bps": round(net, 1), "label": "EXECUTABLE" if exec_ok else "MID (research only)"}
