"""ROUND 7c — THE primitive: cross-venue lead-lag on the same underlying.
Bitget vs Binance vs Bybit, 1h bars, aligned hourly.
Test 1: corr(dA_t, dB_{t+h}) for h=-6..+6, all hours vs weekend-only.
Test 2: which venue's weekend move best predicts NATIVE Monday gap (oracle).
"""
import json, urllib.request, datetime, math

def get(u):
    return json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent":"Mozilla/5.0"}), timeout=25))

def bitget_1h(sym, days=100):
    out={}; end=None
    start_ms = int(datetime.datetime(2026,9,15).timestamp()*1000) - days*86400000
    for _ in range(20):
        u=f"https://api.bitget.com/api/v2/mix/market/history-candles?symbol={sym}&productType=usdt-futures&granularity=1H&limit=200"
        if end: u+=f"&endTime={end}"
        rows=get(u).get('data') or []
        if not rows: break
        for r in rows: out[int(r[0])//3600000*3600000]=float(r[2])  # close keyed by hour-open ms
        oldest=min(int(r[0]) for r in rows)
        if oldest < start_ms or len(rows)<200: break
        end=oldest-1
    return out

def binance_1h(sym, days=100):
    end=int(datetime.datetime(2026,9,15).timestamp()*1000); start=end-days*86400000
    out={}; cur=start
    while cur<end:
        rows=get(f"https://fapi.binance.com/fapi/v1/klines?symbol={sym}&interval=1h&startTime={cur}&limit=1500")
        if not isinstance(rows,list) or not rows: break
        for r in rows: out[r[0]//3600000*3600000]=float(r[4])
        cur=rows[-1][0]+3600000
        if len(rows)<1500: break
    return out

def bybit_1h(sym, days=40):
    end=int(datetime.datetime(2026,9,15).timestamp()*1000)
    out={}; cur=end
    while True:
        rows=get(f"https://api.bybit.com/v5/market/kline?category=linear&symbol={sym}&interval=60&end={cur}&limit=1000").get("result",{}).get("list",[])
        if not rows: break
        for r in rows: out[int(r[0])//3600000*3600000]=float(r[4])
        oldest=min(int(r[0]) for r in rows)
        if oldest < end-days*86400000: break
        cur=oldest-1
    return out

def hourly_corr(A, B, hmax=6, weekend_only=False):
    """A leads B by h>0 if corr(dA_t, dB_{t+h})"""
    ks = sorted(set(A)&set(B))
    def isw(k):
        t=datetime.datetime(1970,1,1)+datetime.timedelta(milliseconds=k)
        return t.weekday()>=5 or (t.weekday()==4 and t.hour>=21) or (t.weekday()==0 and t.hour<4)
    ks=[k for k in ks if k+3600000*1 in set(A)&set(B)]
    dA={k: A[k+3600000]/A[k]-1 for k in ks if k+3600000 in A and k in A and A[k]>0}
    dB={k: B[k+3600000]/B[k]-1 for k in ks if k+3600000 in B and B[k]>0}
    def corr(a,b):
        n=len(a)
        if n<10: return 0,n
        ma=sum(a)/n; mb=sum(b)/n
        sxx=sum((x-ma)**2 for x in a); syy=sum((y-mb)**2 for y in b); sxy=sum((x-ma)*(y-mb) for x,y in zip(a,b))
        return (sxy/math.sqrt(sxx*syy) if sxx and syy else 0), n
    res={}
    for h in range(-hmax, hmax+1):
        a=[]; b=[]
        for k,v in dA.items():
            k2=k+h*3600000
            if k2 in dB and (not weekend_only or isw(k)):
                a.append(v); b.append(dB[k2])
        r,n=corr(a,b); res[h]=(r,n)
    return res

for sym in ["SPYUSDT","AAPLUSDT"]:
    print("==========", sym, "==========")
    BG=bitget_1h(sym); BN=binance_1h(sym); BY=bybit_1h(sym)
    for pair, X, Y in [("Bitget vs Binance", BG, BN), ("Bitget vs Bybit", BG, BY)]:
        allr = hourly_corr(X, Y)
        wkr  = hourly_corr(X, Y, weekend_only=True)
        print("ALL  %-18s" % pair, " ".join("h%+d:%+.2f"% (h,allr[h][0]) for h in sorted(allr)))
        print("     %-18s n=%d" % ("", allr[0][1]))
        print("WEEK %-18s" % pair, " ".join("h%+d:%+.2f"% (h,wkr[h][0]) for h in sorted(wkr)), "n=%d"%wkr[0][1])
