"""sanity: frozen signal+execution reproduce the round-8/9 mid numbers on venue_index."""
import json, sys, math, datetime
sys.path.insert(0, r"D:\cross-venue-alpha")
sys.path.insert(0, r"D:\cross-venue-alpha\strategy")
from strategy.signal import episodes_for
from strategy.execution import pair_pnl
IDX=json.load(open(r"D:\cross-venue-alpha\data\venue_index.json"))
# signal.episodes_for expects bars keyed by hour ms; venue_index bars keyed by bar-open ms (already hourly)
for sym in ["TSLAUSDT","NVDAUSDT","AAPLUSDT","SPYUSDT"]:
    eps,st=episodes_for(IDX[sym])
    rows=[]
    for e in eps:
        # reconstruct quotes: mid-only history -> mid mode, slip = fee floor proxy
        v1=IDX[sym]["bitget"]["bars"];v2=IDX[sym]["binance"]["bars"];v3=IDX[sym]["bybit"]["bars"]
        M={"bitget":float(v1[str(e["t_ms"])]),"binance":float(v2[str(e["t_ms"])]),"bybit":float(v3[str(e["t_ms"])])}
        t2=e["t_ms"]+6*3600000
        try:
            X={v:float({"bitget":v1,"binance":v2,"bybit":v3}[v][str(t2)]) for v in ["bitget","binance","bybit"]}
        except Exception: continue
        entry={"rich_mid":M[e["rich"]],"cheap_mid":M[e["cheap"]],"slip_bps":12.0}
        exit_={"rich_mid":X[e["rich"]],"cheap_mid":X[e["cheap"]],"slip_bps":12.0}
        r=pair_pnl(entry,exit_,mode="mid")
        rows.append(r["net_bps"])
    if rows:
        m=sum(rows)/len(rows)
        print("%-9s episodes=%3d net(mid,fee+slip floors) %+.1f bps" % (sym,len(rows),m))
