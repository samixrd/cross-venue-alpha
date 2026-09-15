import json, math, datetime

# weekend_pairs.json: [sat_date, sunmove, monret(perp-vs-perp Monday session)]
d = json.load(open(r"D:\wk-probes\weekend_pairs.json"))
BASK = ["AAPLUSDT","TSLAUSDT","NVDAUSDT","MSFTUSDT","GOOGLUSDT","AMZNUSDT","METAUSDT"]

def stats(r):
    n=len(r); m=sum(r)/n; s=math.sqrt(sum((x-m)**2 for x in r)/(n-1)) if n>1 else 0
    return n, m*100, s*100

print("=== Baseline 1: Always-Long Monday (perp Mon session, n=12 weekends) ===")
for s in ["SPYUSDT","QQQUSDT"]:
    rows=[r[2] for r in d[s]]; n,m,sd=stats(rows)
    print("%-9s avg %+.2f%%/wk  sd %.2f%%  IR=%.2f" % (s,m,sd,m/sd if sd else 0))
bk=[sum(d[x][i][2] for x in BASK)/7 for i in range(len(d["SPYUSDT"]))][0:12]
n,m,sd=stats(bk); print("BASKET    avg %+.2f%%/wk  sd %.2f%%  IR=%.2f" % (m,sd,m/sd))

print("\n=== Signal-conditioned (basket weekend move sign), perp Monday session ===")
sm=[sum(d[x][i][1] for x in BASK)/7 for i in range(len(d["SPYUSDT"]))]
mo=[sum(d[x][i][2] for x in BASK)/7 for i in range(len(d["SPYUSDT"]))]
up=[mo[i] for i in range(len(sm)) if sm[i]>0]; dn=[mo[i] for i in range(len(sm)) if sm[i]<0]
for nm,g in (("after up-weekend (LONG)",up),("after down-weekend (SHORT)",dn)):
    n,m,sd=stats(g)
    print("%-28s n=%2d avg %+.2f%%" % (nm,n,m))
# strategy PnL = continuation (sign(sm)*mo) vs baseline
cont=[(1 if sm[i]>0 else -1)*mo[i] for i in range(len(sm))]
n,m,sd=stats(cont); print("continuation rule          n=%2d avg %+.2f%%/wk IR=%.2f  (vs always-long %+.2f%%)"%(n,m,m/sd if sd else 0,sum(mo)/len(mo)))
rev=[-c for c in cont]
n,m,sd=stats(rev); print("reversal rule              n=%2d avg %+.2f%%/wk IR=%.2f"%(n,m,m/sd if sd else 0))

print("\n=== Same test vs TRUE underlying gap would need T1 n=9; using perp-vs-perp here as proxy ===")
print("=== Weak-signal zone (|sm|<0.15%): is the signal just beta-to-always-long? ===")
mid=[mo[i] for i in range(len(sm)) if abs(sm[i])<0.0015]
n,m,sd=stats(mid); print("mid-zone avg Mon %+.2f%% n=%d"%(m,n))
big=[mo[i] for i in range(len(sm)) if abs(sm[i])>=0.0015]
n,m,sd=stats(big); print("big-zone avg Mon %+.2f%% n=%d"%(m,n))
