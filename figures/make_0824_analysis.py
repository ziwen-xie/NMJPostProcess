"""0824 dual-color ANALYSIS/QC figure: every cell ROI x every experiment.

Rows = cell ROIs 02-46 (ROI.01 = background, subtracted). Columns concatenate 7
recordings: Ctrl (no-light) | blue1-3 | red1-3. Ctrl2 (far-light control) is
EXCLUDED - it uses a different stimulation pattern. The stim windows are excluded
throughout: blanked in the traces, excluded from the moving baseline, from the
per-ROI y-limit, and from event detection (in-window = light leakage, untrustworthy).

Result: with the stim windows removed there are NO kept out-of-window events for
blue or red - all detected activity is in-window (blue = leakage; red's ~14 events
are all in-window). ΔF/F: ROI.01-corrected baseline, floored. Detection: prominence
kp=8/kh=6. Windows 30-50/80-100/130-150/180-200 s.
Run:  python figures/make_0824_analysis.py  -> figures/0824/fig_0824_all_roi.*
"""
from __future__ import annotations
import re, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import BatchProcess as bp                          # noqa: E402
import matplotlib                                  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                    # noqa: E402
from matplotlib.patches import Rectangle           # noqa: E402
from scipy.signal import find_peaks                # noqa: E402

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "svg.fonttype": "none", "pdf.fonttype": 42, "font.size": 8,
    "axes.linewidth": 0.7, "axes.spines.top": False, "axes.spines.right": False,
    "figure.facecolor": "white",
})
NAVY, GREY, BLUE, RED = "#12365B", "#8A8A8A", "#2C6FB5", "#C0392B"
DATA = ROOT / "data" / "raw" / "dual_color" / "0824"
BGROI = 1
WIN = [(30, 50), (80, 100), (130, 150), (180, 200)]
KP, KH = 8.0, 6.0
ORDER = [("Ctrl.csv", "Ctrl", GREY, "#EDEDED", False),
         ("blue1.csv", "blue 1", BLUE, "#DCE8F5", True),
         ("blue2.csv", "blue 2", BLUE, "#DCE8F5", True),
         ("blue3.csv", "blue 3", BLUE, "#DCE8F5", True),
         ("red1.csv", "red 1", RED, "#F6D9D4", False),
         ("red2.csv", "red 2", RED, "#F6D9D4", False),
         ("red3.csv", "red 3", RED, "#F6D9D4", False)]
CELL_ROIS = list(range(2, 47))


def roin(c): return int(re.search(r"ROI\.0*(\d+)", c).group(1))


def in_window(t):
    return np.array([any(s <= x <= e for s, e in WIN) for x in t], dtype=bool)


def prep(f):
    df = pd.read_csv(DATA / f, encoding="utf-16", skiprows=1)
    t = df["Axis [s]"].to_numpy(float)
    cols = [c for c in df.columns if "ROI" in c]
    bg = df[next(c for c in cols if roin(c) == BGROI)].to_numpy(float)
    mask = in_window(t)          # keep in-window light leakage OUT of the baseline
    dd = {}
    for c in cols:
        if roin(c) == BGROI:
            continue
        raw = df[c].to_numpy(float); floor = 0.03 * abs(float(np.percentile(raw, 8)))
        dff, _ = bp.dff_percentile_window(raw - bg, t, 15.0, 8.0, denom_floor=floor, exclude_mask=mask)
        dd[roin(c)] = dff
    return dd, t


def detect(y, t, is_blue):
    dt = float(np.median(np.diff(t)))
    keep = ~in_window(t)         # estimate noise/threshold from OUT-of-window points only
    yk = y[keep] if keep.any() else y
    med = float(np.median(yk)); sig = max(med - float(np.percentile(yk, 16)), 1e-9)
    pk, _ = find_peaks(y, height=med + KH * sig, prominence=KP * sig, distance=max(1, int(4 / dt)), width=max(1, int(1 / dt)))
    ev = t[pk]
    excluded_mask = in_window(ev)
    kept_mask = ~excluded_mask
    return ev[kept_mask], pk[kept_mask], ev[excluded_mask], pk[excluded_mask]


