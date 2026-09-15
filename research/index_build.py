"""
VENUE INDEX — one public-data store, all formulas read from it.
Downloads 1h closes + 8h funding history for Bitget/Binance/Bybit on the
shared stock-perp universe. JSON store, stdlib-only, incremental update.
"""
import json, urllib.request, datetime, os, math, sys

STORE = r"D:\wk-probes\venue_index.json"
SYMS = ["TSLAUSDT","AAPLUSDT","NVDAUSDT","MSFTUSDT","GOOGLUSDT","AMZNUSDT","METAUSDT","SPYUSDT","QQQUSDT","COINUSDT","MSTRUSDT","HOODUSDT","CRCLUSDT"]
VENUES = ["bitget","binance","bybit"]
DAYS_BARS = 105     # bitget history-candles: 200 bars/page, enough for ~100d; keep index lean
DAYS_FUND = 105     # funding history pageSize 200 = ~66 days per venue

def get(u):
    return json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent":"Mozilla/5.0"}), timeout=25))

def bars_bitget(s):
    out={}; end=None
    stop=(datetime.datetime.now()-datetime.timedelta(days=DAYS_BARS)).timestamp()*1000
    for _ in range(30):
        u=f"https://api.bitget.com/api/v2/mix/market/history-candles?symbol={s}&productType=usdt-futures&granularity=1H&limit=200"
        if end: u+=f"&endTime={end}"
        rows=get(u).get('data') or []
        if not rows: break
        for r in rows: out[int(r[0])]=float(r[2])
        o=min(int(r[0]) for r in rows)
        if o<stop or len(rows)<200: break
        end=o-1
    return out

def bars_binance(s):
    out={}; end=int(datetime.datetime.now().timestamp()*1000)
    stop=end-DAYS_BARS*86400000
    cur=stop
    while cur<end:
        rows=get(f"https://fapi.binance.com/fapi/v1/klines?symbol={s}&interval=1h&startTime={cur}&limit=1500")
        if not isinstance(rows,list) or not rows: break
        for r in rows: out[r[0]]=float(r[4])
        cur=rows[-1][0]+3600000
        if len(rows)<1500: break
    return out

def bars_bybit(s):
    out={}; cur=int(datetime.datetime.now().timestamp()*1000)
    stop=cur-DAYS_BARS*86400000
    while True:
        rows=get(f"https://api.bybit.com/v5/market/kline?category=linear&symbol={s}&interval=60&end={cur}&limit=1000").get("result",{}).get("list",[])
        if not rows: break
        for r in rows: out[int(r[0])]=float(r[4])
        o=min(int(r[0]) for r in rows)
        if o<stop: break
        cur=o-1
    return out

def fund_bitget(s):
    out={}
    try:
        rows=get(f"https://api.bitget.com/api/v2/mix/market/history-fund-rate?symbol={s}&productType=usdt-futures&pageSize=200").get('data') or []
        for r in rows: out[int(r['fundingTime'])]=float(r['fundingRate'])
    except Exception: pass
    return out

def fund_binance(s):
    out={}
    try:
        end=int(datetime.datetime.now().timestamp()*1000)
        rows=get(f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={s}&endTime={end}&limit=1000")
        for r in rows: out[int(r['fundingTime'])]=float(r['fundingRate'])
        if rows:
            rows=get(f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={s}&endTime={rows[0]['fundingTime']-1}&limit=1000")
            for r in rows: out[int(r['fundingTime'])]=float(r['fundingRate'])
    except Exception: pass
    return out

def fund_bybit(s):
    out={}
    try:
        end=int(datetime.datetime.now().timestamp()*1000)
        rows=get(f"https://api.bybit.com/v5/market/funding/history?category=linear&symbol={s}&end={end}&limit=1000").get("result",{}).get("list",[])
        for r in rows: out[int(r['fundingTimestamp'])]=float(r['fundingRate'])
    except Exception: pass
    return out

BARS={"bitget":bars_bitget,"binance":bars_binance,"bybit":bars_bybit}
FUND={"bitget":fund_bitget,"binance":fund_binance,"bybit":fund_bybit}

def build():
    idx = json.load(open(STORE)) if os.path.exists(STORE) else {}
    for s in SYMS:
        idx.setdefault(s, {})
        for v in VENUES:
            b=BARS[v](s); f=FUND[v](s)
            idx[s][v]={"bars":{str(k):x for k,x in b.items()},"fund":{str(k):x for k,x in f.items()}}
            print("%-9s %-8s bars=%5d fund=%4d" % (s,v,len(b),len(f)), flush=True)
    json.dump(idx, open(STORE,"w"))
    print("saved", STORE, "%.1f MB" % (os.path.getsize(STORE)/1e6))

if __name__=="__main__":
    build()
