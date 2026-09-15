import json, math
d = json.load(open(r"D:\wk-probes\weekend_pairs.json"))
sm=[r[1] for r in d["SPYUSDT"]]; mo=[r[2] for r in d["SPYUSDT"]]
n=len(sm)
e_all=sum(mo)/n*100
e_up=[mo[i] for i in range(n) if sm[i]>0]; e_dn=[mo[i] for i in range(n) if sm[i]<0]
e_upm=sum(e_up)/len(e_up)*100; e_dnm=sum(e_dn)/len(e_dn)*100
print("E[Mon]        = %+.2f%%  (always-long baseline, n=%d)" % (e_all,n))
print("E[Mon | w>0]  = %+.2f%%  (n=%d)" % (e_upm,len(e_up)))
print("E[Mon | w<0]  = %+.2f%%  (n=%d)" % (e_dnm,len(e_dn)))
print("Long leg excess over baseline  = %+.2f%%" % (e_upm-e_all))
print("Short leg: short return = -Mon | w<0 = %+.2f%% ; vs baseline: %+.2f%%" % (-e_dnm, -e_dnm-(e_all)))
# strategy excess over always-long, per week: sgn(w)*mo - always_long
exc=[(1 if sm[i]>0 else -1)*mo[i]-sum(mo)/n for i in range(n)]
m=sum(exc)/n*100; sd=math.sqrt(sum((x-m/100)**2 for x in exc)/(n-1))*100
t=(m/sd)*math.sqrt(n) if sd else 0
print("Strategy minus always-long: avg %+.2f%%/wk  IR %.2f  t=%+.2f" % (m, m/sd if sd else 0, t))
