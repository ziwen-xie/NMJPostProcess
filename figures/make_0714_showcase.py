"""0714 academic data-showcase figure (journal style) for the MEMS abstract.

  a  two-colour fluorescence at the array-cell contact (GCaMP8s green / ChrimsonR
     red) with the stimulating µLED pixel and ROI overlay (real ROI.roi coords).
  b  ΔF/F traces: on-pixel light-leakage ROI (02, peach panel) kept separate from
     biological Ca2+ responders (10/12/14, common ΔF/F scale). C = no-light
     control; 1-6 = successive red-µLED stim recordings; orange bands = 10 s stim.
  c  event rate per ROI, no-light control vs red-µLED stim (bar, Mann-Whitney).

Stim: 625 nm red µLED, 4 mW/mm2, three 10 s windows (30-40/70-80/110-120 s).
Design: 14 ROIs from ONE co-culture prep / FOV; 6 repeated stim recordings.

Run:  python figures/make_0714_showcase.py  -> figures/0714/fig_0714_showcase.*
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import figures.make_0714_figures as F        # noqa: E402
import matplotlib                              # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                # noqa: E402
import matplotlib.image as mpimg               # noqa: E402
import matplotlib.patheffects as pe            # noqa: E402
from matplotlib.patches import Rectangle, Circle  # noqa: E402
from scipy import stats as sps                 # noqa: E402

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "svg.fonttype": "none", "pdf.fonttype": 42, "font.size": 13,
    "axes.linewidth": 1.2, "xtick.major.width": 1.2, "ytick.major.width": 1.2,
    "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": "white",
})
NAVY, STIM, GREY, BAND = "#12365B", "#D55E00", "#8A8A8A", "#F4C39C"
CYAN, LEAKC = "#0E8C9B", "#E8871E"
ASSETS = ROOT / "figures" / "0714" / "assets"
STIM_TXT = "Red µLED · 625 nm · 4 mW/mm² · 10 s"
BIO_ROIS = [10, 12, 14]
PLET = dict(fontsize=19, fontweight="bold", va="top")


def _stretch(g, lo=2, hi=99.6):
    a, b = np.percentile(g, lo), np.percentile(g, hi)
    return np.clip((g - a) / (b - a + 1e-9), 0, 1)


def panel_image(ax):
    g = np.array(mpimg.imread(str(ASSETS / "contact_ch470_full.png")))
    r = np.array(mpimg.imread(str(ASSETS / "contact_ch580.png")))
    g = g[..., 0] if g.ndim == 3 else g
    r = r[..., 0] if r.ndim == 3 else r
    ax.imshow(np.dstack([_stretch(r), _stretch(g), np.zeros_like(g, float)]))
    coords = {int(k): tuple(v) for k, v in json.load(open(ROOT / "figures" / "_roi_png_0714.json")).items()}
    px = ((coords[2][0] + coords[3][0]) / 2, (coords[2][1] + coords[3][1]) / 2)
    cxm = np.mean([v[0] for k, v in coords.items() if k != 1])
    cym = np.mean([v[1] for k, v in coords.items() if k != 1])
    for n, (x, y) in coords.items():
        if n == 1:
            continue
        col = LEAKC if n in (2, 3) else (CYAN if n in BIO_ROIS else "white")
        key = n in (2, 3) or n in BIO_ROIS
        ax.add_patch(Circle((x, y), 30, fill=False, edgecolor=col, lw=3.4 if key else 1.8, zorder=3))
        ang = np.arctan2(y - cym, x - cxm)
        ax.text(x + 74 * np.cos(ang), y + 74 * np.sin(ang), f"{n:02d}", color=col, fontsize=16,
                fontweight="bold", ha="center", va="center", zorder=4,
                path_effects=[pe.withStroke(linewidth=3.6, foreground="black")])
    ax.add_patch(Rectangle((px[0] - 44, px[1] - 44), 88, 88, fill=False, edgecolor="red", lw=3.6, zorder=5))
    ax.text(px[0], px[1] - 104, "µLED", color="red", fontsize=15, fontweight="bold",
            ha="center", va="bottom", zorder=5, path_effects=[pe.withStroke(linewidth=3.4, foreground="black")])
    ax.text(0.03, 0.985, "GCaMP8s", color="#39FF9E", transform=ax.transAxes, va="top",
            fontsize=15, fontweight="bold", path_effects=[pe.withStroke(linewidth=2.6, foreground="black")])
    ax.text(0.03, 0.905, "ChrimsonR", color="#FF7A7A", transform=ax.transAxes, va="top",
            fontsize=15, fontweight="bold", path_effects=[pe.withStroke(linewidth=2.6, foreground="black")])
    ax.set_xlim(0, 2048); ax.set_ylim(2048, 0); ax.axis("off")


def _recs():
    recs = []
    ctab, cdet = F.prep(F.CTRL_FILE)
    recs.append((ctab, cdet, F.detect(ctab, cdet, []), []))
    for f in F.STIM_FILES:
        tab, det = F.prep(f)
        recs.append((tab, det, F.detect(tab, det, F.WINDOWS), F.WINDOWS))
    return recs


def _draw_trace(ax, recs, rnum, ylim, T, mark=True):
    ymin, ytop = ylim
    for k, (tab, det, sp, wins) in enumerate(recs):
        off = k * T
        t = tab["Time (s)"].to_numpy() + off
        col = F.col_for(det, rnum); y = tab[col].to_numpy()
        for (s, e) in wins:
            ax.add_patch(Rectangle((s + off, ymin), e - s, ytop - ymin, facecolor=BAND,
                         edgecolor="none", zorder=0))
        if not wins:
            ax.add_patch(Rectangle((off, ymin), T, ytop - ymin, facecolor="#EEEEEE",
                         edgecolor="none", zorder=0))
        ax.plot(t, np.clip(y, ymin, ytop), color=NAVY, lw=1.15, zorder=2)
        if mark and len(sp.get(col, [])):
            ev = sp[col]
            ey = [float(np.clip(y[np.argmin(np.abs(t - (e2 + off)))], ymin, ytop)) for e2 in ev]
            ax.scatter(np.asarray(ev) + off, ey, s=48, facecolor="white", edgecolor="black",
                       linewidths=1.2, zorder=3)
        if k > 0:
            ax.axvline(off, color="#D2D2D2", lw=0.8, ls="--", zorder=1)
    ax.set_ylim(ymin, ytop); ax.set_xlim(0, len(recs) * T)
    ax.tick_params(labelsize=12)
    ax.set_ylabel("ΔF/F", fontsize=15)


def panel_traces(fig, sub, recs):
    T = float(recs[0][0]["Time (s)"].to_numpy()[-1]) + 0.5
    axes = [fig.add_subplot(sub[i]) for i in range(4)]
    _draw_trace(axes[0], recs, 2, (-0.06, 0.30), T, mark=False)
    axes[0].set_facecolor("#FCF3E6")
    axes[0].text(0.006, 0.92, "ROI 02", transform=axes[0].transAxes, va="top", fontsize=14,
                 color=LEAKC, fontweight="bold")
    for ax, rnum in zip(axes[1:], BIO_ROIS):
        _draw_trace(ax, recs, rnum, (-0.09, 0.50), T)
        ax.text(0.006, 0.92, f"ROI {rnum:02d}", transform=ax.transAxes, va="top",
                fontsize=14, color=CYAN, fontweight="bold")
    for ax in axes[:3]:
        ax.tick_params(labelbottom=False)
    axes[-1].set_xlabel("Time (s)", fontsize=16)
    # large segment labels: C = control, 1-6 = stim recordings
    seg = ["C", "1", "2", "3", "4", "5", "6"]
    for k, s in enumerate(seg):
        axes[0].text((k + 0.5) * T, 0.315, s, ha="center", va="bottom",
                     fontsize=50, color="#4A4A4A", fontweight="bold")


def panel_bar(ax):
    data, _ = F.collect_compare()
    ctrl = np.asarray(data["Control"]["counts"], float)
    stim = np.asarray(data["Stim"]["counts"], float)
    ax.bar([0, 1], [ctrl.mean(), stim.mean()], 0.6, yerr=[sps.sem(ctrl), sps.sem(stim)],
           capsize=7, error_kw=dict(lw=1.8), color=[GREY, STIM], edgecolor="black", lw=1.3, zorder=2)
    rng = np.random.default_rng(0)
    for x, a in zip([0, 1], [ctrl, stim]):
        ax.scatter(x + (rng.random(a.size) - 0.5) * 0.32, a, s=30, color="black",
                   alpha=0.28, linewidths=0, zorder=3)
    p = sps.mannwhitneyu(stim, ctrl, alternative="greater").pvalue
    top = max(stim.max(), 1)
    ax.plot([0, 0, 1, 1], [top*1.04, top*1.10, top*1.10, top*1.04], lw=1.5, c="black")
    star = "***" if p < 1e-3 else "**" if p < 1e-2 else "*" if p < 5e-2 else "ns"
    ax.text(0.5, top*1.10, star, ha="center", va="bottom", fontsize=30, fontweight="bold")
    ax.set_xticks([0, 1]); ax.set_xticklabels(["No light", "Red µLED"], fontsize=17)
    ax.set_ylabel("Events / ROI", fontsize=17)
    ax.tick_params(axis="y", labelsize=13); ax.tick_params(axis="x", length=0)
    ax.set_ylim(0, top*1.30)


def main():
    recs = _recs()
    fig = plt.figure(figsize=(13.2, 8.0), dpi=300)
    gs = fig.add_gridspec(2, 2, width_ratios=[1.0, 1.72], height_ratios=[1.12, 0.9],
                          hspace=0.42, wspace=0.24, left=0.06, right=0.985,
                          top=0.84, bottom=0.14)
    panel_image(fig.add_subplot(gs[0, 0]))
    panel_bar(fig.add_subplot(gs[1, 0]))
    panel_traces(fig, gs[:, 1].subgridspec(4, 1, hspace=0.20), recs)
    # aligned panel letters + stimulus header (above the large segment labels)
    fig.text(0.012, 0.965, "a", **PLET)
    fig.text(0.44, 0.965, "b", **PLET)
    fig.text(0.012, 0.45, "c", **PLET)
    fig.text(0.985, 0.965, STIM_TXT, ha="right", va="top", fontsize=15, color="#333")
    base = ROOT / "figures" / "0714" / "fig_0714_showcase"
    for ext, kw in [(".svg", {}), (".pdf", {}), (".png", {"dpi": 300})]:
        try: fig.savefig(base.with_suffix(ext), facecolor="white", transparent=False, **kw)
        except PermissionError: print(f"  locked: {base.with_suffix(ext).name}")
    plt.close(fig)
    print("wrote:", base.with_suffix(".svg"),
          "| size:", __import__("PIL").Image.open(base.with_suffix(".png")).size)


if __name__ == "__main__":
    main()
