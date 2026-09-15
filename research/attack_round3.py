import json, urllib.request, datetime, math, os

OUT = r"D:\wk-probes"
os.makedirs(OUT, exist_ok=True)

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.load(urllib.request.urlopen(req, timeout=25))

# ---------- perp daily bars ----------
PERPS = ["AAPLUSDT","TSLAUSDT","NVDAUSDT","MSFTUSDT","GOOGLUSDT","AMZNUSDT","METAUSDT","SPYUSDT","QQQUSDT"]
def fetch_daily(sym):
    out = {}; end = None
    for _ in range(6):
        u = f"https://api.bitget.com/api/v2/mix/market/history-candles?symbol={sym}&productType=usdt-futures&granularity=1D&limit=200"
        if end: u += f"&endTime={end}"
        d = get(u); rows = d.get('data') or []
        if not rows: break
        for r in rows: out[int(r[0])] = (float(r[1]), float(r[2]), float(r[5]))
        if len(rows) < 200: break
        end = min(int(r[0]) for r in rows) - 1
    return out
P = {s: fetch_daily(s) for s in PERPS}
common = sorted(set.intersection(*[set(v.keys()) for v in P.values()]))

# ---------- underlying (Yahoo) daily OHLC ----------
def yahoo(sym):
    end = int(datetime.datetime(2026,9,14).timestamp())
    u = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={end-90*86400}&period2={end}&interval=1d"
    d = get(u); res = d['chart']['result'][0]
    ts = res['timestamp']; q = res['indicators']['quote'][0]
    m = {}
    for i, t in enumerate(ts):
        m[t] = (q['open'][i], q['close'][i])
    return m  # epoch secs -> (open, close) US-session days
U = {}
for sym in ["SPY","AAPL","TSLA","NVDA","MSFT","GOOGL","AMZN","META","QQQ"]:
    try: U[sym] = yahoo(sym)
    except Exception as e: print("yahoo fail", sym, e)
print("underlying days:", {k: len(v) for k, v in list(U.items())[:2]})

def dow(ts): return datetime.datetime.utcfromtimestamp(ts/1000).weekday()
def d(ts): return datetime.datetime.utcfromtimestamp(ts/1000).date()

def corr(a,b):
    n=len(a); ma=sum(a)/n; mb=sum(b)/n
    sxx=sum((x-ma)**2 for x in a); syy=sum((y-mb)**2 for y in b)
    if sxx==0 or syy==0: return 0,0,n,0
    sxy=sum((x-ma)*(y-mb) for x,y in zip(a,b))
    r=sxy/math.sqrt(sxx*syy); beta=sxy/sxx
    t=r*math.sqrt((n-2)/(1-r*r)) if abs(r)<1 and n>2 else 0
    return r,beta,n,t

# ---------- TEST 1: underlying Monday gap vs perp weekend move (TRUE price discovery) ----------
# perp weekend move: open(Sat bar)=Fri 16Z, to open(Mon bar)=Sun 16Z.
# underlying: Fri close -> Mon open gap (what Monday actually opens at).
print("\n=== T1: perp weekend return vs UNDERLYING Mon open gap ===")
rows_u = {s: [] for s in U}
for ts in common:
    if dow(ts) != 5: continue
    mon_open = ts + 2*86400000  # Sun 16Z = start of Mon bar
    if mon_open not in common: continue
    fri = d(ts - 86400000); mon = d(mon_open)
    # yahoo key: Friday session timestamp (ms->s), Monday open
    for ps, us in [("SPYUSDT","SPY"),("AAPLUSDT","AAPL"),("TSLAUSDT","TSLA"),("NVDAUSDT","NVDA"),("MSFTUSDT","MSFT"),("GOOGLUSDT","GOOGL"),("AMZNUSDT","AMZN"),("METAUSDT","META"),("QQQUSDT","QQQ")]:
        m = U[us]
        # find nearest yahoo bars for fri close and mon open
        fk = [t for t in m if d(t*1000)==fri]; mk = [t for t in m if d(t*1000)==mon]
        if not fk or not mk: continue
        fclose = m[fk[0]][1]; mopen = m[mk[0]][0]
        if not fclose or not mopen: continue
        gap = mopen/fclose - 1
        wkend = P[ps][mon_open][0]/P[ps][ts][0] - 1
        rows_u[us].append((d(ts), wkend, gap))
for us in ["SPY","QQQ","AAPL","TSLA","NVDA","MSFT","GOOGL","AMZN","META"]:
    rr = rows_u[us]
    if len(rr) < 4: print(us, "n<4"); continue
    a=[x[1]*100 for x in rr]; b=[x[2]*100 for x in rr]
    r_,beta_,n_,t_ = corr(a,b)
    agree = sum(1 for x in rr if x[1]*x[2]>0)/n_*100
    print("%-6s n=%2d  r=%+.2f beta=%+.2f t=%+.1f  sign-agree %.0f%%  avgGap=%+.2f%%" % (us,n_,r_,beta_,t_,agree,sum(b)/n_))

# ---------- TEST 2: placebo — same 2-day->1-day structure mid-week ----------
print("\n=== T2: placebo windows (fake weekends, Tue/Wed/Thu anchors) ===")
def window_test(anchor_offsets):
    out = []
    for ts in common:
        offs = anchor_offsets
        if not all(ts+o*86400000 in common for o in [0,2,3]): continue
        for s in ["SPYUSDT","AAPLUSDT","BASKET"]:
            if s=="BASKET":
                if not all(ts+o*86400000 in common for o in offs['need']): continue
                sm = sum(P[x][ts+2*86400000][0]/P[x][ts][0]-1 for x in PERPS[:7])/7
                nx = sum(P[x][ts+3*86400000][0]/P[x][ts+2*86400000][0]-1 for x in PERPS[:7])/7
                out.append((sm,nx))
            else:
                sm = P[s][ts+2*86400000][0]/P[s][ts][0]-1
                nx = P[s][ts+3*86400000][0]/P[s][ts+2*86400000][0]-1
                out.append((sm,nx))
    return out
