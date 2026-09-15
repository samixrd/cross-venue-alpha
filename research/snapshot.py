"""
VEGA WEEKLY QUANT SNAPSHOT — state/execution estimation fold (NOT alpha).
The |z|>=2 fade is frozen (PROTOCOL.md §1); this module only DESCRIBES
market state per ISO week from strictly-past data (causal z, weekly
aggregates). Nothing here may feed back into the signal.
Output: verification/snapshots/all_weeks.md (+ week-vs-week "what changed").
"""
import json, math, datetime, sys, os
from collections import defaultdict
sys.path.insert(0, r"D:\cross-venue-alpha")
from strategy.signal import VEN, Z_TRIGGER, HOLD_H, LAM, WARMUP

IDX=json.load(open(r"D:\cross-venue-alpha\data\venue_index.json"))
OUTDIR=r"D:\cross-venue-alpha\verification\snapshots"; os.makedirs(OUTDIR,exist_ok=True)
H=3600000; FEE=24.0

def wk(ms):
    d=datetime.datetime(1970,1,1)+datetime.timedelta(milliseconds=ms)
    y,w,_=d.isocalendar(); return "%d-W%02d"%(y,w)
def median(x):
    x=sorted(x); n=len(x)
    return 0.0 if n==0 else (x[n//2] if n%2 else (x[n//2-1]+x[n//2])/2)

def causal_series(sym):
    v={vv:IDX[sym][vv]["bars"] for vv in VEN}
    ks=sorted(set(map(int,v["bitget"]))&set(map(int,v["binance"]))&set(map(int,v["bybit"])))
    seq=[]; sd={x:0.0 for x in VEN}; prev={x:None for x in VEN}
    for k in ks:
        try: lg={x:math.log(float(v[x][str(k)])) for x in VEN}
        except Exception: continue
        F=sum(lg.values())/3; D={x:lg[x]-F for x in VEN}
        zs={}
        for x in VEN:
            if prev[x] is not None: sd[x]=LAM*sd[x]+(1-LAM)*(D[x]-prev[x])**2
            zs[x]=D[x]/math.sqrt(sd[x]) if sd[x]>0 else 0.0
            prev[x]=D[x]
        seq.append((k,D,zs))
    return seq

def half_life(series):
    x=[D["bitget"] for _,D,_ in series]; y=[series[i+1][1]["bitget"]-x[i] for i in range(len(x)-1)]
    x=x[:-1]; n=len(x)
    if n<24: return None
    mx=sum(x)/n; my=sum(y)/n
    sxx=sum((t-mx)**2 for t in x)
    if not sxx: return None
    k=-sum((a-mx)*(b-my) for a,b in zip(x,y))/sxx
    return math.log(2)/k if k>0 else None

def lead_scores(seq):
    """per pair, corr(dA_t,dB_{t+1h}) - corr(dB_t,dA_{t+1h}); + => A leads."""
    def dd(v,i): return seq[i][1][v]-seq[i-1][1][v]
    out={}
    for i,a in enumerate(VEN):
        for b in VEN[i+1:]:
            la=[];lb=[];lb2=[];la2=[]
            for j in range(1,len(seq)-1):
                la.append(dd(a,j)); lb.append(dd(b,j+1))
                lb2.append(dd(b,j)); la2.append(dd(a,j+1))
            def cr(u,w):
                n=len(u); mu=sum(u)/n; mw=sum(w)/n
                sxx=sum((t-mu)**2 for t in u); syy=sum((t-mw)**2 for t in w)
                return sum((p-mu)*(q-mw) for p,q in zip(u,w))/math.sqrt(sxx*syy) if sxx and syy else 0
            out[(a,b)]=round(cr(la,lb)-cr(lb2,la2),2)
    return out

def episodes(seq):
    eps=[]; last=-10**18
    idx={k:i for i,(k,_,_) in enumerate(seq)}
    for i,(k,D,zs) in enumerate(seq):
        if i<WARMUP: continue
        rich=max(VEN,key=lambda v:zs[v]); cheap=min(VEN,key=lambda v:zs[v])
        if max(abs(zs[rich]),abs(zs[cheap]))<Z_TRIGGER: continue
        if k-last<HOLD_H*H: continue
        last=k
        j=min(i+HOLD_H,len(seq)-1)
        k2,D2,_=seq[j]
        g=((D[rich]-D2[rich])+(D2[cheap]-D[cheap]))/2*1e4
        eps.append((k,g,g-FEE))
    return eps

W=defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
HL=defaultdict(list); LEAD=defaultdict(list)
for sym in IDX:
    s=causal_series(sym)
    for k,D,zs in s: W[wk(k)][sym]["D"].append(max(abs(v) for v in D.values())*1e4)
    for k,g,n in episodes(s): W[wk(k)][sym]["ep"].append((g,n))
    hl=half_life(s)
    if hl: W[wk(s[-1][0])][sym]["hl"]=hl     # attribute at series end (lagged by design)
    sc=lead_scores(s)
    for kk,v in sc.items(): W[wk(s[-1][0])][sym]["lead"]=(kk,v)

rows=[]
for w in sorted(W):
    S=W[w]
    Ds=[x for sym in S for x in S[sym].get("D",[])]
    ep_all=[(sym,g,n) for sym in S for g,n in S[sym].get("ep",[])]
    hls=[S[sym]["hl"]*60 for sym in S if "hl" in S[sym]]
    leads={}
    for sym in S:
        for (a,b),v in [S[sym]["lead"]] if "lead" in S[sym] else []:
            leads[(a,b)]=leads.get((a,b),0)+v/len(S)
    by_sym=defaultdict(list)
    for sym,g,n in ep_all: by_sym[sym].append(n)
    perf=sorted(((median(v),s) for s,v in by_sym.items()),reverse=True)
    conv=100*sum(1 for _,g,_ in ep_all if g>0)/len(ep_all) if ep_all else 0
    rows.append({
        "week":w,"obs_hours":len(Ds),
        "median_dislocation_bps":round(median(Ds),2),
        "median_half_life_min":round(median(hls),1) if hls else None,
        "episodes":len(ep_all),
        "convergence_rate_pct":round(conv,1),
        "median_net_bps_fee_floor":round(median([n for _,_,n in ep_all]),1) if ep_all else None,
        "best":[(s,round(m,1)) for m,s in perf[:3]],
        "worst":[(s,round(m,1)) for m,s in perf[-2:]],
        "lead": {f"{a}>{b}":v for (a,b),v in sorted(leads.items(),key=lambda x:-x[1]) if abs(v)>0.05} or None})

md=["# VEGA weekly quant snapshots — STATE ESTIMATION FOLD (alpha frozen)","",
    "Causal-only: z uses EWMA over past hours; half-life/leadership attributed at series end (lagged).",
    "net = gross − 24 bps fee floor, MID mode — spread slippage pending executable tape.","",
    "| week | disloc med (bps) | half-life (min) | episodes | conv% | net med (bps) | best | worst | venue lead |",
    "|---|---|---|---|---|---|---|---|---|"]
for r in rows:
    md.append("| %s | %s | %s | %d | %s | %s | %s | %s | %s |"%(
        r["week"],r["median_dislocation_bps"],r["median_half_life_min"],r["episodes"],
        r["convergence_rate_pct"],r["median_net_bps_fee_floor"],
        r["best"],r["worst"],
        " ".join("%s(%+.2f)"%(k,v) for k,v in (r["lead"] or {}).items())))

if len(rows)>=2:
    a,b=rows[-2],rows[-1]
    md += ["","## What changed: %s → %s"%(a["week"],b["week"]),
       "*(latest week is partial — compare levels cautiously; rate stability, not levels, is the monitor)*",
           "- dislocation %.2f → %.2f bps"%(a["median_dislocation_bps"],b["median_dislocation_bps"]),
           "- convergence %.1f%% → %.1f%%"%(a["convergence_rate_pct"],b["convergence_rate_pct"]),
           "- net median %s → %s bps"%(a["median_net_bps_fee_floor"],b["median_net_bps_fee_floor"]),
           "- best names %s → %s"%(a["best"],b["best"])]
md += ["","**Rule: no snapshot metric may alter the trigger, universe, horizon, or estimator.**",""]
open(os.path.join(OUTDIR,"all_weeks.md"),"w",encoding="utf-8").write("\n".join(md))
print("\n".join(md[-14:]))
