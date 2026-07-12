"""MEMS 2027 abstract summary figures for the 0714 single-color evoked-response
demo. Generates several versions to choose from.

Spec: width exactly 3060 px, ~70 pt fonts (smaller only where needed, still
readable), clean academic style, SVG + PNG. Single accent colour (vermillion =
stimulation, CVD-safe), neutral grey for control, navy traces, recessive axes.

Sizing: dpi=100, width 30.6 in -> 3060 px; NO tight-bbox (keeps the exact width),
so layout is controlled by gridspec margins.

Run:  python figures/make_0714_abstract.py   -> figures/0714/abstract/
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
from matplotlib.patches import Rectangle       # noqa: E402
from scipy import stats as sps                 # noqa: E402

OUT = ROOT / "figures" / "0714" / "abstract"
DPI, W_IN = 100, 30.6                          # 30.6 in * 100 dpi = 3060 px
NAVY, STIM, GREY = "#1F4E79", "#D55E00", "#8A8A8A"
BAND = "#F3C9B3"

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "svg.fonttype": "none", "pdf.fonttype": 42,
    "axes.linewidth": 2.6, "xtick.major.width": 2.6, "ytick.major.width": 2.6,
    "axes.spines.top": False, "axes.spines.right": False,
})
FS = dict(title=72, take=44, axlabel=56, tick=42, roi=48, sig=66, seg=32)
LW, MK = 3.0, 220


def _save(fig, base):
    OUT.mkdir(parents=True, exist_ok=True)
    for ext, kw in [(".svg", {}), (".png", {"dpi": DPI})]:
        try: fig.savefig(base.with_suffix(ext), facecolor="white", **kw)
        except PermissionError: print(f"  locked: {base.with_suffix(ext).name}")
    plt.close(fig)
    return base.with_suffix(".svg")


def _load_recs():
    recs = []
    ctab, cdet = F.prep(F.CTRL_FILE)
    recs.append((ctab, cdet, F.detect(ctab, cdet, []), [], "control"))
    for k, f in enumerate(F.STIM_FILES):
        tab, det = F.prep(f)
        recs.append((tab, det, F.detect(tab, det, F.WINDOWS), F.WINDOWS, f"rec {k+1}"))
    return recs


def _compare():
    data, _ = F.collect_compare()
    return (np.asarray(data["Control"]["counts"], float),
            np.asarray(data["Stim"]["counts"], float))


def _roi_tag(ax, rnum):
    ax.text(0.008, 0.95, f"ROI {rnum:02d}", transform=ax.transAxes, ha="left", va="top",
            fontsize=FS["roi"], fontweight="bold", color=NAVY)


def _trace_concat(ax, recs, rnum, T, ylim, seg_tags=False):
    ymin, ytop = ylim
    for k, (tab, det, sp, wins, label) in enumerate(recs):
        off = k * T
        t = tab["Time (s)"].to_numpy() + off
        col = F.col_for(det, rnum)
        y = tab[col].to_numpy() if col else np.zeros_like(t)
        for (s, e) in wins:
            ax.add_patch(Rectangle((s + off, ymin), e - s, ytop - ymin, facecolor=BAND,
                         edgecolor="none", zorder=0))
        if not wins:
            ax.add_patch(Rectangle((off, ymin), T, ytop - ymin, facecolor="#ECECEC",
                         edgecolor="none", zorder=0))
        ax.plot(t, np.clip(y, ymin, ytop), color=NAVY, lw=LW, zorder=2)
        if col is not None and len(sp.get(col, [])):
            evs = sp[col]
            ey = [float(np.clip(y[np.argmin(np.abs(t - (ev + off)))], ymin, ytop)) for ev in evs]
            ax.scatter(np.asarray(evs) + off, ey, s=MK, facecolor="white",
                       edgecolor="black", linewidths=2.6, zorder=3)
        if k > 0:
            ax.axvline(off, color="#CCCCCC", lw=1.8, ls="--", zorder=1)
        if seg_tags:
            ax.text(off + T / 2, ytop, label, ha="center", va="bottom",
                    fontsize=FS["seg"], color="#666")
    ax.set_ylim(ymin, ytop); ax.set_xlim(0, len(recs) * T)
    ax.tick_params(labelsize=FS["tick"], length=8, width=2.6)
    ax.set_ylabel("ΔF/F", fontsize=FS["roi"], fontweight="bold")
    _roi_tag(ax, rnum)


def _one_rec(ax, rec, rnum, ylim, title, shade, xlab=False):
    tab, det, sp, wins, _ = rec
    t = tab["Time (s)"].to_numpy(); col = F.col_for(det, rnum); y = tab[col].to_numpy()
    ymin, ytop = ylim
    if shade:
        for (s, e) in F.WINDOWS:
            ax.add_patch(Rectangle((s, ymin), e - s, ytop - ymin, facecolor=BAND,
                         edgecolor="none", zorder=0))
    ax.plot(t, np.clip(y, ymin, ytop), color=NAVY, lw=LW, zorder=2)
    if shade and len(sp.get(col, [])):
        evs = sp[col]
        ey = [float(np.clip(y[np.argmin(np.abs(t - ev))], ymin, ytop)) for ev in evs]
        ax.scatter(evs, ey, s=MK + 60, facecolor="white", edgecolor="black", linewidths=2.8, zorder=3)
    ax.set_ylim(ymin, ytop); ax.set_xlim(0, t[-1])
    if title:
        ax.set_title(title, fontsize=FS["axlabel"], fontweight="bold",
                     color=(STIM if shade else "#555"), pad=14)
    ax.set_ylabel("ΔF/F", fontsize=FS["roi"], fontweight="bold")
    ax.tick_params(labelsize=FS["tick"], length=8, width=2.6)
    _roi_tag(ax, rnum)
    if xlab:
        ax.set_xlabel("Time (s)", fontsize=FS["axlabel"])


def _bar(ax, ctrl, stim, xlabels=("No light", "Red µLED")):
    means = [ctrl.mean(), stim.mean()]
    sems = [sps.sem(ctrl) if ctrl.size > 1 else 0, sps.sem(stim) if stim.size > 1 else 0]
    ax.bar([0, 1], means, 0.62, yerr=sems, capsize=10, error_kw=dict(lw=2.8),
           color=[GREY, STIM], edgecolor="black", lw=2.6, zorder=2)
    rng = np.random.default_rng(0)
    for x, a in zip([0, 1], [ctrl, stim]):
        if a.size:
            ax.scatter(x + (rng.random(a.size) - 0.5) * 0.34, a, s=90, color="black",
                       alpha=0.28, linewidths=0, zorder=3)
    p = sps.mannwhitneyu(stim, ctrl, alternative="greater").pvalue
    top = max(stim.max(), 1)
    ax.plot([0, 0, 1, 1], [top*1.03, top*1.09, top*1.09, top*1.03], lw=2.6, c="black")
    star = "***" if p < 1e-3 else "**" if p < 1e-2 else "*" if p < 5e-2 else "ns"
    ax.text(0.5, top*1.10, star, ha="center", va="bottom", fontsize=FS["sig"], fontweight="bold")
    ax.text(0.5, top*1.25, f"p = {p:.3f}", ha="center", va="bottom", fontsize=FS["tick"])
    ax.set_xticks([0, 1]); ax.set_xticklabels(xlabels, fontsize=FS["axlabel"])
    ax.set_ylabel("Events / ROI", fontsize=FS["axlabel"], fontweight="bold")
    ax.tick_params(axis="y", labelsize=FS["tick"], length=8, width=2.6)
    ax.tick_params(axis="x", length=0)
    ax.set_ylim(0, top*1.42)


TITLE = "Red µLED stimulation evokes calcium responses"


def version1():
    """Reproducibility: two ROIs, all 6 trials concatenated, + quantification."""
    recs = _load_recs(); ctrl, stim = _compare()
    T = float(recs[0][0]["Time (s)"].to_numpy()[-1]) + 0.5
    fig = plt.figure(figsize=(W_IN, 15.0), dpi=DPI)
    gs = fig.add_gridspec(2, 2, width_ratios=[2.7, 1.0], hspace=0.30, wspace=0.19,
                          left=0.065, right=0.985, top=0.77, bottom=0.10)
    ax1 = fig.add_subplot(gs[0, 0]); ax2 = fig.add_subplot(gs[1, 0], sharex=ax1)
    axb = fig.add_subplot(gs[:, 1])
    _trace_concat(ax1, recs, 12, T, (-0.08, 0.50), seg_tags=True)
    _trace_concat(ax2, recs, 10, T, (-0.05, 0.25))
    ax1.tick_params(labelbottom=False)
    ax2.set_xlabel("Time  —  no-light control, then 6 red-µLED stim recordings",
                   fontsize=FS["axlabel"])
    _bar(axb, ctrl, stim)
    fig.text(0.5, 0.925, TITLE, ha="center", fontsize=FS["title"], fontweight="bold")
    fig.text(0.5, 0.845, "PC12–C2C12 · GCaMP8s ΔF/F · control silent · "
             "more transients across all 6 trials (bands = 10 s stim)",
             ha="center", fontsize=FS["take"], color="#333")
    return _save(fig, OUT / "abstract_v1_traces_bar")


def version2():
    """Contrast: ROI.12 no-light vs a red-µLED recording, side by side, + bar."""
    recs = _load_recs(); ctrl, stim = _compare()
    ctrl_rec, stim_rec = recs[0], recs[1]      # rec 1: clear in-window transient
    fig = plt.figure(figsize=(W_IN, 12.5), dpi=DPI)
    gs = fig.add_gridspec(1, 3, width_ratios=[1, 1, 0.82], wspace=0.30,
                          left=0.07, right=0.98, top=0.68, bottom=0.15)
    axc = fig.add_subplot(gs[0, 0]); axs = fig.add_subplot(gs[0, 1], sharey=axc)
    axb = fig.add_subplot(gs[0, 2])
    _one_rec(axc, ctrl_rec, 12, (-0.08, 0.50), "No-light control", False, xlab=True)
    _one_rec(axs, stim_rec, 12, (-0.08, 0.50), "Red µLED stim (10 s windows)", True, xlab=True)
    _bar(axb, ctrl, stim)
    fig.text(0.5, 0.92, TITLE, ha="center", fontsize=FS["title"], fontweight="bold")
    fig.text(0.5, 0.81, "Silent under no light · transients emerge under red-µLED stim "
             "(orange bands) · PC12–C2C12, GCaMP8s", ha="center", fontsize=FS["take"], color="#333")
    return _save(fig, OUT / "abstract_v2_control_vs_stim")


def version3():
    """Hero: one big ROI.12 concatenated trace; quantification as a compact inset."""
    recs = _load_recs(); ctrl, stim = _compare()
    T = float(recs[0][0]["Time (s)"].to_numpy()[-1]) + 0.5
    fig = plt.figure(figsize=(W_IN, 11.0), dpi=DPI)
    ax = fig.add_axes([0.065, 0.16, 0.70, 0.60])
    axb = fig.add_axes([0.80, 0.16, 0.175, 0.60])
    _trace_concat(ax, recs, 12, T, (-0.08, 0.50), seg_tags=True)
    ax.set_xlabel("Time  —  no-light control, then 6 red-µLED stim recordings",
                  fontsize=FS["axlabel"])
    _bar(axb, ctrl, stim)
    fig.text(0.5, 0.925, TITLE, ha="center", fontsize=FS["title"], fontweight="bold")
    fig.text(0.5, 0.845, "PC12–C2C12 · GCaMP8s ΔF/F · control silent · reproducible across 6 trials",
             ha="center", fontsize=FS["take"], color="#333")
    return _save(fig, OUT / "abstract_v3_hero")


def _spatial_panel(ax, perroi):
    resp = {n: (float(np.mean(perroi[n]["stim"])) if perroi[n]["stim"] else 0.0)
            for n in perroi if n in F.ROI_XY}
    xs = [F.ROI_XY[n][0] for n in resp]; ys = [F.ROI_XY[n][1] for n in resp]
    cs = [resp[n] for n in resp]; vmax = max(cs) if any(cs) else 1.0
    sc = ax.scatter(xs, ys, c=cs, s=760, cmap="hot_r", vmin=0, vmax=vmax,
                    edgecolor="black", linewidths=1.4, zorder=2)
    for n in resp:
        ax.text(F.ROI_XY[n][0], F.ROI_XY[n][1], f"{n:02d}", ha="center", va="center",
                fontsize=FS["seg"] - 4, fontweight="bold", zorder=3,
                color="white" if resp[n] > vmax * 0.55 else "black")
    ax.scatter(*F.PIXEL_XY, marker="s", s=420, facecolor="red", edgecolor="black",
               linewidths=1.6, zorder=1)
    ax.annotate("stim\npixel", F.PIXEL_XY, textcoords="offset points", xytext=(0, -30),
                ha="center", color="red", fontsize=FS["seg"], fontweight="bold")
    ax.set_aspect("equal"); ax.invert_yaxis(); ax.axis("off")
    ax.margins(0.12)
    ax.set_title("Response map", fontsize=FS["axlabel"], fontweight="bold")
    cb = ax.figure.colorbar(sc, ax=ax, fraction=0.040, pad=0.02)
    cb.set_label("events / rec", fontsize=FS["tick"] - 6)
    cb.ax.tick_params(labelsize=FS["tick"] - 8)
    return cb


def _contact_panel(ax):
    import matplotlib.image as mpimg
    img = mpimg.imread(str(OUT.parent / "assets" / "contact_ch470.png"))
    g = img[..., 0] if img.ndim == 3 else img
    lo, hi = np.percentile(g, 2), np.percentile(g, 99.5)
    ax.imshow(np.clip((g - lo) / (hi - lo), 0, 1), cmap="gray")
    ax.axis("off")
    ax.set_title("Array–cell contact (GCaMP, 100 µm bar)", fontsize=FS["axlabel"], fontweight="bold")


def _placeholder(ax, text):
    ax.axis("off")
    ax.add_patch(plt.Rectangle((0.02, 0.05), 0.96, 0.9, transform=ax.transAxes,
                 facecolor="#F5F5F5", edgecolor="#AAAAAA", lw=2.4, ls="--"))
    ax.text(0.5, 0.5, text, transform=ax.transAxes, ha="center", va="center",
            fontsize=FS["take"], color="#888", wrap=True)


def version4():
    """Enriched composite: device schematic (placeholder) + contact image +
    spatial map + representative trace + quantification."""
    recs = _load_recs(); ctrl, stim = _compare()
    _, perroi = F.collect_compare()
    T = float(recs[0][0]["Time (s)"].to_numpy()[-1]) + 0.5
    fig = plt.figure(figsize=(W_IN, 19.5), dpi=DPI)
    gs = fig.add_gridspec(2, 3, height_ratios=[1.05, 1.0], width_ratios=[1, 1, 1.05],
                          hspace=0.30, wspace=0.22, left=0.045, right=0.915,
                          top=0.80, bottom=0.075)
    _placeholder(fig.add_subplot(gs[0, 0]), "µLED array device schematic\n(insert mechanical drawing)")
    _contact_panel(fig.add_subplot(gs[0, 1]))
    _spatial_panel(fig.add_subplot(gs[0, 2]), perroi)
    axt = fig.add_subplot(gs[1, :2])
    _trace_concat(axt, recs, 12, T, (-0.08, 0.50), seg_tags=True)
    axt.set_xlabel("Time  —  no-light control, then 6 red-µLED stim recordings", fontsize=FS["axlabel"])
    _bar(fig.add_subplot(gs[1, 2]), ctrl, stim)
    fig.text(0.5, 0.945, TITLE, ha="center", fontsize=FS["title"], fontweight="bold")
    fig.text(0.5, 0.875, "Single-pixel red µLED · PC12–C2C12, GCaMP8s · control silent · "
             "ΔF/F up to ~0.4 · reproducible across 6 trials",
             ha="center", fontsize=FS["take"], color="#333")
    return _save(fig, OUT / "abstract_v4_enriched")


def main():
    for fn in (version1, version2, version3, version4):
        print("wrote:", fn())


if __name__ == "__main__":
    main()
