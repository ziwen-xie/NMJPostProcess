"""0824 dual-color showcase figure (journal style).

  a  two-colour contact FOV (GCaMP8s green / ChrimsonR red) + ROI overlay.
  b  ΔF/F traces of representative ROIs: no-light control | blue µLED | red µLED,
     with the stim windows BLANKED (both blue and red leak into the GFP channel).
  c  event counts per condition: kept (out-of-window) vs excluded (in-window leakage).

Result: after excluding the light-leakage windows there is NO out-of-window evoked
calcium for blue or red in this preparation — all detected activity is in-window
leakage. Ctrl2 (far-light) omitted (different stim pattern). Background = ROI.01;
ΔF/F baseline + detection exclude the windows. Windows 30-50/80-100/130-150/180-200 s.
Run:  python figures/make_0824_showcase.py
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import BatchProcess as bp                          # noqa: E402
import matplotlib                                  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                    # noqa: E402
import matplotlib.image as mpimg                   # noqa: E402
import matplotlib.patheffects as pe                # noqa: E402
from matplotlib.patches import Rectangle, Circle    # noqa: E402
from scipy.signal import find_peaks                # noqa: E402

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "svg.fonttype": "none", "pdf.fonttype": 42, "font.size": 12,
    "axes.linewidth": 1.1, "xtick.major.width": 1.1, "ytick.major.width": 1.1,
    "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": "white",
})
NAVY, CYAN, GREY, BLUE, RED = "#12365B", "#0E8C9B", "#8A8A8A", "#2C6FB5", "#C0392B"
DATA = ROOT / "data" / "raw" / "dual_color" / "0824"
IMG = ROOT / "figures" / "0824" / "assets" / "contact_0824.png"
BGROI, KP, KH = 1, 8.0, 6.0
WIN = [(30, 50), (80, 100), (130, 150), (180, 200)]
REP_ROIS = [5, 13, 20]
COND = [("Control", ["Ctrl.csv"], GREY, "#EDEDED"),
        ("Blue µLED", ["blue1.csv", "blue2.csv", "blue3.csv"], BLUE, "#DCE8F5"),
        ("Red µLED", ["red1.csv", "red2.csv", "red3.csv"], RED, "#F6D9D4")]
PLET = dict(fontsize=19, fontweight="bold", va="top")


def roin(c): return int(re.search(r"ROI\.0*(\d+)", c).group(1))
def in_window(t): return np.array([any(s <= x <= e for s, e in WIN) for x in t], dtype=bool)


def prep(f):
    df = pd.read_csv(DATA / f, encoding="utf-16", skiprows=1)
    t = df["Axis [s]"].to_numpy(float); cols = [c for c in df.columns if "ROI" in c]
    bg = df[next(c for c in cols if roin(c) == BGROI)].to_numpy(float)
    mask = in_window(t); dd = {}
    for c in cols:
        if roin(c) == BGROI:
            continue
        raw = df[c].to_numpy(float); floor = 0.03 * abs(float(np.percentile(raw, 8)))
        dff, _ = bp.dff_percentile_window(raw - bg, t, 15.0, 8.0, denom_floor=floor, exclude_mask=mask)
        dd[roin(c)] = dff
    return dd, t


def detect(y, t):
    dt = float(np.median(np.diff(t))); keep = ~in_window(t)
    yk = y[keep] if keep.any() else y
    med = float(np.median(yk)); sig = max(med - float(np.percentile(yk, 16)), 1e-9)
    pk, _ = find_peaks(y, height=med + KH * sig, prominence=KP * sig, distance=max(1, int(4 / dt)), width=max(1, int(1 / dt)))
    ev = t[pk]; inw = in_window(ev)
    return ev[~inw], ev[inw]          # kept (out-of-window), excluded (in-window leakage)


def collect():
    kept = {}; excl = {}
    for name, files, *_ in COND:
        kept[name] = 0; excl[name] = 0
        for f in files:
            dd, t = prep(f)
            for n, y in dd.items():
                k, x = detect(y, t); kept[name] += len(k); excl[name] += len(x)
    return kept, excl


def panel_image(ax):
    ax.imshow(mpimg.imread(str(IMG)))
    coords = {int(k): tuple(v) for k, v in json.load(open(ROOT / "figures" / "_roi_png_0824.json")).items()}
    halo = [pe.withStroke(linewidth=2.2, foreground="black")]
    for n, (x, y) in coords.items():
        c = CYAN if n in REP_ROIS else "white"
        ax.add_patch(Circle((x, y), 18, fill=False, edgecolor=c, lw=2.4 if n in REP_ROIS else 1.1, zorder=3))
        if n in REP_ROIS:
            ax.text(x + 24, y - 24, f"{n:02d}", color=c, fontsize=12, fontweight="bold", zorder=4, path_effects=halo)
    ax.text(0.62, 0.975, "GCaMP8s", color="#39FF9E", transform=ax.transAxes, va="top", fontsize=13, fontweight="bold", path_effects=halo)
    ax.text(0.62, 0.905, "ChrimsonR", color="#FF7A7A", transform=ax.transAxes, va="top", fontsize=13, fontweight="bold", path_effects=halo)
    ax.set_xlim(0, 2048); ax.set_ylim(2048, 0); ax.axis("off")


def panel_traces(fig, sub):
    recs = [(prep(files[0]), name, colr, bandc) for name, files, colr, bandc in COND]
    T = recs[0][0][1][-1] + 0.5
    axes = [fig.add_subplot(sub[i]) for i in range(len(REP_ROIS))]
    for ax, rnum in zip(axes, REP_ROIS):
        m = 0.02
        for (dd, t), name, colr, bandc in recs:
            y = dd.get(rnum)
            if y is not None:
                yy = y[~in_window(t)]
                if yy.size: m = max(m, float(np.nanpercentile(yy, 99.7)))
        ymin, ytop = -0.2 * m, 1.3 * m
        for k, ((dd, t), name, colr, bandc) in enumerate(recs):
            off = k * T; y = dd.get(rnum, np.zeros_like(t))
            ax.add_patch(Rectangle((off, ymin), T, ytop - ymin, facecolor=bandc, edgecolor="none", zorder=0))
            if name != "Control":
                for (s, e) in WIN:
                    ax.add_patch(Rectangle((s + off, ymin), e - s, ytop - ymin, facecolor=colr, alpha=0.18, edgecolor="none", zorder=1))
            yp = np.clip(y, ymin, ytop).astype(float).copy()
            if name != "Control":
                yp[in_window(t)] = np.nan          # blank the excluded leakage windows
            ax.plot(t + off, yp, color=NAVY, lw=1.0, zorder=2)
            if k > 0: ax.axvline(off, color="#CCC", lw=0.9, ls="--", zorder=1)
            if rnum == REP_ROIS[0]:
                ax.text(off + T / 2, ytop, name, ha="center", va="bottom", fontsize=11, color=colr, fontweight="bold")
        ax.set_ylim(ymin, ytop); ax.set_xlim(0, len(recs) * T)
        ax.tick_params(labelsize=10); ax.set_ylabel("ΔF/F", fontsize=13)
        ax.text(0.006, 0.9, f"ROI {rnum:02d}", transform=ax.transAxes, va="top", fontsize=12, color=CYAN, fontweight="bold")
    for ax in axes[:-1]: ax.tick_params(labelbottom=False)
    axes[-1].set_xlabel("Time — control | blue µLED | red µLED (shaded = 20 s stim windows, blanked: leakage)", fontsize=12)


def panel_counts(ax, kept, excl):
    names = [c[0] for c in COND]; colrs = [c[2] for c in COND]
    x = np.arange(len(names)); w = 0.38
    ax.bar(x - w/2, [kept[n] for n in names], w, color=colrs, edgecolor="black", lw=1.0, label="kept (out-of-window)")
    ax.bar(x + w/2, [excl[n] for n in names], w, color=colrs, alpha=0.35, edgecolor="black", lw=1.0, hatch="//", label="excluded (in-window leakage)")
    for xi, n in zip(x, names):
        ax.text(xi - w/2, kept[n], str(kept[n]), ha="center", va="bottom", fontsize=11, fontweight="bold")
        ax.text(xi + w/2, excl[n], str(excl[n]), ha="center", va="bottom", fontsize=10, color="#555")
    ax.set_xticks(x); ax.set_xticklabels(names, fontsize=13)
    ax.set_ylabel("Event count", fontsize=13); ax.tick_params(axis="y", labelsize=10); ax.tick_params(axis="x", length=0)
    ax.legend(fontsize=9.5, frameon=False, loc="upper left")
    ax.set_title("No out-of-window response; all activity is in-window leakage", fontsize=11.5, fontweight="bold")


def main():
    kept, excl = collect()
    fig = plt.figure(figsize=(14, 8.2), dpi=300)
    gs = fig.add_gridspec(2, 2, width_ratios=[1.0, 1.5], height_ratios=[1.05, 0.95],
                          hspace=0.5, wspace=0.24, left=0.055, right=0.99, top=0.9, bottom=0.12)
    panel_image(fig.add_subplot(gs[0, 0]))
    panel_counts(fig.add_subplot(gs[1, 0]), kept, excl)
    panel_traces(fig, gs[:, 1].subgridspec(len(REP_ROIS), 1, hspace=0.2))
    fig.text(0.012, 0.95, "a", **PLET); fig.text(0.4, 0.95, "b", **PLET); fig.text(0.012, 0.45, "c", **PLET)
    fig.text(0.99, 0.95, "Dual-color · 462/625 nm · 4 mW/mm²", ha="right", va="top", fontsize=13, color="#333")
    base = ROOT / "figures" / "0824" / "fig_0824_showcase"
    for ext, kw in [(".svg", {}), (".png", {"dpi": 300})]:
        try: fig.savefig(base.with_suffix(ext), facecolor="white", **kw)
        except PermissionError: print("locked", ext)
    plt.close(fig)
    print("kept:", kept, "| excluded(in-window):", excl)
    print("wrote", base.with_suffix(".png"))


if __name__ == "__main__":
    main()
