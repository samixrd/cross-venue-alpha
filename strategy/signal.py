"""
VEGA signal (frozen §1) — importable, deterministic, causal-only sigma.
run(venue_index-like dict, symbols) -> episodes list.
"""
import math, datetime, bisect
H = 3600000
VEN = ["bitget", "binance", "bybit"]
LAM = 0.97; Z_TRIGGER = 2.0; HOLD_H = 6; WARMUP = 24

def hours(sym_data):
    sets = [set(map(int, sym_data[v]["bars"])) for v in VEN]
    return sorted(set.intersection(*sets))

def carry_forward(ts_data, t0, nH):
    """signed actual settlement rates in (t0, t0+nH] (rates are per-period)."""
    f = {int(k): v for k, v in ts_data.items()}
    ks = sorted(f); out = 0.0
    t1 = t0 + nH * H
    i = bisect.bisect_right(ks, t0); j = bisect.bisect_right(ks, t1)
    for k in ks[i:j]: out += f[k]
    return out, (j - i)

def episodes_for(sym_data):
    ks = hours(sym_data)
    if len(ks) < WARMUP + HOLD_H + 2: return [], {}
    rows = []
    for k in ks:
        if k % H: continue
        try: mids = {v: math.log(float(sym_data[v]["bars"][str(k)])) for v in VEN}
        except Exception: continue
        F = sum(mids.values()) / 3
        D = {v: mids[v] - F for v in VEN}
        # carry per venue = funding it pays vs venue-mean carry (signed conventions)
        cm = {v: carry_forward(sym_data[v]["fund"], k, HOLD_H)[0] for v in VEN}
        cbar = sum(cm.values()) / 3
        Dn = {v: D[v] - (cm[v] - cbar) for v in VEN}   # net-of-carry, venue-relative
        rows.append((k, D, Dn))
    sd = {v: 0.0 for v in VEN}; prev = {v: None for v in VEN}
    Z = []
    for k, D, Dn in rows:
        zs = {}
        for v in VEN:
            if prev[v] is not None:
                dd = Dn[v] - prev[v]
                sd[v] = LAM * sd[v] + (1 - LAM) * dd * dd
            zs[v] = Dn[v] / math.sqrt(sd[v]) if sd[v] > 0 else 0.0
            prev[v] = Dn[v]
        Z.append(zs)
    eps = []; last = -10**18; stats = {"n_hours": len(ks)}
    for i, zs in enumerate(Z):
        if i < WARMUP: continue
        rich = max(VEN, key=lambda v: zs[v]); cheap = min(VEN, key=lambda v: zs[v])
        if abs(zs[rich]) < Z_TRIGGER and abs(zs[cheap]) < Z_TRIGGER: continue
        if rows[i][0] - last < HOLD_H * H: continue
        last = rows[i][0]
        # direction: fade = short rich, long cheap
        eps.append({"t_ms": rows[i][0], "rich": rich, "cheap": cheap,
                    "z_rich": zs[rich], "z_cheap": zs[cheap],
                    "D_rich": rows[i][1][rich], "D_cheap": rows[i][1][cheap]})
    return eps, stats

def log_to_ms(t): return int(datetime.datetime(1970,1,1)+datetime.timedelta(milliseconds=t)).timestamp()*1000
