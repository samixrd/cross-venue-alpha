"""ROUND 7e — DECISIVE: does cross-venue basis predict its own reversion, NET of 4-side costs?
D_t = ln(P_Bitget/P_Binance). Trade: |D| abnormal -> short rich leg / long cheap leg.
Cost floor: taker fee 0.06% x 4 sides = 24 bps + spreads, hold 1h..6h.
Also Bybit pair. Weekend subsample = the thin regime where D is biggest."""
import json, urllib.request, datetime, math

def get(u):
    return json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent":"Mozilla/5.0"}), timeout=25))

def binance_1h(sym, days=120):
    end=int(datetime.datetime(2026,9,15).timestamp()*1000); start=end-days*86400000
    out={}; cur=start
    while cur<end:
        rows=get(f"https://fapi.binance.com/fapi/v1/klines?symbol={sym}&interval=1h&startTime={cur}&limit=1500")
        if not isinstance(rows,list) or not rows: break
        for r in rows: out[r[0]]=float(r[4])
        cur=rows[-1][0]+3600000
        if len(rows)<1500: break
    return out

def bitget_1h(sym, days=120):
    out={}; end=None
    stop=int((datetime.datetime(2026,9,15)-datetime.timedelta(days=days)).timestamp()*1000)
    for _ in range(60):
        u=f"https://api.bitget.com/api/v2/mix/market/history-candles?symbol={sym}&productType=usdt-futures&granularity=1H&limit=200"
        if end: u+=f"&endTime={end}"
        rows=get(u).get('data') or []
        if not rows: break
        for r in rows: out[int(r[0])]=float(r[2])
        oldest=min(int(r[0]) for r in rows)
        if oldest<stop or len(rows)<200: break
        end=oldest-1
    return out

def bybit_1h(sym, days=40):
    end=int(datetime.datetime(2026,9,15).timestamp()*1000)
    out={}; cur=end
    while True:
        rows=get(f"https://api.bybit.com/v5/market/kline?category=linear&symbol={sym}&interval=60&end={cur}&limit=1000").get("result",{}).get("list",[])
        if not rows: break
        for r in rows: out[int(r[0])]=float(r[4])
        oldest=min(int(r[0]) for r in rows)
        if oldest < end-days*86400000: break
        cur=oldest-1
    return out

H=3600000
def isw(k):
    t=datetime.datetime(1970,1,1)+datetime.timedelta(milliseconds=k)
    return t.weekday()>=5 or (t.weekday()==4 and t.hour>=21) or (t.weekday()==0 and t.hour<4)

for sym in ["SPYUSDT","AAPLUSDT","TSLAUSDT"]:
    A=bitget_1h(sym); B=binance_1h(sym); C=bybit_1h(sym)
    for tag, X, Y in [("BG<->BN",A,B), ("BG<->BY",A,C)]:
        ks=sorted(set(X)&set(Y)&set(k+H for k in set(X)&set(Y)))
        D={k: math.log(X[k]/Y[k]) for k in ks}
        # rolling mu/sigma over 24h
        sk=sorted(D); vals=[D[k] for k in sk]
        rows=[]
        for i,k in enumerate(sk):
            lo=max(0,i-24)
            win=vals[lo:i]
            if len(win)<12: continue
            mu=sum(win)/len(win); sg=math.sqrt(sum((x-mu)**2 for x in win)/len(win)) or 1e-9
            z=(D[k]-mu)/sg
            for h in (1,3,6):
                k2=k+h*H
                if k2 in D:
                    # reversion PnL (bps) for SHORT rich leg if z>0 / LONG if z<0:
                    pnl = -z/abs(z) * (D[k2]-D[k]) * 1e4   # log basis change, signed against z
                    rows.append((k,z,pnl,h,isw(k)))
        for h in (1,3,6):
            allr=[r for r in rows if r[3]==h]
            big=[r for r in allr if abs(r[1])>=2.0]
            bigw=[r for r in big if r[4]]
            if not allr: continue
            avg=lambda g: sum(x[2] for x in g)/len(g) if g else 0
            print("%-9s %s h=%dh | all: mean %+.1fbps n=%d | |z|>2: %+.1fbps n=%d | weekend & |z|>2: %+.1fbps n=%d" %
                  (sym,tag,h,avg(allr),len(allr),avg(big),len(big),avg(bigw),len(bigw)))
    print()
