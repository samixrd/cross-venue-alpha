"""ROUND 7d — Oracle test: which venue's WEEKEND move predicts native Monday gap?
Bitget vs Binance (the leader). Same weekend anchor window (Fri21->Sun16 UTC).
Also: does Bitget lag Binance even at weekends? (h-1 asymmetry holds?)"""
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

def yahoo(sym):
    end=int(datetime.datetime(2026,9,15).timestamp())
    r=get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={end-110*86400}&period2={end}&interval=1d")['chart']['result'][0]
    q=r['indicators']['quote'][0]
    return {datetime.datetime.utcfromtimestamp(t).date():(o,c) for t,o,c in zip(r['timestamp'],q['open'],q['close']) if t and o and c}

d=json.load(open(r"D:\wk-probes\weekend_pairs.json"))  # sat-date, w, monret (perp)
PAIRS=[("SPYUSDT","SPY"),("AAPLUSDT","AAPL")]
BN={s:binance_1h(s) for s,_ in PAIRS}
U={u:yahoo(u) for _,u in PAIRS}

def wk_return(bars, satstr):
    sat=datetime.date.fromisoformat(satstr)
    sat_dt=datetime.datetime(sat.year,sat.month,sat.day,tzinfo=datetime.timezone.utc)
    fri21=int((sat_dt-datetime.timedelta(days=1, hours=3)).timestamp()*1000)   # Friday 21:00 UTC
    sun16=int((sat_dt-datetime.timedelta(days=2)).replace(hour=0).timestamp()*1000)+0  # placeholder fix below
    sun16=int((sat_dt+datetime.timedelta(hours=16)).timestamp()*1000) if sat.weekday()==5 else int((sat_dt-datetime.timedelta(hours=8)).timestamp()*1000)
    ks=[k for k in bars if abs(k-fri21)<=3600000]; k2=[k for k in bars if abs(k-sun16)<=3600000]
    if not ks or not k2: return None
    return bars[max(k2,key=lambda k:k<fri21+10**18 and k<=sun16)] if False else bars[min(k2,key=lambda k:abs(k-sun16))]/bars[min(ks,key=lambda k:abs(k-fri21))]-1

def corr(a,b):
    n=len(a)
    if n<5: return 0,0,0
    ma=sum(a)/n; mb=sum(b)/n
    sxx=sum((x-ma)**2 for x in a); syy=sum((y-mb)**2 for y in b); sxy=sum((x-ma)*(y-mb) for x,y in zip(a,b))
    if not sxx or not syy: return 0,0,0
    r=sxy/math.sqrt(sxx*syy); t=r*math.sqrt((n-2)/(1-r*r)) if abs(r)<1 else 0
    return r,sxy/sxx,t

for psym, usym in PAIRS:
    wbg=[]; wbn=[]; gap=[]
    for r in d[psym]:
        satstr=r[0]; w=r[1]
        b=wk_return(BN[psym], satstr)
        if b is None: continue
        sat=datetime.date.fromisoformat(satstr); fri=sat-datetime.timedelta(days=1); mon=sat+datetime.timedelta(days=2)
        if fri in U[usym] and mon in U[usym]:
            wbg.append(w); wbn.append(b); gap.append(U[usym][mon][0]/U[usym][fri][1]-1)
    r1,b1,t1=corr([x*100 for x in wbg],[x*100 for x in gap])
    r2,b2,t2=corr([x*100 for x in wbn],[x*100 for x in gap])
    r3,_,t3=corr([x*100 for x in wbg],[x*100 for x in wbn])
    print("%s: n=%d | Bitget w->gap r=%+.2f t=%+.1f beta=%+.2f | Binance w->gap r=%+.2f t=%+.1f beta=%+.2f | BG<->BN w r=%+.2f" % (usym,len(gap),r1,t1,b1,r2,t2,b2,r3))
