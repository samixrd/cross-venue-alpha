"""
Export static JSON data snapshots for GitHub Pages static hosting.
Generates a standalone public/ folder with index.html and json feeds.
"""
import os, sys, json, glob, datetime, shutil, math, bisect
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

def compute_empirical_episodes_and_curve(IDX):
    VEN = ["bitget", "binance", "bybit"]
    LAM = 0.97
    Z_TRIGGER = 2.0
    HOLD_H = 6
    WARMUP = 24
    FEE_BPS = 24.0
    H = 3600000

    def carry_forward(ts_data, t0, nH):
        f = {int(k): v for k, v in ts_data.items()}
        ks = sorted(f); out = 0.0
        t1 = t0 + nH * H
        import bisect
        i = bisect.bisect_right(ks, t0); j = bisect.bisect_right(ks, t1)
        for k in ks[i:j]: out += f[k]
        return out

    all_episodes = []
    for sym in IDX.keys():
        sets = [set(map(int, IDX[sym][v]["bars"].keys())) for v in VEN]
        common_hrs = sorted(set.intersection(*sets))
        if len(common_hrs) < WARMUP + HOLD_H + 2:
            continue

        rows = []
        for k in common_hrs:
            try: mids = {v: math.log(float(IDX[sym][v]["bars"][str(k)])) for v in VEN}
            except Exception: continue
            F = sum(mids.values()) / 3
            D = {v: mids[v] - F for v in VEN}
            cm = {v: carry_forward(IDX[sym][v]["fund"], k, HOLD_H) for v in VEN}
            cbar = sum(cm.values()) / 3
            Dn = {v: D[v] - (cm[v] - cbar) for v in VEN}
            rows.append((k, D, Dn, mids))

        sd = {v: 0.0 for v in VEN}
        prev = {v: None for v in VEN}
        Z = []
        for k, D, Dn, mids in rows:
            zs = {}
            for v in VEN:
                if prev[v] is not None:
                    dd = Dn[v] - prev[v]
                    sd[v] = LAM * sd[v] + (1 - LAM) * dd * dd
                zs[v] = Dn[v] / math.sqrt(sd[v]) if sd[v] > 0 else 0.0
                prev[v] = Dn[v]
            Z.append(zs)

        last_t = -10**18
        for i in range(WARMUP, len(rows)):
            t_entry = rows[i][0]
            zs = Z[i]
            rich = max(VEN, key=lambda v: zs[v])
            cheap = min(VEN, key=lambda v: zs[v])
            
            if abs(zs[rich]) < Z_TRIGGER and abs(zs[cheap]) < Z_TRIGGER: continue
            if t_entry - last_t < HOLD_H * H: continue

            t_exit = t_entry + HOLD_H * H
            exit_row = None
            for j in range(i + 1, len(rows)):
                if rows[j][0] == t_exit:
                    exit_row = rows[j]; break
            if exit_row is None:
                continue

            last_t = t_entry
            e_mids = rows[i][3]; x_mids = exit_row[3]
            gross_bps = ((e_mids[rich] - x_mids[rich]) + (x_mids[cheap] - e_mids[cheap])) / 2 * 1e4
            rich_fund = carry_forward(IDX[sym][rich]["fund"], t_entry, HOLD_H)
            cheap_fund = carry_forward(IDX[sym][cheap]["fund"], t_entry, HOLD_H)
            fund_bps = (rich_fund - cheap_fund) * 1e4
            net_bps = gross_bps - FEE_BPS - fund_bps

            all_episodes.append({
                "t_ms": t_entry, "sym": sym, "rich": rich, "cheap": cheap,
                "z_rich": round(zs[rich], 2), "z_cheap": round(zs[cheap], 2),
                "gross_bps": round(gross_bps, 2), "funding_bps": round(fund_bps, 2),
                "net_bps": round(net_bps, 2),
                "ts_human": datetime.datetime.fromtimestamp(t_entry/1000, tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            })

    all_episodes.sort(key=lambda x: x["t_ms"])
    cum = 0.0
    real_curve = []
    for e in all_episodes:
        cum += e["net_bps"]
        real_curve.append({
            "t_ms": e["t_ms"], "cum_bps": round(cum, 1), "net_bps": e["net_bps"], "sym": e["sym"],
            "date": datetime.datetime.fromtimestamp(e["t_ms"]/1000, tz=datetime.timezone.utc).strftime("%Y-%m-%d")
        })

    step = max(1, len(real_curve) // 350)
    downsampled_curve = real_curve[::step]
    if real_curve and real_curve[-1] not in downsampled_curve:
        downsampled_curve.append(real_curve[-1])

    return all_episodes, downsampled_curve

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

records = load_tape_records()
syms = sorted(set(r.get("sym") for r in records))
venues = sorted(set(r.get("venue") for r in records))
last_ts = records[-1].get("ts_utc") if records else None
chain = verify_chain(records)
tape_files = sorted(glob.glob(str(ROOT / "tape" / "20*.jsonl")))
tape_dates = [Path(f).stem for f in tape_files]
proto_hash_file = ROOT / "PROTOCOL_HASH.txt"
proto_hash = proto_hash_file.read_text().strip()[:16] if proto_hash_file.exists() else ""
matrix = get_live_matrix(records)

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
    "matrix": matrix,
}
(API_DIR / "status.json").write_text(json.dumps(status_data, indent=2))
(API_DIR / "matrix.json").write_text(json.dumps({"matrix": matrix}, indent=2))

# metrics.json
metrics_file = ROOT / "docs" / "quant_metrics.json"
metrics_data = json.loads(metrics_file.read_text()) if metrics_file.exists() else {}
(API_DIR / "metrics.json").write_text(json.dumps(metrics_data, indent=2))

# chain.json
(API_DIR / "chain.json").write_text(json.dumps(chain, indent=2))

# tape_live.json
last = list(reversed(records[-60:])) if len(records) > 60 else list(reversed(records))
tape_live = [{"ts": r.get("ts_utc","")[:19].replace("T"," "), "sym": r.get("sym",""), "venue": r.get("venue",""), "bid": r.get("bid"), "ask": r.get("ask"), "spread_bps": round(r.get("spread_bps",0),2), "funding_rate": r.get("funding_rate",0)} for r in last]
(API_DIR / "tape_live.json").write_text(json.dumps({"records": tape_live, "total": len(records)}, indent=2))

# episodes.json & equity.json
venue_index_file = ROOT / "data" / "venue_index.json"
if not venue_index_file.exists():
    venue_index_file = ROOT / "venue_index.json"
if venue_index_file.exists():
    venue_index = json.loads(venue_index_file.read_text(encoding="utf-8"))
else:
    venue_index = {}

if venue_index:
    episodes, curve = compute_empirical_episodes_and_curve(venue_index)
    last_eps = episodes[-40:] if len(episodes) > 40 else episodes
    (API_DIR / "episodes.json").write_text(json.dumps({"episodes": last_eps, "total": len(episodes)}, indent=2))
    (API_DIR / "equity.json").write_text(json.dumps({"curve": curve}, indent=2))
else:
    print("Warning: venue_index not found")

print(f"Exported static data to {PUB}:")
print(f" - status.json ({len(records)} records)")
print(f" - metrics.json")
print(f" - chain.json")
print(f" - tape_live.json")
print(f" - episodes.json ({len(episodes)} total)")
print(f" - equity.json ({len(curve)} points)")
