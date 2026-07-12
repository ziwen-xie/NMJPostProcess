"""0714 distance analysis: ROI distance-to-stim-pixel vs event count, amplitude,
and latency. Tests whether the response is spatially organized around the
stimulating red µLED pixel.

ROI centres are read from the Leica ROI.roi (real µm). The stim pixel is taken as
the midpoint of ROI.02/03 (the two ROIs sitting on the pixel). Per ROI, events are
pooled across the 6 stim recordings (ROI.02/03 in-window leakage excluded).

Run:  python figures/make_0714_distance.py  -> figures/0714/fig_0714_E_distance.*
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import figures.make_0714_figures as F        # noqa: E402
import BatchProcess as bp                      # noqa: E402
import matplotlib                              # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                # noqa: E402
from scipy import stats as sps                 # noqa: E402

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "svg.fonttype": "none", "pdf.fonttype": 42, "font.size": 11,
    "axes.linewidth": 1.0, "axes.spines.top": False, "axes.spines.right": False,
})
NAVY = "#1F4E79"


def load_coords():
    d = json.load(open(ROOT / "figures" / "_roi_coords_0714.json"))
    return {int(k): tuple(v) for k, v in d.items()}


def collect():
    """Per ROI: distance (µm), events/recording, per-event amplitudes & latencies."""
    coords = load_coords()
    px = ((coords[2][0] + coords[3][0]) / 2, (coords[2][1] + coords[3][1]) / 2)
    per = {}   # roi -> dict(dist, counts[list per rec], amps[], lats[])
    for f in F.STIM_FILES:
        tab, det = F.prep(f); sp = F.detect(tab, det, F.WINDOWS)
        _, _, lat = bp.calculate_stim_onset_latencies(sp, F.WINDOWS, max_latency_window_s=60.0)
        ti = tab["Time (s)"].to_numpy()
        latmap = {}
        if not lat.empty:
            for _, r in lat.iterrows():
                latmap.setdefault(r["ROI"], []).append(r["latency_s"])
        for c in det:
            n = F.roinum(c)
            if n not in coords or n in (2, 3):   # 02/03 on the pixel: leakage, exclude
                continue
            d = float(np.hypot(coords[n][0] - px[0], coords[n][1] - px[1]))
            rec = per.setdefault(n, dict(dist=d, counts=[], amps=[], lats=[]))
            tms = sp.get(c, [])
            rec["counts"].append(len(tms))
            y = tab[c].to_numpy()
            for tt in tms:
                rec["amps"].append(float(y[np.argmin(np.abs(ti - tt))]))
            rec["lats"].extend(latmap.get(c, []))
    return per


def _panel(ax, xs, ys, yerr, ylabel, color, invert_expect):
    xs, ys = np.asarray(xs, float), np.asarray(ys, float)
    ax.errorbar(xs, ys, yerr=yerr, fmt="o", ms=11, color=color, ecolor="#999",
                elinewidth=1.2, capsize=4, mec="black", mew=1.0, zorder=3)
    # trend line + Spearman
    if xs.size >= 3:
        rho, p = sps.spearmanr(xs, ys)
        b, a = np.polyfit(xs, ys, 1)
        xx = np.linspace(xs.min(), xs.max(), 50)
        ax.plot(xx, a + b * xx, color="#333", lw=1.6, ls="--", zorder=2)
        ax.text(0.96, 0.94, f"Spearman ρ = {rho:+.2f}\np = {p:.3f}", transform=ax.transAxes,
                ha="right", va="top", fontsize=11,
                bbox=dict(facecolor="white", edgecolor="#ccc", pad=3))
    ax.set_xlabel("Distance from stim pixel (µm)", fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)


def main():
    per = collect()
    rois = sorted(per)
    # count: all ROIs (events per recording)
    d_all = [per[n]["dist"] for n in rois]
    cnt = [np.mean(per[n]["counts"]) for n in rois]
    cnt_e = [sps.sem(per[n]["counts"]) if len(per[n]["counts"]) > 1 else 0 for n in rois]
    # amplitude / latency: only ROIs with events
    resp = [n for n in rois if per[n]["amps"]]
    d_r = [per[n]["dist"] for n in resp]
    amp = [np.mean(per[n]["amps"]) for n in resp]
    amp_e = [sps.sem(per[n]["amps"]) if len(per[n]["amps"]) > 1 else 0 for n in resp]
    latr = [n for n in rois if per[n]["lats"]]
    d_l = [per[n]["dist"] for n in latr]
    lat = [np.mean(per[n]["lats"]) for n in latr]
    lat_e = [sps.sem(per[n]["lats"]) if len(per[n]["lats"]) > 1 else 0 for n in latr]

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
    _panel(axes[0], d_all, cnt, cnt_e, "Events / recording", "#3182BD", True)
    _panel(axes[1], d_r, amp, amp_e, "Event amplitude (ΔF/F)", "#D55E00", True)
    _panel(axes[2], d_l, lat, lat_e, "Latency from onset (s)", "#2E7D32", False)
    for ax, roiset in zip(axes, (rois, resp, latr)):
        dd = [per[n]["dist"] for n in roiset]
        yy = ([np.mean(per[n]["counts"]) for n in roiset] if ax is axes[0]
              else [np.mean(per[n]["amps"]) for n in roiset] if ax is axes[1]
              else [np.mean(per[n]["lats"]) for n in roiset])
        for n, x, y in zip(roiset, dd, yy):
            ax.annotate(f"{n:02d}", (x, y), textcoords="offset points", xytext=(9, 4),
                        fontsize=8.5, color="#555")
    fig.suptitle("0714: calcium response vs ROI distance from the stimulating red µLED pixel",
                 fontsize=13, weight="bold", y=1.0)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    out = ROOT / "figures" / "0714"
    base = out / "fig_0714_E_distance"
    for ext, kw in [(".svg", {}), (".pdf", {}), (".png", {"dpi": 300})]:
        try: fig.savefig(base.with_suffix(ext), facecolor="white", **kw)
        except PermissionError: print(f"  locked: {base.with_suffix(ext).name}")
    plt.close(fig)
    # print summary
    print(f"{'ROI':>4} {'dist_um':>8} {'ev/rec':>7} {'meanAmp':>8} {'meanLat':>8}")
    for n in rois:
        a = np.mean(per[n]["amps"]) if per[n]["amps"] else float("nan")
        l = np.mean(per[n]["lats"]) if per[n]["lats"] else float("nan")
        print(f"{n:>4} {per[n]['dist']:>8.1f} {np.mean(per[n]['counts']):>7.2f} {a:>8.3f} {l:>8.1f}")
    print("wrote:", base.with_suffix(".svg"))


if __name__ == "__main__":
    main()
