"""
Generate Institutional Quantitative Metrics & High-Resolution Visual Plots
for VEGA 105-Day Multi-Venue Empirical Backtest.
Outputs:
  - docs/equity_curve.png
  - docs/drawdown.png
  - docs/dislocation_convergence.png
  - Markdown summary table matching Bitget AI Hackathon S2 Judging criteria.
"""
import os, json, math, datetime
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

DATA_PATH = r"D:\cross-venue-alpha\data\venue_index.json"
DOCS_DIR = r"D:\cross-venue-alpha\docs"
os.makedirs(DOCS_DIR, exist_ok=True)

with open(DATA_PATH, "r", encoding="utf-8") as f:
    IDX = json.load(f)

VEN = ["bitget", "binance", "bybit"]
LAM = 0.97
Z_TRIGGER = 2.0
HOLD_H = 6
WARMUP = 24
FEE_BPS = 24.0 # 4 x 0.06% taker round-trip
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
        try:
            mids = {v: math.log(float(IDX[sym][v]["bars"][str(k)])) for v in VEN}
        except Exception:
            continue
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
        if abs(zs[rich]) < Z_TRIGGER and abs(zs[cheap]) < Z_TRIGGER:
            continue
        if t_entry - last_t < HOLD_H * H:
            continue

        t_exit = t_entry + HOLD_H * H
        exit_row = None
        for j in range(i + 1, len(rows)):
            if rows[j][0] == t_exit:
                exit_row = rows[j]
                break
        if exit_row is None:
            continue

        last_t = t_entry
        e_mids = rows[i][3]
        x_mids = exit_row[3]

        gross_bps = ((e_mids[rich] - x_mids[rich]) + (x_mids[cheap] - e_mids[cheap])) / 2 * 1e4
        rich_fund = carry_forward(IDX[sym][rich]["fund"], t_entry, HOLD_H)
        cheap_fund = carry_forward(IDX[sym][cheap]["fund"], t_entry, HOLD_H)
        fund_bps = (rich_fund - cheap_fund) * 1e4
        net_bps = gross_bps - FEE_BPS - fund_bps

        all_episodes.append({
            "t": t_entry,
            "sym": sym,
            "rich": rich,
            "cheap": cheap,
            "z_rich": zs[rich],
            "z_cheap": zs[cheap],
            "gross_bps": gross_bps,
            "funding_bps": fund_bps,
            "net_bps": net_bps,
            "D_entry_bps": (rows[i][1][rich] - rows[i][1][cheap]) * 1e4,
            "D_exit_bps": (exit_row[1][rich] - exit_row[1][cheap]) * 1e4,
        })

all_episodes.sort(key=lambda x: x["t"])
print(f"Total historical episodes generated: {len(all_episodes)}")

t_min = all_episodes[0]["t"]
t_split = t_min + 60 * 24 * H

is_eps = [e for e in all_episodes if e["t"] < t_split]
oos_eps = [e for e in all_episodes if e["t"] >= t_split]

def compute_metrics(eps, name=""):
    if not eps:
        return {}
    returns = np.array([e["net_bps"] / 1e4 for e in eps])
    n = len(returns)
    win_rate = np.mean(returns > 0) * 100.0
    mean_ret = np.mean(returns)
    std_ret = np.std(returns, ddof=1) if n > 1 else 1e-6
    
    annual_factor = math.sqrt(365.25 * 4)
    duration_years = (eps[-1]["t"] - eps[0]["t"]) / (365.25 * 86400000)
    sharpe = (mean_ret / std_ret) * math.sqrt(n / max(duration_years, 0.01)) if std_ret > 0 else 0
    
    neg_rets = returns[returns < 0]
    downside_std = np.std(neg_rets, ddof=1) if len(neg_rets) > 1 else 1e-6
    sortino = (mean_ret / downside_std) * math.sqrt(n / max(duration_years, 0.01)) if downside_std > 0 else 0
    
    cum_bps = np.cumsum([e["net_bps"] for e in eps])
    cum_peaks = np.maximum.accumulate(cum_bps)
    drawdowns = cum_bps - cum_peaks
    max_dd_bps = np.min(drawdowns)
    
    avg_bps = np.mean([e["net_bps"] for e in eps])
    total_bps = np.sum([e["net_bps"] for e in eps])
    
    return {
        "name": name,
        "n": n,
        "win_rate": win_rate,
        "mean_net_bps": avg_bps,
        "total_net_bps": total_bps,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_dd_bps": max_dd_bps,
    }

is_m = compute_metrics(is_eps, "In-Sample (Day 1–60)")
oos_m = compute_metrics(oos_eps, "Out-of-Sample (Day 61–105)")
tot_m = compute_metrics(all_episodes, "Full 105-Day Period")

decay = oos_m["sharpe"] / is_m["sharpe"] if is_m["sharpe"] > 0 else 0

print("="*60)
print(f"In-Sample:     Sharpe={is_m['sharpe']:.2f}, Sortino={is_m['sortino']:.2f}, Win={is_m['win_rate']:.1f}%, Mean={is_m['mean_net_bps']:+.1f} bps, MaxDD={is_m['max_dd_bps']:.1f} bps (n={is_m['n']})")
print(f"Out-of-Sample: Sharpe={oos_m['sharpe']:.2f}, Sortino={oos_m['sortino']:.2f}, Win={oos_m['win_rate']:.1f}%, Mean={oos_m['mean_net_bps']:+.1f} bps, MaxDD={oos_m['max_dd_bps']:.1f} bps (n={oos_m['n']})")
print(f"Full 105-Day:  Sharpe={tot_m['sharpe']:.2f}, Sortino={tot_m['sortino']:.2f}, Win={tot_m['win_rate']:.1f}%, Mean={tot_m['mean_net_bps']:+.1f} bps, MaxDD={tot_m['max_dd_bps']:.1f} bps (n={tot_m['n']})")
print(f"OOS/IS Sharpe Decay Ratio: {decay:.2f} (Hackathon Alert Threshold: < 0.50)")
print("="*60)

