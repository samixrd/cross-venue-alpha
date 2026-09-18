"""
Export static JSON data snapshots for GitHub Pages static hosting.
Generates a standalone public/ folder with index.html and json feeds.
"""
import os, sys, json, glob, datetime, shutil
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

PUB = ROOT / "public"
API_DIR = PUB / "api"
PUB.mkdir(exist_ok=True)
API_DIR.mkdir(exist_ok=True)

# 1. Copy index.html
shutil.copyfile(ROOT / "dashboard" / "index.html", PUB / "index.html")

# 2. Helpers
def load_tape_records():
    records = []
    for path in sorted(glob.glob(str(ROOT / "tape" / "20*.jsonl"))):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try: records.append(json.loads(line))
                    except: pass
    return records

def verify_chain(records):
    if not records:
        return {"status": "NO_DATA", "checked": 0, "tip": None, "sessions": 0}
    sessions = 0
    for i, r in enumerate(records):
        actual_prev = r.get("prev_hash", "")
        if actual_prev == "GENESIS" or i == 0:
            sessions += 1
            continue
        expected_prev = records[i - 1].get("chain", "")[:64]
        if actual_prev and expected_prev and actual_prev != expected_prev:
            return {"status": "BROKEN", "checked": i, "tip": records[i-1].get("chain","")[:16], "break_at": i, "sessions": sessions}
    tip = records[-1].get("chain", "") if records else ""
    return {"status": "INTACT", "checked": len(records), "tip": tip[:16] if tip else None, "sessions": sessions}

def is_weekend_now():
    n = datetime.datetime.now(datetime.timezone.utc)
    wd, h = n.weekday(), n.hour
    return (wd == 4) or (wd in (5, 6)) or (wd == 0 and h <= 21)

def run_signal_pipeline(venue_index):
    try:
        from strategy.signal import episodes_for, VEN
        all_eps = []
        for sym, sym_data in venue_index.items():
            if sym == "SPY": continue
            if not all(v in sym_data for v in VEN): continue
            eps, _ = episodes_for(sym_data)
            for e in eps: e["sym"] = sym
            all_eps.extend(eps)
        all_eps.sort(key=lambda x: x["t_ms"])
        return all_eps
    except Exception as ex:
        print("Signal pipeline err:", ex)
        return []

def build_equity_curve(episodes):
    from strategy.execution import FEE_BPS
    cumulative = 0.0
    curve = []
    for ep in episodes:
        z_spread = abs(ep.get("z_rich", 0)) + abs(ep.get("z_cheap", 0))
        gross = z_spread * 3.0
        net = gross - FEE_BPS
        cumulative += net
        curve.append({"t_ms": ep["t_ms"], "cum_bps": round(cumulative, 1), "net_bps": round(net, 1), "sym": ep.get("sym","")})
    return curve

records = load_tape_records()
syms = sorted(set(r.get("sym") for r in records))
venues = sorted(set(r.get("venue") for r in records))
last_ts = records[-1].get("ts_utc") if records else None
chain = verify_chain(records)
tape_files = sorted(glob.glob(str(ROOT / "tape" / "20*.jsonl")))
tape_dates = [Path(f).stem for f in tape_files]
proto_hash_file = ROOT / "PROTOCOL_HASH.txt"
proto_hash = proto_hash_file.read_text().strip()[:16] if proto_hash_file.exists() else ""

status_data = {
    "record_count": len(records),
    "symbol_count": len(syms),
    "venue_count": len(venues),
    "symbols": syms,
    "venues": venues,
    "last_ts": last_ts,
    "tape_dates": tape_dates,
    "chain_status": chain["status"],
    "chain_tip": chain["tip"],
    "is_weekend": is_weekend_now(),
    "protocol_hash": proto_hash,
    "collector_mode": "WEEKEND 5-min sampling" if is_weekend_now() else "WEEKDAY hourly sampling",
}
(API_DIR / "status.json").write_text(json.dumps(status_data, indent=2))

# metrics.json
metrics_file = ROOT / "docs" / "quant_metrics.json"
metrics_data = json.loads(metrics_file.read_text()) if metrics_file.exists() else {}
(API_DIR / "metrics.json").write_text(json.dumps(metrics_data, indent=2))

# chain.json
(API_DIR / "chain.json").write_text(json.dumps(chain, indent=2))

# tape_live.json
last = list(reversed(records[-20:])) if len(records) > 20 else list(reversed(records))
tape_live = [{"ts": r.get("ts_utc","")[:19].replace("T"," "), "sym": r.get("sym",""), "venue": r.get("venue",""), "bid": r.get("bid"), "ask": r.get("ask"), "spread_bps": round(r.get("spread_bps",0),2), "funding_rate": r.get("funding_rate",0)} for r in last]
(API_DIR / "tape_live.json").write_text(json.dumps({"records": tape_live, "total": len(records)}, indent=2))

# episodes.json & equity.json
venue_index_file = ROOT / "data" / "venue_index.json"
if not venue_index_file.exists():
    venue_index_file = ROOT / "venue_index.json"
venue_index = json.loads(venue_index_file.read_text()) if venue_index_file.exists() else {}
episodes = run_signal_pipeline(venue_index)

if episodes:
    last_eps = episodes[-30:] if len(episodes) > 30 else episodes
    for e in last_eps:
        e["ts_human"] = datetime.datetime.fromtimestamp(e["t_ms"]/1000, tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    (API_DIR / "episodes.json").write_text(json.dumps({"episodes": last_eps, "total": len(episodes)}, indent=2))

    curve = build_equity_curve(episodes)
    if len(curve) > 400:
        step = len(curve) // 400
        curve = curve[::step]
    (API_DIR / "equity.json").write_text(json.dumps({"curve": curve}, indent=2))
else:
    print("Warning: episodes was empty, checking existing cached json...")
    if not (API_DIR / "episodes.json").exists():
        (API_DIR / "episodes.json").write_text(json.dumps({"episodes": [], "total": 0}, indent=2))
    if not (API_DIR / "equity.json").exists():
        (API_DIR / "equity.json").write_text(json.dumps({"curve": []}, indent=2))

print(f"Exported static data to {PUB}:")
print(f" - status.json ({len(records)} records)")
print(f" - metrics.json")
print(f" - chain.json")
print(f" - tape_live.json")
print(f" - episodes.json ({len(episodes)} total)")
print(f" - equity.json ({len(curve)} points)")
