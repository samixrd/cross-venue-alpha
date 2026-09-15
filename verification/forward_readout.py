"""
VEGA FORWARD READOUT — the pre-declared PASS/FAIL on executable quotes.
Tape: D:\cross-venue-alpha\tape\*.jsonl (3 venues x 13 symbols, 5-min
weekends / hourly weekdays, hash-chained).

Per hour where all 3 venues have quotes for a symbol:
  z from strategy.signal pipeline; trigger |z|>=2 on either extreme venue.
  PAIRED ENTRY at that sample: short rich at ITS BID, long cheap at ITS ASK.
  Exit at first tape sample >=6h later with both fills present (paired).
  Funding: recorded venue rates crossed in-window, accrue differential
  (rich pays / cheap receives, signed) in bps; missing => flag.
  Impact: per §3 depth rule (500 USDT legs).
Verdict (pre-declared, PROTOCOL §4):
  PASS = weekend-regime net mean > 0 AND >= 5 paired episodes AND SPY
         control does not outperform the strong subset.
  FAIL = everything else. VEGA stays a candidate; no re-cuts.
"""
import json, glob, os, math, datetime, sys
from collections import defaultdict
sys.path.insert(0, r"D:\cross-venue-alpha")
from strategy.signal import VEN, Z_TRIGGER, HOLD_H, LAM, WARMUP
from strategy.execution import pair_pnl

TAPE = r"D:\cross-venue-alpha\tape"
OUT  = r"D:\cross-venue-alpha\verification"
os.makedirs(OUT, exist_ok=True)

def load():
    by = defaultdict(dict)   # sym -> venue -> {ts_ms: rec}
    for f in sorted(glob.glob(os.path.join(TAPE, "20*.jsonl"))):
        for line in open(f, encoding="utf-8"):
            line = line.strip()
            if not line: continue
            r = json.loads(line)
            ts = int(datetime.datetime.fromisoformat(r["ts_utc"]).timestamp()*1000)
            ts -= ts % 3600000
            prev = by[r["sym"]][r["venue"]].get(ts)
            if prev is None or (prev.get("mid") or 0) != r.get("mid"):
                pass
            by[r["sym"]][r["venue"]][ts] = r   # latest sample of the hour wins
    return by

def is_weekend(ts):
    t = datetime.datetime(1970,1,1)+datetime.timedelta(milliseconds=ts)
    return t.weekday()>=5 or (t.weekday()==4 and t.hour>=21) or (t.weekday()==0 and t.hour<4)

