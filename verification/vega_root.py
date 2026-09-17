"""VEGA tape root — same raw-line Merkle scheme as WD tape, own files.
Usage: python vega_root.py root --date 2026-09-20   (Sun 17:20 UTC task)
       python vega_root.py verify
Frozen cutoff: weekend samples up to Sun 17:00 UTC (same convention as WD)."""
import json, glob, os, sys, hashlib, datetime, argparse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAPE = os.path.join(ROOT, "tape")
MAN  = os.path.join(ROOT, "verification")
os.makedirs(MAN, exist_ok=True)
def sha(b): return hashlib.sha256(b).hexdigest()
def lines_upto(cutoff):
    out=[]
    for f in sorted(glob.glob(os.path.join(TAPE,"20*.jsonl"))):
        for line in open(f,encoding="utf-8"):
            l=line.strip()
            if not l: continue
            r=json.loads(l)
            if datetime.datetime.fromisoformat(r["ts_utc"])<=cutoff: out.append(l)
    return out
def merkle(leaves):
    if not leaves: return "EMPTY"
    lvl=[sha(l.encode()) for l in leaves]
    while len(lvl)>1:
        if len(lvl)%2: lvl.append(lvl[-1])
        lvl=[sha((lvl[i]+lvl[i+1]).encode()) for i in range(0,len(lvl),2)]
    return lvl[0]
def root_for(datestr):
    cut=datetime.datetime.fromisoformat(datestr+"T17:00:00+00:00")
    ls=lines_upto(cut); r=merkle(ls)
    mp=os.path.join(MAN,"root_"+datestr+".json")
    if os.path.exists(mp):
        old=json.load(open(mp))
        print("committed:",old["root"],"| recompute:",r,"| match:",old["root"]==r)
        return old["root"]==r
    json.dump({"cutoff_utc":cut.isoformat(),"root":r,"record_count":len(ls),
               "generated":datetime.datetime.now(datetime.timezone.utc).isoformat()},open(mp,"w"))
    print("VEGA tape root",datestr,":",r,f"({len(ls)} records)")
    print("X card:\nThree-venue tape committed before the outcome:\n%s\n13 symbols, bid/ask/depth/funding, cutoff Sun 17:00 UTC. Verdict rule pre-declared. #BitgetHackathon @Bitget_AI"%r)
    return True
if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("mode",choices=["root","verify"]); ap.add_argument("--date",default="2026-09-20")
    a=ap.parse_args()
    if a.mode=="root": sys.exit(0 if root_for(a.date) else 1)
    else:
        ok=True
        for p in sorted(glob.glob(os.path.join(MAN,"root_*.json"))):
            d=json.load(open(p)); ls=lines_upto(datetime.datetime.fromisoformat(d["cutoff_utc"]))
            m=merkle(ls); good=m==d["root"] and len(ls)==d["record_count"]
            ok&=good; print("VERIFY %s: %s root=%s records=%d"%(os.path.basename(p),"PASS" if good else "FAIL",m[:16],len(ls)))
        sys.exit(0 if ok else 1)
