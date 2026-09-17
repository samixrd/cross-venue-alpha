"""
WEEKEND DESK RESERVE -> VEGA collector (flagship tape). Completely separate
from the WD tape (wk-probes/collected/): VEGA tape lives in
D:/cross-venue-alpha/tape/ with its own chain.

Frozen research universe: ALL 13 common stock-perp symbols (no selection).
TSLA/NVDA/AAPL = exploratory strong-effect subset. SPY = exploratory
negative control. The collector does not know or care which won.

Sampling (frozen):
  weekday: hourly at HH:00:00 UTC  (historically compatible w/ 1h backtest)
  weekend window (Fri 00:00 -> Mon 21:00 UTC): every 5 minutes
    -> hourly grid always exists inside the finer tape; forward execution
       horizon stays comparable to the backtest horizon (CTO constraint).

Record per symbol per venue (one JSONL line):
  ts_utc, dow, hour, minute, sym, venue,
  bid, ask, bid_sz, ask_sz, last, mid, spread_bps,
  funding_rate, next_funding_ms, oi, index/mark where provided,
  prev_hash, chain
APIs (public, keyless): Bitget /api/v2/mix/market/tickers ;
  Binance /fapi/v1/ticker/bookTicker + /fapi/v1/premiumIndex + /fapi/v1/ticker/price ;
  Bybit /v5/market/tickers?category=linear
"""
import json, urllib.request, datetime, time, os, sys, hashlib

ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, "tape")
STATE  = os.path.join(OUTDIR, "_chain_state.json")
os.makedirs(OUTDIR, exist_ok=True)

SYMBOLS = ["TSLAUSDT","AAPLUSDT","NVDAUSDT","MSFTUSDT","GOOGLUSDT","AMZNUSDT",
           "METAUSDT","SPYUSDT","QQQUSDT","COINUSDT","MSTRUSDT","HOODUSDT","CRCLUSDT"]

def get(u):
    req=urllib.request.Request(u, headers={"User-Agent":"Mozilla/5.0"})
    return json.load(urllib.request.urlopen(req, timeout=25))

def sha(s): return hashlib.sha256(s.encode()).hexdigest()

def load_prev():
    if os.path.exists(STATE):
        return json.load(open(STATE)).get("prev", "GENESIS")
    return "GENESIS"

def save_prev(p):
    json.dump({"prev":p,"updated":datetime.datetime.now(datetime.timezone.utc).isoformat()}, open(STATE,"w"))

# ---------- venue fetchers: sym -> record fields ----------
def fetch_bitget():
    d=get("https://api.bitget.com/api/v2/mix/market/tickers?productType=usdt-futures")
    out={}
    for t in d.get('data') or []:
        s=t['symbol']
        if s not in SYMBOLS: continue
        f=lambda k: float(t[k]) if t.get(k) not in (None,"") else None
        out[s]=dict(bid=f('bidPr'),ask=f('askPr'),bid_sz=f('bidSz'),ask_sz=f('askSz'),
                    last=f('lastPr'),oi=f('holdingAmount'),funding_rate=f('fundingRate'),
                    index=f('indexPrice'),mark=f('markPrice'),venue="bitget")
    return out

def fetch_binance():
    bt=get("https://fapi.binance.com/fapi/v1/ticker/bookTicker")
    px={r['symbol']:float(r['price']) for r in get("https://fapi.binance.com/fapi/v1/ticker/price")}
    pi={r['symbol']:r for r in get("https://fapi.binance.com/fapi/v1/premiumIndex")}
    out={}
    for t in bt:
        s=t['symbol']
        if s not in SYMBOLS: continue
        p=pi.get(s,{})
        out[s]=dict(bid=float(t['bidPrice']),ask=float(t['askPrice']),bid_sz=float(t['bidQty']),
                    ask_sz=float(t['askQty']),last=px.get(s),oi=None,
                    funding_rate=float(p.get('lastFundingRate',0) or 0),
                    next_funding_ms=int(p.get('nextFundingTime',0) or 0),
                    index=float(p.get('markPrice',0) or 0),mark=float(p.get('markPrice',0) or 0),
                    venue="binance")
    return out

def fetch_bybit():
    d=get("https://api.bybit.com/v5/market/tickers?category=linear")
    out={}
    for t in d.get("result",{}).get("list",[]):
        s=t.get('symbol')
        if s not in SYMBOLS: continue
        f=lambda k: float(t[k]) if t.get(k) not in (None,"") else None
        out[s]=dict(bid=f('bid1Price'),ask=f('ask1Price'),bid_sz=f('bid1Size'),ask_sz=f('ask1Size'),
                    last=f('lastPrice'),oi=f('openInterestValue'),funding_rate=f('fundingRate'),
                    next_funding_ms=f('nextFundingTime'),index=None,mark=f('markPrice'),venue="bybit")
    return out

FETCH={"bitget":fetch_bitget,"binance":fetch_binance,"bybit":fetch_bybit}

def sample_once(verbose=False):
    now=datetime.datetime.now(datetime.timezone.utc)
    prev=load_prev(); rec_prev=prev
    n=0
    fpath=os.path.join(OUTDIR, now.strftime("%Y-%m-%d")+".jsonl")
    with open(fpath,"a",encoding="utf-8") as f:
        for venue in ["bitget","binance","bybit"]:
            try: recs=FETCH[venue]()
            except Exception as e:
                if verbose: print("venue fail",venue,e); continue
            for s,r in recs.items():
                r["ts_utc"]=now.isoformat(timespec="seconds"); r["dow"]=now.weekday()
                r["hour"]=now.hour; r["minute"]=now.minute; r["sym"]=s
                if r.get("bid") and r.get("ask") and r["bid"]>0:
                    r["mid"]=(r["bid"]+r["ask"])/2
                    r["spread_bps"]=(r["ask"]-r["bid"])/r["mid"]*1e4
                canon=json.dumps({k:r[k] for k in sorted(r) if k not in ("prev_hash","chain")},sort_keys=True,separators=(",",":"))
                prev=sha(prev+canon)
                r["prev_hash"]=rec_prev; r["chain"]=prev; rec_prev=prev
                f.write(json.dumps(r)+"\n"); n+=1
    save_prev(prev)
    if verbose: print("v2 sampled",n,"records; chain tip",prev[:16])
    return n

def in_weekend(dt):
    wd=dt.weekday(); h=dt.hour
    if wd==4: return h>=0
    if wd in (5,6): return True
    if wd==0: return h<=21
    return False

def run_daemon(duration_minutes=None):
    print("v2 three-venue collector up", f"(duration: {duration_minutes}m)" if duration_minutes else "(infinite)", flush=True)
    start_time = time.time()
    while True:
        try: sample_once()
        except Exception as e: print("cycle fail", e, flush=True)
        now = datetime.datetime.now(datetime.timezone.utc)
        sleep_sec = 300 if in_weekend(now) else 3600
        if duration_minutes:
            elapsed = time.time() - start_time
            if elapsed + sleep_sec >= duration_minutes * 60:
                rem = max(0, duration_minutes * 60 - elapsed)
                if rem > 10: time.sleep(rem)
                print("duration limit reached, exiting cleanly", flush=True)
                break
        time.sleep(sleep_sec)

if __name__ == "__main__":
    if "--now" in sys.argv:
        sample_once(verbose=True)
    elif "--duration" in sys.argv:
        idx = sys.argv.index("--duration")
        mins = float(sys.argv[idx + 1]) if len(sys.argv) > idx + 1 else 30
        run_daemon(duration_minutes=mins)
    else:
        run_daemon()

