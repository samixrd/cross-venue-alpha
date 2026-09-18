"""
VEGA Dashboard — FastAPI backend
Serves live data from tape, signal pipeline, and quant metrics.
Run: python dashboard/server.py
Open: http://localhost:8000
"""
import os, sys, json, glob, math, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    print("pip install fastapi uvicorn[standard]")
    sys.exit(1)

app = FastAPI(title="VEGA Dashboard", docs_url=None, redoc_url=None)

# ── Helpers ────────────────────────────────────────────────────────────────────

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

def load_metrics():
    path = ROOT / "docs" / "quant_metrics.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}

def load_venue_index():
    for candidate in [ROOT / "data" / "venue_index.json", ROOT / "venue_index.json"]:
        if candidate.exists():
            return json.loads(candidate.read_text())
    return {}

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

def get_live_matrix(records):
    latest = {}
    for r in records:
        sym = r.get("sym")
        venue = r.get("venue")
        if sym and venue:
            latest[(sym, venue)] = r

    symbols = ["TSLAUSDT","NVDAUSDT","AAPLUSDT","AMZNUSDT","MSFTUSDT","GOOGLUSDT","METAUSDT","SPYUSDT","QQQUSDT","COINUSDT","MSTRUSDT","HOODUSDT","CRCLUSDT"]
    matrix = []
    for s in symbols:
        bg = latest.get((s, "bitget"), {})
        bn = latest.get((s, "binance"), {})
        by = latest.get((s, "bybit"), {})

        bg_mid = bg.get("mid") or ((bg.get("bid",0)+bg.get("ask",0))/2 if bg.get("bid") else None)
        bn_mid = bn.get("mid") or ((bn.get("bid",0)+bn.get("ask",0))/2 if bn.get("bid") else None)
        by_mid = by.get("mid") or ((by.get("bid",0)+by.get("ask",0))/2 if by.get("bid") else None)

        mids = [m for m in [bg_mid, bn_mid, by_mid] if m and m > 0]
        mean_mid = sum(mids) / len(mids) if mids else 0.0

        disloc_bps = 0.0
        if mids and mean_mid > 0:
            max_diff = max(abs(m - mean_mid) for m in mids)
            disloc_bps = round((max_diff / mean_mid) * 10000, 2)

        matrix.append({
            "sym": s,
            "bitget": round(bg_mid, 2) if bg_mid else None,
            "binance": round(bn_mid, 2) if bn_mid else None,
            "bybit": round(by_mid, 2) if by_mid else None,
            "disloc_bps": disloc_bps,
            "bg_spread": round(bg.get("spread_bps", 0), 2) if bg else None,
            "last_ts": (bg.get("ts_utc") or bn.get("ts_utc") or by.get("ts_utc",""))[:19].replace("T"," ")
        })
    return matrix

# ── API Routes ─────────────────────────────────────────────────────────────────

@app.get("/api/status")
def api_status():
    records = load_tape_records()
    syms = set(r.get("sym") for r in records)
    venues = set(r.get("venue") for r in records)
    last_ts = records[-1].get("ts_utc") if records else None
    chain = verify_chain(records)
    tape_files = sorted(glob.glob(str(ROOT / "tape" / "20*.jsonl")))
    tape_dates = [Path(f).stem for f in tape_files]
    proto_hash_file = ROOT / "PROTOCOL_HASH.txt"
    proto_hash = proto_hash_file.read_text().strip()[:16] if proto_hash_file.exists() else ""
    matrix = get_live_matrix(records)
    return JSONResponse({
        "record_count": len(records),
        "matrix": matrix,
        "symbol_count": len(syms),
        "venue_count": len(venues),
        "symbols": sorted(syms),
        "venues": sorted(venues),
        "last_ts": last_ts,
        "tape_dates": tape_dates,
        "chain_status": chain["status"],
        "chain_tip": chain["tip"],
        "is_weekend": is_weekend_now(),
        "protocol_hash": proto_hash,
        "collector_mode": "WEEKEND 5-min sampling" if is_weekend_now() else "WEEKDAY hourly sampling",
    })

@app.get("/api/matrix")
def api_matrix():
    records = load_tape_records()
    return JSONResponse({"matrix": get_live_matrix(records)})

@app.get("/api/metrics")
def api_metrics():
    return JSONResponse(load_metrics())

@app.get("/api/episodes")
def api_episodes(limit: int = 30):
    vi = load_venue_index()
    if not vi:
        return JSONResponse({"episodes": [], "error": "venue_index not found"})
    eps = run_signal_pipeline(vi)
    last = eps[-limit:] if len(eps) > limit else eps
    for e in last:
        e["ts_human"] = datetime.datetime.fromtimestamp(e["t_ms"]/1000, tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return JSONResponse({"episodes": last, "total": len(eps)})

@app.get("/api/equity")
def api_equity():
    vi = load_venue_index()
    if not vi:
        return JSONResponse({"curve": []})
    eps = run_signal_pipeline(vi)
    curve = build_equity_curve(eps)
    if len(curve) > 400:
        step = len(curve) // 400
        curve = curve[::step]
    return JSONResponse({"curve": curve})

@app.get("/api/tape/live")
def api_tape_live(limit: int = 60):
    records = load_tape_records()
    last = list(reversed(records[-limit:])) if len(records) > limit else list(reversed(records))
    simplified = [{"ts": r.get("ts_utc","")[:19].replace("T"," "), "sym": r.get("sym",""), "venue": r.get("venue",""), "bid": r.get("bid"), "ask": r.get("ask"), "spread_bps": round(r.get("spread_bps",0),2), "funding_rate": r.get("funding_rate",0)} for r in last]
    return JSONResponse({"records": simplified, "total": len(records)})

@app.get("/api/chain")
def api_chain():
    records = load_tape_records()
    return JSONResponse(verify_chain(records))

DASH_DIR = Path(__file__).parent

@app.get("/", response_class=HTMLResponse)
def root():
    html_path = DASH_DIR / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>index.html not found</h1>")

if __name__ == "__main__":
    print("VEGA Dashboard -> http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