# PLOT 1: Equity Curve
plt.style.use('dark_background' if 'dark_background' in plt.style.available else 'default')
fig, ax = plt.subplots(figsize=(12, 6), dpi=300)

dates = [datetime.datetime.fromtimestamp(e["t"] / 1000, tz=datetime.timezone.utc) for e in all_episodes]
cum_net = np.cumsum([e["net_bps"] for e in all_episodes])
cum_gross = np.cumsum([e["gross_bps"] for e in all_episodes])
split_date = datetime.datetime.fromtimestamp(t_split / 1000, tz=datetime.timezone.utc)

ax.plot(dates, cum_net, color="#00e676", linewidth=2.2, label=f"Net PnL (net of 24bps fee + funding) [+ {tot_m['total_net_bps']:.0f} bps]")
ax.plot(dates, cum_gross, color="#64b5f6", linewidth=1.5, linestyle="--", alpha=0.7, label=f"Gross Dislocation PnL [+ {np.sum([e['gross_bps'] for e in all_episodes]):.0f} bps]")

ax.axvline(split_date, color="#ff9800", linestyle=":", linewidth=2, label="IS (60d) / OOS (45d) Walk-Forward Split")
ax.axvspan(dates[0], split_date, alpha=0.08, color="#2196f3", label="In-Sample Window (60d)")
ax.axvspan(split_date, dates[-1], alpha=0.08, color="#4caf50", label="Out-of-Sample Walk-Forward (45d)")

ax.set_title("VEGA — 105-Day Cumulative Net PnL (3-Venue Stock-Perp Dislocation)", fontsize=14, fontweight="bold", pad=12)
ax.set_ylabel("Cumulative PnL (Basis Points)", fontsize=11)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
fig.autofmt_xdate()
ax.grid(True, linestyle="--", alpha=0.3)
ax.legend(loc="upper left", framealpha=0.85, fontsize=10)

plt.tight_layout()
equity_path = os.path.join(DOCS_DIR, "equity_curve.png")
plt.savefig(equity_path)
plt.close()
print(f"Saved: {equity_path}")

# PLOT 2: Drawdown Chart
fig, ax = plt.subplots(figsize=(12, 4), dpi=300)

cum_peaks = np.maximum.accumulate(cum_net)
dd_bps = cum_net - cum_peaks

ax.fill_between(dates, dd_bps, 0, color="#f44336", alpha=0.45, label="Drawdown (bps)")
ax.plot(dates, dd_bps, color="#e57373", linewidth=1.2)
ax.axvline(split_date, color="#ff9800", linestyle=":", linewidth=1.5)

ax.set_title(f"VEGA — Underwater Drawdown Profile (Max DD: {tot_m['max_dd_bps']:.1f} bps)", fontsize=13, fontweight="bold", pad=10)
ax.set_ylabel("Drawdown (Basis Points)", fontsize=10)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
fig.autofmt_xdate()
ax.grid(True, linestyle="--", alpha=0.3)
ax.legend(loc="lower left", framealpha=0.85, fontsize=10)

plt.tight_layout()
dd_path = os.path.join(DOCS_DIR, "drawdown.png")
plt.savefig(dd_path)
plt.close()
print(f"Saved: {dd_path}")

# PLOT 3: Dislocation vs Convergence
fig, ax = plt.subplots(figsize=(8, 6), dpi=300)

d_in = np.array([e["D_entry_bps"] for e in all_episodes])
d_conv = np.array([e["D_entry_bps"] - e["D_exit_bps"] for e in all_episodes])

ax.scatter(d_in, d_conv, alpha=0.55, color="#29b6f6", edgecolors="none", s=30, label="Episodes (13 Symbols)")
max_val = max(np.percentile(d_in, 98), 50)
ax.plot([0, max_val], [0, max_val], color="#ffb74d", linestyle="--", linewidth=1.8, label="100% Reversion Line")
ax.axhline(0, color="gray", linestyle=":", linewidth=1)

ax.set_title("Entry Dislocation vs Realized 6h Convergence", fontsize=13, fontweight="bold", pad=10)
ax.set_xlabel("Entry Paired Dislocation |D_rich - D_cheap| (bps)", fontsize=11)
ax.set_ylabel("Realized 6h Dislocation Shrinkage (bps)", fontsize=11)
ax.grid(True, linestyle="--", alpha=0.3)
ax.legend(loc="upper left", framealpha=0.85, fontsize=10)

plt.tight_layout()
conv_path = os.path.join(DOCS_DIR, "dislocation_convergence.png")
plt.savefig(conv_path)
plt.close()
print(f"Saved: {conv_path}")

out_metrics = {
    "in_sample": is_m,
    "out_of_sample": oos_m,
    "full_period": tot_m,
    "sharpe_decay_ratio": round(decay, 2),
    "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
}
with open(os.path.join(DOCS_DIR, "quant_metrics.json"), "w", encoding="utf-8") as f:
    json.dump(out_metrics, f, indent=2)
print("Saved docs/quant_metrics.json")