def main():
    recs = [(prep(f), f, name, colr, bandc, is_blue) for f, name, colr, bandc, is_blue in ORDER]
    T = recs[0][0][1][-1] + 0.5
    n = len(CELL_ROIS)
    fig, axes = plt.subplots(n, 1, figsize=(24, 0.4 * n + 0.8), sharex=True)
    summary = {
        name: {
            "file": f,
            "events_kept": 0,
            "events_in_stim_kept": 0,
            "events_outside_stim_kept": 0,
            "stim_window_events_excluded": 0,
            "active_rois": set(),
        }
        for f, name, *_ in ORDER
    }
    event_rows = []
    for ax, rnum in zip(axes, CELL_ROIS):
        m = 0.02
        for (dd, t), f, name, colr, bandc, is_blue in recs:
            y = dd.get(rnum)
            if y is None:
                continue
            yy = y[~in_window(t)]
            if yy.size:
                m = max(m, float(np.nanpercentile(yy, 99.8)))
        ymin, ytop = -0.15 * m, 1.25 * m
        for k, ((dd, t), f, name, colr, bandc, is_blue) in enumerate(recs):
            off = k * T; y = dd.get(rnum, np.zeros_like(t))
            ax.add_patch(Rectangle((off, ymin), T, ytop - ymin, facecolor=bandc, edgecolor="none", zorder=0))
            if name != "Ctrl":      # shade stim windows for blue/red (not the no-light Ctrl)
                for (s, e) in WIN:
                    ax.add_patch(Rectangle((s + off, ymin), e - s, ytop - ymin, facecolor=colr, alpha=0.16, edgecolor="none", zorder=1))
            yp = np.clip(y, ymin, ytop).astype(float).copy()
            if name != "Ctrl":
                yp[in_window(t)] = np.nan        # blank the excluded stim windows (not drawn)
            ax.plot(t + off, yp, color=NAVY, lw=0.55, zorder=2)
            ev, pk, excluded_ev, excluded_pk = detect(y, t, is_blue)
            stim_mask = in_window(ev)
            summary[name]["events_kept"] += int(len(ev))
            summary[name]["events_in_stim_kept"] += int(stim_mask.sum())
            summary[name]["events_outside_stim_kept"] += int((~stim_mask).sum())
            summary[name]["stim_window_events_excluded"] += int(len(excluded_ev))
            if len(ev):
                summary[name]["active_rois"].add(rnum)
            for e2, p2 in zip(ev, pk):
                event_rows.append({
                    "recording": name,
                    "file": f,
                    "roi": rnum,
                    "time_s": float(e2),
                    "in_analysis_window": bool(any(s <= e2 <= e for s, e in WIN)),
                    "dff": float(y[p2]),
                    "kept": True,
                    "exclusion_reason": "",
                })
            for e2, p2 in zip(excluded_ev, excluded_pk):
                event_rows.append({
                    "recording": name,
                    "file": f,
                    "roi": rnum,
                    "time_s": float(e2),
                    "in_analysis_window": bool(any(s <= e2 <= e for s, e in WIN)),
                    "dff": float(y[p2]),
                    "kept": False,
                    "exclusion_reason": "stim_window",
                })
            ey = [float(np.clip(y[p2], ymin, ytop)) for p2 in pk]
            ax.scatter(np.asarray(ev) + off, ey, s=11, facecolor="white", edgecolor="black", linewidths=0.6, zorder=3)
            if k > 0:
                ax.axvline(off, color="#CCC", lw=0.5, ls="--", zorder=1)
        ax.set_ylim(ymin, ytop); ax.set_xlim(0, len(recs) * T)
        ax.set_yticks([0]); ax.tick_params(labelsize=6)
        ax.set_ylabel(f"{rnum:02d}", fontsize=7.5, rotation=0, ha="right", va="center", labelpad=6)
        if rnum != CELL_ROIS[-1]:
            ax.tick_params(labelbottom=False)
    for k, (_, _f, name, colr, *_ ) in enumerate(recs):
        axes[0].text((k + 0.5) * T, axes[0].get_ylim()[1], name, ha="center", va="bottom",
                     fontsize=8.5, color=colr, fontweight="bold")
    axes[-1].set_xlabel("Time (s) - Ctrl | blue uLED x3 | red uLED x3   "
                        "(shaded = excluded stim windows, blanked; open circles = kept outside-window events)",
                        fontsize=10)
    counts = "; ".join(f"{name}={summary[name]['events_kept']}" for _, name, *_ in ORDER)
    fig.suptitle("0824 dual-color - dF/F of every cell ROI (02-46; ROI.01 = background), "
                 f"baseline excludes in-window light leakage. Kept events: {counts}",
                 y=0.998, fontsize=11.5, fontweight="bold")
    fig.text(0.004, 0.5, "ROI", rotation=90, va="center", fontsize=10, fontweight="bold")
    fig.tight_layout(rect=(0.011, 0, 1, 0.99))
    outdir = ROOT / "figures" / "0824"
    outdir.mkdir(parents=True, exist_ok=True)
    rows = []
    for f, name, *_ in ORDER:
        vals = summary[name]
        rows.append({
            "recording": name,
            "file": f,
            "events_kept": vals["events_kept"],
            "events_in_analysis_window_kept": vals["events_in_stim_kept"],
            "events_outside_analysis_window_kept": vals["events_outside_stim_kept"],
            "stim_window_events_excluded": vals["stim_window_events_excluded"],
            "active_rois": len(vals["active_rois"]),
        })
    pd.DataFrame(rows).to_csv(outdir / "0824_recording_summary.csv", index=False)
    pd.DataFrame(event_rows).to_csv(outdir / "0824_event_table.csv", index=False)
    base = outdir / "fig_0824_all_roi"
    for ext, kw in [(".svg", {}), (".png", {"dpi": 170})]:
        try: fig.savefig(base.with_suffix(ext), facecolor="white", **kw)
        except PermissionError: print("locked", ext)
    plt.close(fig)
    print("wrote", base.with_suffix(".png"))


if __name__ == "__main__":
    main()
