import json, urllib.request, datetime, math, os

OUT = r"D:\wk-probes"
os.makedirs(OUT, exist_ok=True)
SYMS = ["AAPLUSDT","TSLAUSDT","NVDAUSDT","MSUSDT","MSFTUSDT","GOOGLUSDT","AMZNUSDT","METAUSDT","SPYUSDT","QQQUSDT","COINUSDT","MSTRUSDT","HOODUSDT","CRCLUSDT","BTCUSDT","ETHUSDT","SOLUSDT"]
SYMS = [s for s in SYMS if s != "MSUSDT"]

def fetch_daily(sym):
    out = {}
    end = None
    for _ in range(6):
        u = f"https://api.bitget.com/api/v2/mix/market/history-candles?symbol={sym}&productType=usdt-futures&granularity=1D&limit=200"
        if end: u += f"&endTime={end}"
        try:
            d = json.load(urllib.request.urlopen(u, timeout=20))
        except Exception as e:
            print(sym, "fetch err", e); break
        rows = d.get('data') or []
        if not rows: break
        for r in rows:
            out[int(r[0])] = (float(r[1]), float(r[2]), float(r[5]))
        oldest = min(int(r[0]) for r in rows)
        if len(rows) < 200: break
        end = oldest - 1
    return out

data = {s: fetch_daily(s) for s in SYMS}
common = sorted(set.intersection(*[set(v.keys()) for v in data.values()]))
print("common days:", len(common),
      datetime.datetime.utcfromtimestamp(common[0]/1000).date(), "->",
      datetime.datetime.utcfromtimestamp(common[-1]/1000).date())

def dow(ts): return datetime.datetime.utcfromtimestamp(ts/1000).weekday()

# Bar convention: 1D bar opens 16:00 UTC. Sat bar opens Fri 16:00 UTC (=US close Fri).
# Sun bar opens Sat 16:00 (covers Sat US afternoon+overnight), Mon bar opens Sun 16:00
# -> Sun-16UTC..Mon-16UTC = the full Monday US session. So:
# weekend move = open(next bar after Sun) / open(Sat bar) anchored at Friday close print
results = {s: [] for s in SYMS}
for ts in common:
    if dow(ts) != 5: continue
    sat, sun, mon, tue = ts, ts+86400000, ts+2*86400000, ts+3*86400000
    if not all(t in common for t in (sat,sun,mon,tue)): continue
    for s in SYMS:
        d = data[s]
        anchor = d[sat][0]                 # Friday US close print
        c_sun  = d[mon][0]                 # Sun 16:00 UTC = pre-open Monday
        c_mon  = d[tue][0]                 # Mon 16:00 = Monday US close
        if anchor <= 0: continue
        sunmove = c_sun/anchor - 1          # the whole weekend's cumulative move
        monret  = c_mon/c_sun - 1           # Monday US session return (tradeable from Sunday close)
        results[s].append((datetime.datetime.utcfromtimestamp(sat/1000).date(), sunmove, monret))

json.dump({s: [[str(r[0]), r[1], r[2]] for r in v] for s, v in results.items()},
          open(os.path.join(OUT, "weekend_pairs.json"), "w"))

def corr(a, b):
    n = len(a)
    if n < 3: return 0, 0, n
    ma = sum(a)/n; mb = sum(b)/n
    sxx = sum((x-ma)**2 for x in a)
    if sxx == 0: return 0, 0, n
    sxy = sum((x-ma)*(y-mb) for x, y in zip(a, b))
    syy = sum((y-mb)**2 for y in b)
    r = sxy/math.sqrt(sxx*syy) if syy else 0
    beta = sxy/sxx
    # t-stat
    if n > 2 and abs(r) < 1:
        t = r*math.sqrt((n-2)/(1-r*r))
    else:
        t = 0
    return r, beta, n, t

print("\n=== Does weekend move predict Monday session? (OOS-in-sample probe) ===")
print("sym          n   corr    beta   t-stat   meanMon%   hit% (sign agrees)")
BASK = ["AAPLUSDT","TSLAUSDT","NVDAUSDT","MSFTUSDT","GOOGLUSDT","AMZNUSDT","METAUSDT"]
for s in SYMS + ["BASKET"]:
    if s == "BASKET":
        rows = results["AAPLUSDT"]
        pairs = []
        for i in range(len(rows)):
            sm = sum(results[x][i][1] for x in BASK)/len(BASK)
            mr = sum(results[x][i][2] for x in BASK)/len(BASK)
            pairs.append((sm, mr))
    else:
        pairs = [(r[1], r[2]) for r in results[s]]
    if len(pairs) < 4: print(s, "too few"); continue
    a = [p[0]*100 for p in pairs]; b = [p[1]*100 for p in pairs]
    r_, beta_, n_, t_ = corr(a, b)
    hit = sum(1 for p in pairs if p[0]*p[1] > 0)/n_*100
    meanmon = sum(b)/n_
    print("%-12s %3d  %+.2f  %+.2f   %+.2f    %+.2f      %.0f" % (s, n_, r_, beta_, t_, meanmon, hit))

print("\n=== Crypto beta: BTC weekend move vs asset weekend move (same window) ===")
btc = results["BTCUSDT"]
n_b = len(btc)
for s in ["ETHUSDT","SOLUSDT","AAPLUSDT","TSLAUSDT","NVDAUSDT","SPYUSDT","QQQUSDT","MSTRUSDT","COINUSDT","HOODUSDT","CRCLUSDT","BASKET7"]:
    if s == "BASKET7":
        a = [sum(results[x][i][1] for x in BASK)/len(BASK)*100 for i in range(n_b)]
    else:
        rows = results[s]; a = [r[1]*100 for r in rows][:n_b]
    bb = [r[1]*100 for r in btc][:len(a)]
    r_, beta_, n_, t_ = corr(bb, a)
    print("%-10s r=%+.2f beta=%+.2f t=%+.1f n=%d" % (s, r_, beta_, t_, n_))

print("\n=== Partial-out: stock weekend move AFTER removing crypto-beta component ===")
# residual = sunmove - beta*BTC_sunmove, then test residual vs Monday session
for s in BASK + ["SPYUSDT","QQQUSDT"]:
    rows = results[s]
    bb = [r[1] for r in btc][:len(rows)]
    sm = [r[1] for r in rows]; mo = [r[2] for r in rows]
    r0, beta0, *_ = corr(bb, sm)
    resid = [x - beta0*y for x, y in zip(sm, bb)]
    r1, beta1, n1, t1 = corr([x*100 for x in resid], [x*100 for x in mo])
    print("%-10s raw r=%+.2f -> crypto-purged r=%+.2f beta=%+.2f t=%+.1f" % (s, r0, r1, beta1, t1))

print("\n=== Weekend magnitude vs Monday continuation ===")
rows = results["AAPLUSDT"]
big = [(r[1], r[2]) for r in rows if abs(r[1]) >= 0.005]
sml = [(r[1], r[2]) for r in rows if abs(r[1]) < 0.005]
for name, grp in (("big |move|>=0.5%", big), ("small", sml)):
    if len(grp) >= 3:
        agree = sum(1 for x, y in grp if x*y > 0)/len(grp)*100
        meanif = sum(y for x, y in grp if x > 0)/max(1, sum(1 for x, y in grp if x > 0))
        print("%-18s n=%2d sign-agree %.0f%%  avg Mon ret after up-weekend: %+.2f%%" % (name, len(grp), agree, meanif))