def run():
    by = load()
    report = ["# VEGA forward readout — executable paired convergence", ""]
    all_eps = []; per_sym = {}
    for sym, vd in by.items():
        if len(vd) < 3: continue
        hrs = sorted(set(vd[VEN[0]]) & set(vd[VEN[1]]) & set(vd[VEN[2]]))
        if len(hrs) < WARMUP + 2: continue
        # z on mid consensus (sigma causal)
        sd = {v: 0.0 for v in VEN}; prevD = {v: None for v in VEN}; series=[]
        for hk in hrs:
            mids = {v: math.log(vd[v][hk]["mid"]) for v in VEN}
            F = sum(mids.values())/3
            D = {v: mids[v]-F for v in VEN}
            zs={}
            for v in VEN:
                if prevD[v] is not None:
                    sd[v] = LAM*sd[v] + (1-LAM)*(D[v]-prevD[v])**2
                zs[v] = D[v]/math.sqrt(sd[v]) if sd[v]>0 else 0.0
                prevD[v] = D[v]
            series.append((hk, D, zs))
        eps=[]; last=-10**18
        for i,(hk,D,zs) in enumerate(series):
            if i < WARMUP: continue
            rich=max(VEN,key=lambda v:zs[v]); cheap=min(VEN,key=lambda v:zs[v])
            if max(abs(zs[rich]),abs(zs[cheap])) < Z_TRIGGER: continue
            if hk-last < HOLD_H*3600000: continue
            # paired entry quotes
            e = vd[rich][hk]; c = vd[cheap][hk]
            # exit: first hour >= hk+6h where both venues have samples
            ex=None
            for hk2,D2,z2 in series[i+1:]:
                if hk2 >= hk+HOLD_H*3600000 and rich in vd and cheap in vd and hk2 in vd[rich] and hk2 in vd[cheap]:
                    ex = (hk2, vd[rich][hk2], vd[cheap][hk2]); break
            if ex is None:
                eps.append({"t":hk,"sym":sym,"status":"FAILURE: no paired exit fill"}); last=hk; continue
            hk2, eR, eC = ex
            res = pair_pnl(
                {"rich_bid":e["bid"],"cheap_ask":c["ask"],"rich_bid_sz":e.get("bid_sz"),"cheap_ask_sz":c.get("ask_sz")},
                {"rich_bid":eR["bid"],"cheap_ask":eC["ask"],"rich_bid_sz":eR.get("bid_sz"),"cheap_ask_sz":eC.get("ask_sz")},
                mode="executable")
            res.update({"t":hk,"sym":sym,"weekend":is_weekend(hk),"rich":rich,"cheap":cheap,
                        "z_rich":round(zs[rich],2),"z_cheap":round(zs[cheap],2),
                        "D_rich_bps":round(D[rich]*1e4,1),"status":res.get("label","?")})
            eps.append(res); last=hk
        per_sym[sym]=eps; all_eps += [e for e in eps if "net_bps" in e]

    wke=[e for e in all_eps if e.get("weekend")]
    wk=[e for e in all_eps if not e.get("weekend")]
    fails=sum(1 for s in per_sym.values() for e in s if "FAILURE" in str(e.get("status")))
    def summ(g):
        if not g: return "n=0"
        m=sum(x["net_bps"] for x in g)/len(g)
        return "n=%d net %+.1f bps hit %.0f%%" % (len(g), m, 100*sum(1 for x in g if x["net_bps"]>0)/len(g))
    strong=[e for e in wke if e["sym"] in ("TSLAUSDT","NVDAUSDT","AAPLUSDT")]
    spy=[e for e in wke if e["sym"]=="SPYUSDT"]
    verdict = "PENDING — no executable episodes yet"
    if wke:
        m=sum(x["net_bps"] for x in wke)/len(wke)
        ms=sum(x["net_bps"] for x in strong)/len(strong) if strong else 0
        msp=sum(x["net_bps"] for x in spy)/len(spy) if spy else 0
        ok = m>0 and len(wke)>=5 and (not strong or msp <= ms)
        verdict = ("PASS — flagship claim unlocked" if ok else "FAIL — VEGA stays candidate; Weekend Desk remains submission")
    lines = [f"episodes: weekend {summ(wke)} | weekday {summ(wk)} | failed-exit rows kept: {fails}",
             f"strong subset weekend {summ(strong)} | SPY control weekend {summ(spy)}",
             f"VERDICT (pre-declared): **{verdict}**", "",
             "| t (UTC) | sym | pair | z | D bps | gross | net | weekend |", "|---|---|---|---|---|---|---|---|"]
    for e in sorted(all_eps, key=lambda x:x["t"])[:80]:
        t=datetime.datetime(1970,1,1)+datetime.timedelta(milliseconds=e["t"])
        lines.append("| %s | %s | %s/%s | %.1f/%.1f | %s | %s | %s | %s |" % (
            t.strftime("%m-%d %H:%M"), e["sym"][:7], e.get("rich","-"), e.get("cheap","-"),
            e.get("z_rich",0), e.get("z_cheap",0), e.get("D_rich_bps","-"),
            e.get("gross_bps","-"), e.get("net_bps", e.get("status","-")), "yes" if e.get("weekend") else "no"))
    report += lines
    open(os.path.join(OUT,"forward_verdict.md"),"w",encoding="utf-8").write("\n".join(report))
    print("\n".join(lines[:5])); print("saved verification/forward_verdict.md")

if __name__=="__main__": run()
