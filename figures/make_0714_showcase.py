"""0714 academic data-showcase figure (journal style, for the MEMS abstract).

Panels (minimal text, panel letters, no schematic):
  a  two-colour fluorescence at the array-cell contact (GCaMP8s green / ChrimsonR red)
  b  representative ΔF/F traces of ROI 02, 10, 12, 14 (control + 6 stim recordings)
  c  event rate per ROI, no-light control vs red-µLED stimulation

Run:  python figures/make_0714_showcase.py  -> figures/0714/fig_0714_showcase.*
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import figures.make_0714_figures as F        # noqa: E402
import matplotlib                              # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                # noqa: E402
import matplotlib.image as mpimg               # noqa: E402
from matplotlib.patches import Rectangle       # noqa: E402
from scipy import stats as sps                 # noqa: E402

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "svg.fonttype": "none", "pdf.fonttype": 42, "font.size": 12,
    "axes.linewidth": 1.1, "xtick.major.width": 1.1, "ytick.major.width": 1.1,
    "axes.spines.top": False, "axes.spines.right": False,
})
NAVY, STIM, GREY, BAND = "#12365B", "#D55E00", "#8A8A8A", "#F4CBB4"
ASSETS = ROOT / "figures" / "0714" / "assets"
REP = [2, 10, 12, 14]
PLETTER = dict(fontsize=24, fontweight="bold", va="top", ha="right")


def _stretch(g, lo=2, hi=99.6):
    a, b = np.percentile(g, lo), np.percentile(g, hi)
    return np.clip((g - a) / (b - a + 1e-9), 0, 1)


def panel_image(ax):
    g = np.array(mpimg.imread(str(ASSETS / "contact_ch470_full.png")))
    r = np.array(mpimg.imread(str(ASSETS / "contact_ch580.png")))
    g = g[..., 0] if g.ndim == 3 else g
    r = r[..., 0] if r.ndim == 3 else r
    rgb = np.dstack([_stretch(r), _stretch(g), np.zeros_like(g, dtype=float)])
    ax.imshow(rgb)
    ax.axis("off")
    ax.text(0.03, 0.97, "GCaMP8s", color="#39FF88", transform=ax.transAxes, va="top",
            fontsize=14, fontweight="bold")
    ax.text(0.03, 0.90, "ChrimsonR", color="#FF6B6B", transform=ax.transAxes, va="top",
            fontsize=14, fontweight="bold")
    ax.text(-0.02, 1.06, "a", transform=ax.transAxes, **PLETTER)


def _recs():
    recs = []
    ctab, cdet = F.prep(F.CTRL_FILE)
    recs.append((ctab, cdet, F.detect(ctab, cdet, []), [], "ctrl"))
    for k, f in enumerate(F.STIM_FILES):
        tab, det = F.prep(f)
        recs.append((tab, det, F.detect(tab, det, F.WINDOWS), F.WINDOWS, f"{k+1}"))
    return recs


def panel_traces(axes, recs):
    T = float(recs[0][0]["Time (s)"].to_numpy()[-1]) + 0.5
    for row, (ax, rnum) in enumerate(zip(axes, REP)):
        # per-ROI y-scale; cap leak ROIs so their in-window leakage clips
        m = max(0.05, *[np.nanpercentile(tab[F.col_for(det, rnum)].to_numpy(), 99.5)
                        for tab, det, *_ in recs if F.col_for(det, rnum)])
        if rnum in F.LEAK_ROIS:
            m = min(m, 0.35)
        ymin, ytop = -0.18 * m, 1.15 * m
        for k, (tab, det, sp, wins, lab) in enumerate(recs):
            off = k * T
            t = tab["Time (s)"].to_numpy() + off
            col = F.col_for(det, rnum); y = tab[col].to_numpy()
            for (s, e) in wins:
                ax.add_patch(Rectangle((s + off, ymin), e - s, ytop - ymin, facecolor=BAND,
                             edgecolor="none", zorder=0))
            if not wins:
                ax.add_patch(Rectangle((off, ymin), T, ytop - ymin, facecolor="#EEEEEE",
                             edgecolor="none", zorder=0))
            ax.plot(t, np.clip(y, ymin, ytop), color=NAVY, lw=1.1, zorder=2)
            if len(sp.get(col, [])):
                ev = sp[col]
                ey = [float(np.clip(y[np.argmin(np.abs(t - (e2 + off)))], ymin, ytop)) for e2 in ev]
                ax.scatter(np.asarray(ev) + off, ey, s=42, facecolor="white",
                           edgecolor="black", linewidths=1.1, zorder=3)
            if k > 0:
                ax.axvline(off, color="#D2D2D2", lw=0.8, ls="--", zorder=1)
        ax.set_ylim(ymin, ytop); ax.set_xlim(0, len(recs) * T)
        ax.set_ylabel(f"ROI {rnum:02d}\nΔF/F", fontsize=12)
        ax.tick_params(labelsize=10)
        if row < len(REP) - 1:
            ax.tick_params(labelbottom=False)
        lk = "  (on pixel: in-window = light leakage)" if rnum in F.LEAK_ROIS else ""
        ax.text(0.006, 0.9, f"ROI {rnum:02d}{lk}", transform=ax.transAxes, va="top",
                fontsize=11, color=NAVY, fontweight="bold")
    axes[-1].set_xlabel("Time (s)  —  no-light control, then 6 red-µLED stim recordings", fontsize=12)
    # segment tags on the top trace
    for k, (_, _, _, _, lab) in enumerate(recs):
        axes[0].text((k + 0.5) * T, axes[0].get_ylim()[1], "control" if lab == "ctrl" else f"rec {lab}",
                     ha="center", va="bottom", fontsize=9.5, color="#666")
    axes[0].text(-0.055, 1.16, "b", transform=axes[0].transAxes, **PLETTER)


def panel_bar(ax):
    data, _ = F.collect_compare()
    ctrl = np.asarray(data["Control"]["counts"], float)
    stim = np.asarray(data["Stim"]["counts"], float)
    means, sems = [ctrl.mean(), stim.mean()], [sps.sem(ctrl), sps.sem(stim)]
    ax.bar([0, 1], means, 0.6, yerr=sems, capsize=6, error_kw=dict(lw=1.4),
           color=[GREY, STIM], edgecolor="black", lw=1.1, zorder=2)
    rng = np.random.default_rng(0)
    for x, a in zip([0, 1], [ctrl, stim]):
        ax.scatter(x + (rng.random(a.size) - 0.5) * 0.32, a, s=26, color="black",
                   alpha=0.30, linewidths=0, zorder=3)
    p = sps.mannwhitneyu(stim, ctrl, alternative="greater").pvalue
    top = max(stim.max(), 1)
    ax.plot([0, 0, 1, 1], [top*1.02, top*1.07, top*1.07, top*1.02], lw=1.2, c="black")
    star = "***" if p < 1e-3 else "**" if p < 1e-2 else "*" if p < 5e-2 else "ns"
    ax.text(0.5, top*1.08, f"{star}  p={p:.3f}", ha="center", va="bottom", fontsize=13)
    ax.set_xticks([0, 1]); ax.set_xticklabels(["No light", "Red µLED"], fontsize=13)
    ax.set_ylabel("Events / ROI", fontsize=13)
    ax.tick_params(axis="y", labelsize=10); ax.tick_params(axis="x", length=0)
    ax.set_ylim(0, top*1.28)
    ax.text(-0.13, 1.09, "c", transform=ax.transAxes, **PLETTER)


def main():
    recs = _recs()
    fig = plt.figure(figsize=(13, 7.6), dpi=300)
    gs = fig.add_gridspec(2, 2, width_ratios=[1.0, 1.75], height_ratios=[1.05, 1.0],
                          hspace=0.42, wspace=0.26, left=0.055, right=0.985,
                          top=0.93, bottom=0.10)
    panel_image(fig.add_subplot(gs[0, 0]))
    panel_bar(fig.add_subplot(gs[1, 0]))
    sub = gs[:, 1].subgridspec(len(REP), 1, hspace=0.18)
    panel_traces([fig.add_subplot(sub[i]) for i in range(len(REP))], recs)
    base = ROOT / "figures" / "0714" / "fig_0714_showcase"
    for ext, kw in [(".svg", {}), (".pdf", {}), (".png", {"dpi": 300})]:
        try: fig.savefig(base.with_suffix(ext), facecolor="white", **kw)
        except PermissionError: print(f"  locked: {base.with_suffix(ext).name}")
    plt.close(fig)
    print("wrote:", base.with_suffix(".svg"),
          "| size:", __import__("PIL").Image.open(base.with_suffix(".png")).size)


if __name__ == "__main__":
    main()
