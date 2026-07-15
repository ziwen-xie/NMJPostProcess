"""0824 dual-color ANALYSIS/QC figure: every cell ROI x every experiment.

Rows = cell ROIs 02-46 (ROI.01 = background, subtracted). Columns concatenate the
8 recordings: Ctrl | Ctrl2 | blue1-3 | red1-3. Stim windows shaded (blue/red tint).
Detected events circled; blue in-window events excluded (462 nm GFP leakage).
Per-ROI y-limit excludes blue in-window leakage so real responses set the scale.

NOTE: 0824's no-light control is NOT silent (~150 spontaneous events even at high
threshold) - a spontaneously-active preparation. ΔF/F: ROI.01-corrected baseline,
floored. Detection: prominence kp=8/kh=6. Windows 30-50/80-100/130-150/180-200 s.
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
         ("Ctrl2.csv", "Ctrl2", GREY, "#EDEDED", True),   # light control: stim-window leakage
         ("blue1.csv", "blue 1", BLUE, "#DCE8F5", True),
         ("blue2.csv", "blue 2", BLUE, "#DCE8F5", True),
         ("blue3.csv", "blue 3", BLUE, "#DCE8F5", True),
         ("red1.csv", "red 1", RED, "#F6D9D4", False),
         ("red2.csv", "red 2", RED, "#F6D9D4", False),
         ("red3.csv", "red 3", RED, "#F6D9D4", False)]
CELL_ROIS = list(range(2, 47))


def roin(c): return int(re.search(r"ROI\.0*(\d+)", c).group(1))


def prep(f):
    df = pd.read_csv(DATA / f, encoding="utf-16", skiprows=1)
    t = df["Axis [s]"].to_numpy(float)
    cols = [c for c in df.columns if "ROI" in c]
    bg = df[next(c for c in cols if roin(c) == BGROI)].to_numpy(float)
    dd = {}
    for c in cols:
        if roin(c) == BGROI:
            continue
        raw = df[c].to_numpy(float); floor = 0.03 * abs(float(np.percentile(raw, 8)))
        dff, _ = bp.dff_percentile_window(raw - bg, t, 15.0, 8.0, denom_floor=floor)
        dd[roin(c)] = dff
    return dd, t


def detect(y, t, is_blue):
    dt = float(np.median(np.diff(t))); med = float(np.median(y)); sig = max(med - float(np.percentile(y, 16)), 1e-9)
    pk, _ = find_peaks(y, height=med + KH * sig, prominence=KP * sig, distance=max(1, int(4 / dt)), width=max(1, int(1 / dt)))
    ev = t[pk]
    if is_blue:
        ev = ev[[not any(s <= x <= e for s, e in WIN) for x in ev]]
    return ev


def in_window(t):
    return np.array([any(s <= x <= e for s, e in WIN) for x in t])


def main():
    recs = [(prep(f), name, colr, bandc, is_blue) for f, name, colr, bandc, is_blue in ORDER]
    T = recs[0][0][1][-1] + 0.5
    n = len(CELL_ROIS)
    fig, axes = plt.subplots(n, 1, figsize=(24, 0.4 * n + 0.8), sharex=True)
    for ax, rnum in zip(axes, CELL_ROIS):
        m = 0.02
        for (dd, t), name, colr, bandc, is_blue in recs:
            y = dd.get(rnum)
            if y is None:
                continue
            yy = y[~in_window(t)] if is_blue else y
            if yy.size:
                m = max(m, float(np.nanpercentile(yy, 99.8)))
        ymin, ytop = -0.15 * m, 1.25 * m
        for k, ((dd, t), name, colr, bandc, is_blue) in enumerate(recs):
            off = k * T; y = dd.get(rnum, np.zeros_like(t))
            ax.add_patch(Rectangle((off, ymin), T, ytop - ymin, facecolor=bandc, edgecolor="none", zorder=0))
            if name != "Ctrl":      # shade stim windows for Ctrl2/blue/red (not the no-light Ctrl)
                for (s, e) in WIN:
                    ax.add_patch(Rectangle((s + off, ymin), e - s, ytop - ymin, facecolor=colr, alpha=0.16, edgecolor="none", zorder=1))
            ax.plot(t + off, np.clip(y, ymin, ytop), color=NAVY, lw=0.55, zorder=2)
            ev = detect(y, t, is_blue)
            ey = [float(np.clip(y[np.argmin(np.abs(t - e2))], ymin, ytop)) for e2 in ev]
            ax.scatter(np.asarray(ev) + off, ey, s=11, facecolor="white", edgecolor="black", linewidths=0.6, zorder=3)
            if k > 0:
                ax.axvline(off, color="#CCC", lw=0.5, ls="--", zorder=1)
        ax.set_ylim(ymin, ytop); ax.set_xlim(0, len(recs) * T)
        ax.set_yticks([0]); ax.tick_params(labelsize=6)
        ax.set_ylabel(f"{rnum:02d}", fontsize=7.5, rotation=0, ha="right", va="center", labelpad=6)
        if rnum != CELL_ROIS[-1]:
            ax.tick_params(labelbottom=False)
    for k, (_, name, colr, *_ ) in enumerate(recs):
        axes[0].text((k + 0.5) * T, axes[0].get_ylim()[1], name, ha="center", va="bottom",
                     fontsize=8.5, color=colr, fontweight="bold")
    axes[-1].set_xlabel("Time (s) — Ctrl | Ctrl2 | blue µLED ×3 | red µLED ×3   (shaded = 20 s stim windows; "
                        "○ = detected event; blue in-window leakage excluded)", fontsize=10)
    fig.suptitle("0824 dual-color — ΔF/F of every cell ROI (02–46; ROI.01 = background).  "
                 "Ctrl = no-light (silent, 0 ev); Ctrl2 = light control (57); blue = 171; red = 12 out-of-window events",
                 y=0.998, fontsize=12, fontweight="bold")
    fig.text(0.004, 0.5, "ROI", rotation=90, va="center", fontsize=10, fontweight="bold")
    fig.tight_layout(rect=(0.011, 0, 1, 0.99))
    base = ROOT / "figures" / "0824" / "fig_0824_all_roi"
    for ext, kw in [(".svg", {}), (".png", {"dpi": 170})]:
        try: fig.savefig(base.with_suffix(ext), facecolor="white", **kw)
        except PermissionError: print("locked", ext)
    plt.close(fig)
    print("wrote", base.with_suffix(".png"))


if __name__ == "__main__":
    main()
