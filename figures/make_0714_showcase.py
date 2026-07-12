"""0714 academic data-showcase figure (journal style) for the MEMS abstract.

  a  two-colour fluorescence at the array-cell contact (GCaMP8s green / ChrimsonR
     red) with the stimulating µLED pixel and ROI overlay (real ROI.roi coords).
  b  ΔF/F traces: on-pixel light-leakage control ROI (artifact) separated from
     biological Ca2+ response ROIs; stimulus stated (625 nm, 4 mW/mm2, 10 s).
  c  paired per-ROI event rate, no-light control vs red-µLED stim (Wilcoxon).

Stim: 625 nm red µLED, 4 mW/mm2, three 10 s windows (30-40/70-80/110-120 s).
Design: 14 ROIs from ONE co-culture prep / FOV; 6 repeated stim recordings ->
ROIs are not independent biological replicates (stated on panel c).

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
from matplotlib.patches import Rectangle, Circle  # noqa: E402
from scipy import stats as sps                 # noqa: E402

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "svg.fonttype": "none", "pdf.fonttype": 42, "font.size": 12,
    "axes.linewidth": 1.1, "xtick.major.width": 1.1, "ytick.major.width": 1.1,
    "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": "white",
})
NAVY, STIM, GREY, BAND = "#12365B", "#D55E00", "#8A8A8A", "#F4C39C"
CYAN, LEAKC = "#19C3D6", "#F2A93B"
ASSETS = ROOT / "figures" / "0714" / "assets"
PLET = dict(fontsize=17, fontweight="bold", va="top", ha="right")
STIM_TXT = "Red µLED · 625 nm · 4 mW/mm² · 10 s"
LEAK_ROIS, BIO_ROIS = [2], [10, 12, 14]        # panel b rows
PXPERUM = 2048 / 665.28                          # 3.078 px/µm (0.325 µm/px)


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
    for n, (x, y) in coords.items():
        if n == 1:
            continue
        col = LEAKC if n in (2, 3) else (CYAN if n in BIO_ROIS else "white")
        lw = 3.0 if n in (2, 3) + tuple(BIO_ROIS) else 1.6
        ax.add_patch(Circle((x, y), 34, fill=False, edgecolor=col, lw=lw, zorder=3))
        ax.text(x + 40, y - 40, f"{n:02d}", color=col, fontsize=12, fontweight="bold", zorder=4)
    # µLED pixel
    ax.add_patch(Rectangle((px[0] - 42, px[1] - 42), 84, 84, fill=False, edgecolor="red",
                 lw=3.4, zorder=5))
    ax.text(px[0] + 60, px[1] + 78, "µLED", color="red", fontsize=12.5, fontweight="bold", zorder=5)
    # (100 µm scale bar is burned into the source image, bottom-left)
    ax.text(0.03, 0.985, "GCaMP8s", color="#39FF9E", transform=ax.transAxes, va="top",
            fontsize=13.5, fontweight="bold")
    ax.text(0.03, 0.915, "ChrimsonR", color="#FF7A7A", transform=ax.transAxes, va="top",
            fontsize=13.5, fontweight="bold")
    ax.set_xlim(0, 2048); ax.set_ylim(2048, 0); ax.axis("off")
    ax.text(-0.02, 1.05, "a", transform=ax.transAxes, **PLET)


def _recs():
    recs = []
    ctab, cdet = F.prep(F.CTRL_FILE)
    recs.append((ctab, cdet, F.detect(ctab, cdet, []), [], "ctrl"))
    for k, f in enumerate(F.STIM_FILES):
        tab, det = F.prep(f)
        recs.append((tab, det, F.detect(tab, det, F.WINDOWS), F.WINDOWS, f"{k+1}"))
    return recs


def _draw_trace(ax, recs, rnum, ylim, T, mark=True):
    ymin, ytop = ylim
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
        if mark and len(sp.get(col, [])):
            ev = sp[col]
            ey = [float(np.clip(y[np.argmin(np.abs(t - (e2 + off)))], ymin, ytop)) for e2 in ev]
            ax.scatter(np.asarray(ev) + off, ey, s=46, facecolor="white", edgecolor="black",
                       linewidths=1.1, zorder=3)
        if k > 0:
            ax.axvline(off, color="#D2D2D2", lw=0.8, ls="--", zorder=1)
    ax.set_ylim(ymin, ytop); ax.set_xlim(0, len(recs) * T)
    ax.tick_params(labelsize=10)


def panel_traces(fig, sub, recs):
    T = float(recs[0][0]["Time (s)"].to_numpy()[-1]) + 0.5
    axes = [fig.add_subplot(sub[i]) for i in range(4)]
    # row 0: artifact ROI.02 (own scale, clipped)
    _draw_trace(axes[0], recs, 2, (-0.06, 0.30), T, mark=False)
    axes[0].set_ylabel("ΔF/F", fontsize=12)
    axes[0].text(0.006, 0.9, "ROI 02", transform=axes[0].transAxes, va="top", fontsize=11.5,
                 color=LEAKC, fontweight="bold")
    axes[0].set_facecolor("#FCF4E8")
    # rows 1-3: biological responders on a COMMON ΔF/F scale
    for ax, rnum in zip(axes[1:], BIO_ROIS):
        _draw_trace(ax, recs, rnum, (-0.09, 0.50), T)
        ax.set_ylabel("ΔF/F", fontsize=12)
        ax.text(0.006, 0.9, f"ROI {rnum:02d}", transform=ax.transAxes, va="top",
                fontsize=11.5, color=CYAN if rnum != 12 else "#0E8C9B", fontweight="bold")
    for ax in axes[:3]:
        ax.tick_params(labelbottom=False)
    axes[-1].set_xlabel("Time (s)  ·  no-light control (grey), then 6 red-µLED stim recordings", fontsize=12)
    for k, (_, _, _, _, lab) in enumerate(recs):
        axes[0].text((k + 0.5) * T, 0.305, "control" if lab == "ctrl" else f"rec {lab}",
                     ha="center", va="bottom", fontsize=9, color="#666")
    # section labels (vertically separated to avoid collisions)
    axes[0].text(0.006, 1.15, "On-pixel artifact — red-light leakage (not counted)",
                 transform=axes[0].transAxes, fontsize=11, color=LEAKC, fontweight="bold")
    axes[1].text(0.006, 1.09, "Biological Ca²⁺ responses (common ΔF/F scale)",
                 transform=axes[1].transAxes, fontsize=11, color="#0E8C9B", fontweight="bold")
    # panel letter + stimulus/marker legend as figure-level text (no clipping)
    fig.text(0.435, 0.975, "b", fontsize=17, fontweight="bold", va="top")
    fig.text(0.72, 0.965, STIM_TXT + "     orange band = stim window     ○ = detected Ca²⁺ event",
             ha="center", va="top", fontsize=10.5, color="#333")


def panel_paired(ax):
    _, perroi = F.collect_compare()
    rois = [n for n in sorted(perroi) if n not in (2, 3)]     # exclude on-pixel leakage ROIs
    cv = np.array([perroi[n]["control"] for n in rois], float)
    sv = np.array([float(np.mean(perroi[n]["stim"])) for n in rois], float)
    rng = np.random.default_rng(3)
    jx0 = -0.0 + (rng.random(len(rois)) - 0.5) * 0.10
    for x0, y0, y1 in zip(jx0, cv, sv):
        ax.plot([0 + x0, 1 + x0], [y0, y1], color="#C7C7C7", lw=1.0, zorder=1)
    ax.scatter(0 + jx0, cv, s=42, color=GREY, edgecolor="black", linewidths=0.8, zorder=3)
    ax.scatter(1 + jx0, sv, s=42, color=STIM, edgecolor="black", linewidths=0.8, zorder=3)
    try:
        w, p = sps.wilcoxon(sv, cv)
    except ValueError:
        p = float("nan")
    top = max(sv.max(), 0.1)
    ax.plot([0, 0, 1, 1], [top*1.05, top*1.11, top*1.11, top*1.05], lw=1.2, c="black")
    star = "***" if p < 1e-3 else "**" if p < 1e-2 else "*" if p < 5e-2 else "ns"
    ax.text(0.5, top*1.12, f"{star}  Wilcoxon p = {p:.3f}", ha="center", va="bottom", fontsize=12)
    ax.set_xticks([0, 1]); ax.set_xticklabels(["No light", "Red µLED"], fontsize=13)
    ax.set_ylabel("Events / ROI  (mean of 6 recs)", fontsize=12.5)
    ax.tick_params(axis="y", labelsize=10); ax.tick_params(axis="x", length=0)
    ax.set_xlim(-0.4, 1.4); ax.set_ylim(-0.05, top*1.28)
    ax.text(0.5, -0.20, f"n = {len(rois)} ROIs, one co-culture preparation\n"
            "(paired per ROI; ROIs not independent biological replicates)",
            transform=ax.transAxes, ha="center", va="top", fontsize=10.5, color="#555")
    ax.figure.text(0.008, 0.485, "c", fontsize=17, fontweight="bold", va="top")


def main():
    recs = _recs()
    fig = plt.figure(figsize=(13.2, 8.0), dpi=300)
    gs = fig.add_gridspec(2, 2, width_ratios=[1.0, 1.72], height_ratios=[1.15, 0.9],
                          hspace=0.5, wspace=0.24, left=0.055, right=0.985,
                          top=0.90, bottom=0.135)
    panel_image(fig.add_subplot(gs[0, 0]))
    panel_paired(fig.add_subplot(gs[1, 0]))
    panel_traces(fig, gs[:, 1].subgridspec(4, 1, hspace=0.22), recs)
    base = ROOT / "figures" / "0714" / "fig_0714_showcase"
    for ext, kw in [(".svg", {}), (".pdf", {}), (".png", {"dpi": 300})]:
        try: fig.savefig(base.with_suffix(ext), facecolor="white", transparent=False, **kw)
        except PermissionError: print(f"  locked: {base.with_suffix(ext).name}")
    plt.close(fig)
    print("wrote:", base.with_suffix(".svg"),
          "| size:", __import__("PIL").Image.open(base.with_suffix(".png")).size)


if __name__ == "__main__":
    main()
