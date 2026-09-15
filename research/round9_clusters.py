"""round9: cluster-robust inference on the reserve signal (episode day-clusters)."""
import json, math, datetime
from collections import defaultdict
IDX=json.load(open(r"D:\wk-probes\venue_index.json"))
H=3600000
def dayof(k): return (datetime.datetime(1970,1,1)+datetime.timedelta(milliseconds=k)).date()
def build(sym):
    v1=IDX[sym]["bitget"]["bars"];v2=IDX[sym]["binance"]["bars"];v3=IDX[sym]["bybit"]["bars"]
    ks=sorted(set(map(int,v1))&set(map(int,v2))&set(map(int,v3)))
    ts=[k for k in ks]; L={ "bitget":[math.log(float(v1[str(k)])) for k in ks],
        "binance":[math.log(float(v2[str(k)])) for k in ks], "bybit":[math.log(float(v3[str(k)])) for k in ks]}
    F=[(L["bitget"][i]+L["binance"][i]+L["bybit"][i])/3 for i in range(len(ks))]
    D=[L["bitget"][i]-F[i] for i in range(len(ks))]
    dn=[]
    fBG={int(k):v for k,v in IDX[sym]["bitget"]["fund"].items()}; fBN={int(k):v for k,v in IDX[sym]["binance"]["fund"].items()}
    kA=sorted(fBG); kB=sorted(fBN)
    import bisect
    def last(ks_,f,t):
        i=bisect.bisect_right(ks_,t)-1
        return f[ks_[i]] if i>=0 else 0.0
    for i in range(len(ts)):
        fut=0.0
        for j in range(6):
            if i+j<len(ts):
                t2=ts[i+j]+2*H
                fut+= (last(kA,fBG,t2)-last(kB,fBN,t2))
        dn.append(D[i]-fut)
    dD=[dn[i]-dn[i-1] for i in range(1,len(dn))]
    sd=0.0; Z=[]
    for i in range(len(dn)):
        if i>0:
            sd=0.97*sd+0.03*dD[i-1]**2; Z.append(dn[i]/math.sqrt(sd) if sd>0 else 0)
        else: Z.append(0.0)
    return D,Z,ts
def clusters(sym, byday=True):
    D,Z,ts=build(sym); n=len(D); eps=[]; last=-99
    for i in range(n):
        if abs(Z[i])>=2 and i-last>=6:
            j=min(i+6,n-1)
            eps.append((ts[i], (D[i]-D[j])*1e4*(1 if Z[i]>0 else -1))); last=i
    g=defaultdict(list)
    for t,p in eps: g[dayof(t) if byday else dayof(t).isocalendar()[1]].append(p)
    cm=[sum(v)/len(v) for v in g.values()]
    m=sum(cm)/len(cm); sd=math.sqrt(sum((x-m)**2 for x in cm)/(len(cm)-1)) if len(cm)>1 else 0
    t=m/sd*math.sqrt(len(cm)) if sd else 0
    # also naive (episode-level) for contrast
    p=[x[1] for x in eps]; mn=sum(p)/len(p); sn=math.sqrt(sum((x-mn)**2 for x in p)/(len(p)-1))
    tn=mn/sn*math.sqrt(len(p))
    return len(eps), tn, len(cm), t
for sym in ["TSLAUSDT","NVDAUSDT","AAPLUSDT","SPYUSDT"]:
    ne,tn,nc,tc=clusters(sym)
    print("%-9s episodes=%3d naive t=%+.1f | DAY-CLUSTERS n=%2d robust t=%+.1f" % (sym,ne,tn,nc,tc))
