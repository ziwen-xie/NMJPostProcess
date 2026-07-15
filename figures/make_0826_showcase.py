"""0826 dual-color data-showcase figure (journal style).

  a  two-colour contact FOV (GCaMP8s green / ChrimsonR red) + ROI overlay + µLED.
  b  ΔF/F traces of representative responders: no-light control | blue-µLED | red-µLED.
  c/d/e  event count / amplitude / latency for Control vs Blue vs Red µLED.

Dual-color: PC12 express ChR2 (blue-activated), C2C12 express ChrimsonR + GCaMP8s.
Blue (462 nm) leaks into the GFP channel, so blue in-window events are excluded;
red (625 nm) does not leak. 4 stim windows (30-50/80-100/130-150/180-200 s, 2 Hz).
ΔF/F on raw ROI signal (all 20 ROIs are cells; no cell-free background). Detection:
prominence threshold tuned so the no-light control is silent (kp=6, kh=5).
Run:  python figures/make_0826_showcase.py
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
from scipy import stats as sps                     # noqa: E402

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "svg.fonttype": "none", "pdf.fonttype": 42, "font.size": 12,
    "axes.linewidth": 1.1, "xtick.major.width": 1.1, "ytick.major.width": 1.1,
    "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": "white",
})
NAVY, CYAN = "#12365B", "#0E8C9B"
BLUE, RED, GREY = "#2C6FB5", "#C0392B", "#8A8A8A"
DATA = ROOT / "data" / "raw" / "dual_color" / "0826"   # images/roi are in figures/0826/assets
IMG = ROOT / "figures" / "0826" / "assets" / "contact_0826.png"
WIN = [(30, 50), (80, 100), (130, 150), (180, 200)]
KP, KH, LATCAP = 6.0, 5.0, 60.0
REP_ROIS = [5, 6, 13]
COND = [("Control", ["Ctrl.csv"], GREY, "#EDEDED"),
        ("Blue µLED", ["blue1.csv", "blue2.csv", "blue3.csv"], BLUE, "#DCE8F5"),
        ("Red µLED", ["red1.csv", "red2.csv", "red3.csv"], RED, "#F6D9D4")]
PLET = dict(fontsize=19, fontweight="bold", va="top")


def roin(c): return int(re.search(r"ROI\.0*(\d+)", c).group(1))


def prep(f):
    df = pd.read_csv(DATA / f, encoding="utf-16", skiprows=1)
    t = df["Axis [s]"].to_numpy(float); cols = [c for c in df.columns if "ROI" in c]; dd = {}
    mask = np.array([any(s <= x <= e for s, e in WIN) for x in t])   # exclude leakage from baseline
    for c in cols:
        dff, _ = bp.dff_percentile_window(df[c].to_numpy(float), t, 15.0, 8.0, exclude_mask=mask)
        dd[c] = dff
    return pd.DataFrame(dd), cols, t


def detect(tab, cols, t, is_blue):
    dt = float(np.median(np.diff(t))); out = {}
    keep = ~np.array([any(s <= x <= e for s, e in WIN) for x in t])   # noise from out-of-window
    for c in cols:
        y = tab[c].to_numpy(); yk = y[keep] if keep.any() else y
        med = float(np.median(yk)); sig = max(med - float(np.percentile(yk, 16)), 1e-9)
        pk, _ = find_peaks(y, height=med + KH * sig, prominence=KP * sig, distance=max(1, int(4 / dt)), width=max(1, int(1 / dt)))
        ev = t[pk]
        if is_blue:
            ev = ev[[not any(s <= x <= e for s, e in WIN) for x in ev]]
        out[roin(c)] = ev
    return out


def col_for(cols, n): return next((c for c in cols if roin(c) == n), None)


def latency(ev):
    starts = [s for s, _ in WIN]; out = []
    for x in ev:
        prev = [s for s in starts if s <= x]
        if prev:
            L = x - max(prev)
            if 0 <= L <= LATCAP: out.append(L)
    return out


def collect():
    counts = {}; amps = {}; lats = {}
    for name, files, *_ in COND:
        counts[name] = []; amps[name] = []; lats[name] = []
        for f in files:
            tab, cols, t = prep(f); sp = detect(tab, cols, t, name == "Blue µLED")
            for n, ev in sp.items():
                counts[name].append(len(ev))
                y = tab[col_for(cols, n)].to_numpy()
                for x in ev: amps[name].append(float(y[np.argmin(np.abs(t - x))]))
                lats[name].extend(latency(ev))
    return counts, amps, lats


def panel_image(ax):
    ax.imshow(mpimg.imread(str(IMG)))
    coords = {int(k): tuple(v) for k, v in json.load(open(ROOT / "figures" / "_roi_png_0826.json")).items()}
    halo = [pe.withStroke(linewidth=2.4, foreground="black")]
    for n, (x, y) in coords.items():
        c = CYAN if n in REP_ROIS else "white"
        ax.add_patch(Circle((x, y), 22, fill=False, edgecolor=c, lw=2.6 if n in REP_ROIS else 1.4, zorder=3))
        if n in REP_ROIS:
            ax.text(x + 26, y - 26, f"{n:02d}", color=c, fontsize=12, fontweight="bold", zorder=4, path_effects=halo)
    ax.text(0.03, 0.975, "GCaMP8s", color="#39FF9E", transform=ax.transAxes, va="top", fontsize=13,
            fontweight="bold", path_effects=halo)
    ax.text(0.03, 0.905, "ChrimsonR", color="#FF7A7A", transform=ax.transAxes, va="top", fontsize=13,
            fontweight="bold", path_effects=halo)
    ax.set_xlim(0, 2048); ax.set_ylim(2048, 0); ax.axis("off")


def panel_traces(fig, sub):
    recs = [(prep(files[0]), name, colr, bandc, name == "Blue µLED")
            for name, files, colr, bandc in COND]
    T = recs[0][0][2][-1] + 0.5
    axes = [fig.add_subplot(sub[i]) for i in range(len(REP_ROIS))]
    for ax, rnum in zip(axes, REP_ROIS):
        m = 0.05
        for (tab, cols, t), name, colr, bandc, is_blue in recs:
            if is_blue:      # blue leakage saturates GFP; exclude from scaling
                continue
            col = col_for(cols, rnum)
            if col: m = max(m, float(np.nanmax(tab[col].to_numpy())))
        ymin, ytop = -0.15 * m, 1.30 * m       # red responses in view; blue leakage clips
        for k, ((tab, cols, t), name, colr, bandc, is_blue) in enumerate(recs):
            off = k * T; col = col_for(cols, rnum); y = tab[col].to_numpy()
            ax.add_patch(Rectangle((off, ymin), T, ytop - ymin, facecolor=bandc, edgecolor="none", zorder=0))
            if name != "Control":
                for (s, e) in WIN:
                    ax.add_patch(Rectangle((s + off, ymin), e - s, ytop - ymin, facecolor=colr, alpha=0.18, edgecolor="none", zorder=1))
            ax.plot(t + off, np.clip(y, ymin, ytop), color=NAVY, lw=1.0, zorder=2)
            sp = detect(tab, cols, t, is_blue); ev = sp.get(rnum, [])
            ey = [float(np.clip(y[np.argmin(np.abs(t - e2))], ymin, ytop)) for e2 in ev]
            ax.scatter(np.asarray(ev) + off, ey, s=40, facecolor="white", edgecolor="black", linewidths=1.0, zorder=3)
            if k > 0: ax.axvline(off, color="#CCC", lw=0.9, ls="--", zorder=1)
            if rnum == REP_ROIS[0]:
                ax.text(off + T / 2, ytop, name, ha="center", va="bottom", fontsize=11, color=colr, fontweight="bold")
        ax.set_ylim(ymin, ytop); ax.set_xlim(0, len(recs) * T)
        ax.tick_params(labelsize=10); ax.set_ylabel("ΔF/F", fontsize=13)
        ax.text(0.006, 0.9, f"ROI {rnum:02d}", transform=ax.transAxes, va="top", fontsize=12, color=CYAN, fontweight="bold")
    for ax in axes[:-1]: ax.tick_params(labelbottom=False)
    axes[-1].set_xlabel("Time — no-light control | blue µLED | red µLED (shaded = 20 s stim windows)", fontsize=12)


def metric_panel(ax, data, ylabel, title, total=False):
    names = [c[0] for c in COND]; colrs = [c[2] for c in COND]
    xs = range(len(names))
    for x, nm, cr in zip(xs, names, colrs):
        a = np.asarray(data[nm], float)
        v = a.sum() if total else (a.mean() if a.size else 0)
        if a.size == 0 and not total:
            ax.bar(x, 0, 0.62, facecolor="none", edgecolor=cr, hatch="///", lw=0.9)
            ax.text(x, 0, "n=0", ha="center", va="bottom", fontsize=8, color="#888"); continue
        s = 0 if total else (sps.sem(a) if a.size > 1 else 0)
        ax.bar(x, v, 0.62, color=cr, alpha=0.85, edgecolor="black", lw=1.0,
               yerr=s if s else None, capsize=4, error_kw=dict(lw=1.0))
    if total:  # significance red vs control
        red = np.asarray(data["Red µLED"], float); ctl = np.asarray(data["Control"], float)
        try:
            p = sps.mannwhitneyu(red, ctl, alternative="greater").pvalue
            top = max(red.sum(), 1); star = "***" if p < 1e-3 else "**" if p < 1e-2 else "*" if p < 5e-2 else "ns"
            ax.plot([0, 0, 2, 2], [top*1.03, top*1.07, top*1.07, top*1.03], lw=1.3, c="#222")
            ax.text(1.0, top*1.075, star, ha="center", va="bottom", fontsize=20, fontweight="bold")
            ax.set_ylim(0, top*1.28)
        except ValueError: pass
    ax.set_xticks(list(xs)); ax.set_xticklabels(names, fontsize=11.5)
    ax.set_ylabel(ylabel, fontsize=13); ax.set_title(title, fontsize=12.5, fontweight="bold")
    ax.tick_params(axis="y", labelsize=10); ax.tick_params(axis="x", length=0)


def main():
    counts, amps, lats = collect()
    fig = plt.figure(figsize=(14.5, 8.4), dpi=300)
    gs = fig.add_gridspec(2, 3, height_ratios=[1.05, 0.95], hspace=0.55, wspace=0.3,
                          left=0.055, right=0.99, top=0.9, bottom=0.13)
    panel_image(fig.add_subplot(gs[0, 0]))
    panel_traces(fig, gs[0, 1:].subgridspec(len(REP_ROIS), 1, hspace=0.2))
    metric_panel(fig.add_subplot(gs[1, 0]), counts, "Total events", "Event count", total=True)
    metric_panel(fig.add_subplot(gs[1, 1]), amps, "Amplitude (ΔF/F)", "Event amplitude")
    metric_panel(fig.add_subplot(gs[1, 2]), lats, "Latency (s)", "Latency from onset")
    fig.text(0.012, 0.95, "a", **PLET); fig.text(0.34, 0.95, "b", **PLET)
    fig.text(0.012, 0.45, "c", **PLET); fig.text(0.365, 0.45, "d", **PLET); fig.text(0.68, 0.45, "e", **PLET)
    base = ROOT / "figures" / "0826" / "fig_0826_showcase"
    for ext, kw in [(".svg", {}), (".png", {"dpi": 300})]:
        try: fig.savefig(base.with_suffix(ext), facecolor="white", **kw)
        except PermissionError: print("locked", ext)
    plt.close(fig)
    print("totals:", {k: int(np.sum(v)) for k, v in counts.items()})
    print("wrote", base.with_suffix(".png"))


if __name__ == "__main__":
    main()