# real weekend: anchor = Fri-16Z bar (dow 5), next day = Mon session (dow 1 bar covers Mon US)
wk_real = []
for ts in common:
    if dow(ts)!=5: continue
    for s in ["SPYUSDT","AAPLUSDT","BASKET"]:
        tgt=[ts+2*86400000, ts+3*86400000]
        if not all(t in common for t in tgt): continue
        if s=="BASKET":
            sm=sum(P[x][tgt[0]][0]/P[x][ts][0]-1 for x in PERPS[:7])/7
            nx=sum(P[x][tgt[1]][0]/P[x][tgt[0]][0]-1 for x in PERPS[:7])/7
        else:
            sm=P[s][tgt[0]][0]/P[s][ts][0]-1; nx=P[s][tgt[1]][0]/P[s][tgt[0]][0]-1
        wk_real.append((s,sm,nx))
# placebo: anchor Tue-16Z (dow 1) -> 2-day move to Thu, predict Fri session
pl = []
for ts in common:
    if dow(ts)!=1: continue
    for s in ["SPYUSDT","AAPLUSDT","BASKET"]:
        tgt=[ts+2*86400000, ts+3*86400000]
        if not all(t in common for t in tgt): continue
        if s=="BASKET":
            sm=sum(P[x][tgt[0]][0]/P[x][ts][0]-1 for x in PERPS[:7])/7
            nx=sum(P[x][tgt[1]][0]/P[x][tgt[0]][0]-1 for x in PERPS[:7])/7
        else:
            sm=P[s][tgt[0]][0]/P[s][ts][0]-1; nx=P[s][tgt[1]][0]/P[s][tgt[0]][0]-1
        pl.append((s,sm,nx))
for name, grp in (("WEEKEND (Fri2Mon->Mon)", wk_real), ("PLACEBO (Tue2Thu->Thu)", pl)):
    print(name)
    for s in ["SPYUSDT","AAPLUSDT","BASKET"]:
        a=[x[1]*100 for x in grp if x[0]==s]; b=[x[2]*100 for x in grp if x[0]==s]
        if len(a)<4: continue
        r_,beta_,n_,t_=corr(a,b)
        print("  %-9s n=%2d r=%+.2f beta=%+.2f t=%+.1f" % (s,n_,r_,beta_,t_))

# ---------- TEST 3: volatility normalization ----------
print("\n=== T3: vol-normalized (z-score weekend move by own weekend sigma) ===")
for s in ["SPYUSDT","AAPLUSDT","AMZNUSDT","BASKET"]:
    sm=[]; mo=[]
    for ts in common:
        if dow(ts)!=5: continue
        tgt=[ts+2*86400000, ts+3*86400000]
        if not all(t in common for t in tgt): continue
        if s=="BASKET":
            sm.append(sum(P[x][tgt[0]][0]/P[x][ts][0]-1 for x in PERPS[:7])/7)
            mo.append(sum(P[x][tgt[1]][0]/P[x][tgt[0]][0]-1 for x in PERPS[:7])/7)
        else:
            sm.append(P[s][tgt[0]][0]/P[s][ts][0]-1); mo.append(P[s][tgt[1]][0]/P[s][tgt[0]][0]-1)
    n=len(sm); mu=sum(sm)/n; sg=math.sqrt(sum((x-mu)**2 for x in sm)/(n-1))
    z=[(x-mu)/sg for x in sm]
    r_,beta_,n_,t_=corr(z,[x*100 for x in mo])
    print("%-9s sigma_weekend=%.2f%%  z vs Mon: r=%+.2f beta=%+.2f t=%+.1f" % (s, sg*100, r_, beta_, t_))
    # standardized-shock comparison: only |z|>=0.7 weekends, avg Monday continuation per asset
    if s=="BASKET": continue

# ---------- TEST 4: weekend sigma per asset (is AAPL just noisier than SPY?) ----------
print("\n=== T4: weekend move dispersion per asset ===")
for s in PERPS:
    sm=[]
    for ts in common:
        if dow(ts)!=5: continue
        t2=ts+2*86400000
        if t2 in common and ts in P[s]:
            sm.append(P[s][t2][0]/P[s][ts][0]-1)
    if len(sm)>3:
        sg=math.sqrt(sum((x-sum(sm)/len(sm))**2 for x in sm)/(len(sm)-1))
        mx=max(abs(x) for x in sm)
        print("%-9s sigma=%.2f%%  max|move|=%.2f%%  n=%d" % (s, sg*100, mx*100, len(sm)))

# ---------- TEST 5: turnover sanity — mean abs Monday move (size of edges) ----------
print("\n=== T5: mean |Monday session move| (edge vs cost yardstick) ===")
for s in ["SPYUSDT","AAPLUSDT"]:
    mo=[abs(x) for x in [ (P[s][ts][0]/P[s][ts-86400000][0]-1) for ts in common if dow(ts)==2 and ts-86400000 in common]]
    if mo: print(s, "mean |daily| %.2f%%" % (sum(mo)/len(mo)*100))
