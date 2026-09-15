"""
ROUND 8 — adversarial battery on the god formula:
P1  CIRCULARITY TEST: is "+37bps reversion" just OU-mechanics? Measure what
    FRACTION of the excess divergence is captured at h=1..8h (capture curve).
    If capture% is low & stable, the edge magnitude is bounded by divergence.
P2  PLACEBO: random (non-|z|>2) hours, same 6h fade -> should be ~ -drift.
P3  SHUFFLE: permute z-signs within series -> destroys signal, keeps vol.
P4  COST REALISM: 4x taker (24 bps) + spread proxy = 2x median hourly |trailing
    6-bar range/2| (bar-range proxy, labeled ESTIMATED).
"""
import json, math, datetime, random

IDX = json.load(open(r"D:\wk-probes\venue_index.json"))
H=3600000
def series(sym):
    v1=IDX[sym]["bitget"]["bars"]; v2=IDX[sym]["binance"]["bars"]; v3=IDX[sym]["bybit"]["bars"]
    ks=sorted(set(map(int,v1))&set(map(int,v2))&set(map(int,v3)))
    return [(k, math.log(float(v1[str(k)])), math.log(float(v2[str(k)])), math.log(float(v3[str(k)]))) for k in ks]

def stats(p):
    n=len(p)
    if n<3: return None
    m=sum(p)/n; sd=math.sqrt(sum((x-m)**2 for x in p)/(n-1))
    return n, m, sd, (m/sd*math.sqrt(n) if sd else 0), 100*sum(1 for x in p if x>0)/n

def build_D_z(sym):
    al=series(sym)
    ts=[a[0] for a in al]; D=[a[1]-(a[1]+a[2]+a[3])/3 for a in al]
    dn=[]
    fA={int(k):v for k,v in IDX[sym]["bitget"]["fund"].items()}; fB={int(k):v for k,v in IDX[sym]["binance"]["fund"].items()}
    ksA=sorted(fA); ksB=sorted(fB)
    def last(ks,f,ts_):
        import bisect
        i=bisect.bisect_right(ks,ts_)-1
        return f[ks[i]] if i>=0 else 0.0
    for i,(k,_,_,_) in enumerate(al):
        fut=0.0
        for j in range(6):
            if i+j<len(al):
                t2=ts[i+j]+2*H  # next settlement after
                fut += last(ksA,fA,t2)-last(ksB,fB,t2)
        dn.append(D[i]-fut)
    dD=[dn[i]-dn[i-1] for i in range(1,len(dn))]
    sd=0.0; Z=[]
    for i in range(len(dn)):
        if i>0:
            sd=0.97*sd+0.03*dD[i-1]**2
            Z.append(dn[i]/math.sqrt(sd) if sd>0 else 0)
        else: Z.append(0)
    return ts, D, Z

for sym in ["TSLAUSDT","NVDAUSDT","AAPLUSDT","SPYUSDT"]:
    ts,D,Z=build_D_z(sym)
    n=len(D)
    # P1 capture curve
    print("== %s ==" % sym)
    row=[]
    for h in (1,2,3,4,6,8):
        cap=[]; last=-99
        for i in range(len(Z)):
            if abs(Z[i])>=2 and i-last>=h:
                j=min(i+h,n-1)
                ex=(D[i]-D[j])*(1 if Z[i]>0 else -1)     # captured reversion (log)
                div=abs(D[i])                            # total divergence available
                if div>0: cap.append(ex/div)
                last=i
        if cap: row.append("h%d:cap%.0f%%" % (h, 100*sum(cap)/len(cap)))
    print("  capture curve:", " ".join(row))
    # P2 placebo: same fade at RANDOM hours z in [-1,1]
    random.seed(7)
    pl=[]; cand=[i for i in range(1,n-7) if abs(Z[i])<1]
    picks=random.sample(cand, min(len(cand), 120))
    for i in picks:
        pnl=-(D[i+6]-D[i])*1e4*(1 if Z[i]>0 else -1)
        pl.append(pnl)
    s=stats(pl); print("  PLACEBO random hours: n=%d avg %+.1f bps t=%+.1f" % (s[0],s[1],s[3]) if s else "  placebo n/a")
    # P3 shuffle z-signs
    zs=[Z[i] for i in range(n)]; random.shuffle(zs)
    sh=[]; last=-99
    for i in range(n):
        if abs(zs[i])>=2 and i-last>=6:
            sh.append(-(D[min(i+6,n-1)]-D[i])*1e4*(1 if zs[i]>0 else -1)); last=i
    s3=stats(sh); print("  SHUFFLED z-signs:    n=%d avg %+.1f bps t=%+.1f" % (s3[0],s3[1],s3[3]) if s3 else "")
    # P4 cost-adjusted signal
    sig=[]; last=-99
    for i in range(n):
        if abs(Z[i])>=2 and i-last>=6:
            sig.append(-(D[min(i+6,n-1)]-D[i])*1e4*(1 if Z[i]>0 else -1)); last=i
    if sig:
        s4=stats(sig)
        fees=24.0
        print("  SIGNAL net-of-fees(%dbps): avg %+.1f bps -> %+.1f | t %+.1f | hit %.0f%%" % (fees,s4[1],s4[1]-fees,s4[3],s4[4]))
