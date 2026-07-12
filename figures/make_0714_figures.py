"""Figures for the 0714 single-color (basic) evoked-response demo.

Six 10s-stimulation recordings (1-6.csv, same red pixel next to ROI.2, done one
after another) + one no-light control (Ctrl.csv). 14 ROIs, 2 fps, ~155 s each,
three 10 s stim windows per file at 30-40 / 70-80 / 110-120 s. ROI.01 = background.

Outputs (figures/0714/):
  A) example traces of representative ROIs, 6 stim recordings + the no-light
     control CONCATENATED into one timeline (18 stim windows + control block)
  B) Control vs Stim comparison: event count / amplitude / latency

ROI.02/03 sit on the stim pixel -> their in-window peaks are red-light leakage,
not calcium, so they are excluded. Detection: ROI.01 background, raw-baseline
dF/F, prominence-based peak detector (robust lower-percentile noise; peaks must
clear both height and prominence >= k*sigma) which catches obvious transients
(incl. pre-stim spontaneous) while rejecting small noise bumps. Latency from
stim onset (stimulated recordings only).
"""
from __future__ import annotations
import os, re, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import BatchProcess as bp                       # noqa: E402
import matplotlib                               # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                 # noqa: E402
from matplotlib.patches import Rectangle        # noqa: E402
from scipy import stats as sps                  # noqa: E402
from scipy.signal import find_peaks             # noqa: E402

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "svg.fonttype": "none", "pdf.fonttype": 42, "font.size": 8,
    "axes.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False,
})

DIR = ROOT / "data" / "raw" / "single_color_red" / "0714"
WINDOWS = [(30.0, 40.0), (70.0, 80.0), (110.0, 120.0)]
STIM_FILES = [DIR / f"{i}.csv" for i in range(1, 7)]
CTRL_FILE = DIR / "Ctrl.csv"
# Prominence-based transient detector. Noise sigma is estimated from the lower
# side of the distribution (median - 16th pct), which the positive-going calcium
# transients cannot inflate -> stable threshold even when a transient sits in the
# baseline window. A peak must clear both an absolute height and a prominence
# (stand out from its neighbours), which rejects small noise bumps.
K_PROM, K_HEIGHT, MIN_W_S, MIN_DIST_S = 4.0, 3.5, 1.0, 4.0
# ROI.02/03 sit on top of the stim pixel: their in-window "peaks" are red-light
# leakage into the GFP channel, not calcium. Exclude them entirely.
EXCLUDE_ROIS = {2, 3}
REP_ROIS = [10, 12, 9, 8, 7]
ROI_NOTE = {7: "distal — sparse"}
OUT = ROOT / "figures" / "0714"
STIM_COLOR = "#C0392B"                  # red-ish (matches the stimulating pixel)


def roinum(col: str) -> int:
    m = re.search(r"ROI\.(\d+)", col)
    return int(m.group(1)) if m else -1


def prep(path: Path):
    df = pd.read_csv(path, encoding="utf-16", skiprows=1)
    t = df["Axis [s]"].to_numpy(float)
    roicols = [c for c in df.columns if "ROI" in c]
    bg = next(c for c in roicols if "ROI.01" in c)          # explicit background
    det = [c for c in roicols if c != bg and roinum(c) not in EXCLUDE_ROIS]
    bgv = df[bg].to_numpy(float)
    dd = {}
    for c in det:
        raw = df[c].to_numpy(float)
        dff, _ = bp.dff_percentile_window(raw - bgv, t, 15.0, 8.0, F_denom=raw)
        dd[c] = dff
    tab = pd.DataFrame(dd); tab.insert(0, "Time (s)", t)
    return tab, det


def detect2(y, t, dt):
    """Prominence-based calcium-transient detector with robust (lower-percentile)
    noise. Returns event times. Includes pre-stim spontaneous transients."""
    med = float(np.median(y))
    sig = max(med - float(np.percentile(y, 16)), 1e-6)
    pk, _ = find_peaks(y, height=med + K_HEIGHT * sig, prominence=K_PROM * sig,
                       distance=max(1, int(round(MIN_DIST_S / dt))),
                       width=max(1, int(round(MIN_W_S / dt))))
    return t[pk]


def detect(tab, det):
    t = tab["Time (s)"].to_numpy()
    dt = float(np.median(np.diff(t)))
    return {c: detect2(tab[c].to_numpy(), t, dt) for c in det}


def col_for(det, num):
    for c in det:
        if roinum(c) == num:
            return c
    return None


# ----------------------------------------------------------------- Figure A
def figure_traces():
    # load & detect the 6 stim files, then the control as a 7th segment (no stim)
    recs = []  # (tab, det, sp, windows, label)
    for k, f in enumerate(STIM_FILES):
        tab, det = prep(f)
        recs.append((tab, det, detect(tab, det), WINDOWS, f"rec {k+1}"))
    ctab, cdet = prep(CTRL_FILE)
    recs.append((ctab, cdet, detect(ctab, cdet), [], "control"))
    T = float(recs[0][0]["Time (s)"].to_numpy()[-1]) + 0.5   # per-file span for offset

    fig, axes = plt.subplots(len(REP_ROIS), 1, figsize=(12, 1.35 * len(REP_ROIS) + 0.6),
                             sharex=True)
    for row, rnum in enumerate(REP_ROIS):
        ax = axes[row]
        ymax_est = 0.02
        seg_all = []
        for k, (tab, det, sp, wins, label) in enumerate(recs):
            off = k * T
            t = tab["Time (s)"].to_numpy() + off
            col = col_for(det, rnum)
            y = tab[col].to_numpy() if col else np.zeros_like(t)
            seg_all.append((t, y, off, sp.get(col, []) if col else [], wins))
            ymax_est = max(ymax_est, np.nanpercentile(y, 99.5))
        ymin = -0.2 * ymax_est
        ytop = 1.15 * ymax_est
        for k, (t, y, off, evs, wins) in enumerate(seg_all):
            for (s, e) in wins:
                ax.add_patch(Rectangle((s + off, ymin), e - s, ytop - ymin,
                             facecolor=STIM_COLOR, edgecolor="none", alpha=0.13, zorder=0))
            # shade the control segment faint grey so it reads as a distinct block
            if not wins:
                ax.add_patch(Rectangle((off, ymin), T, ytop - ymin,
                             facecolor="#000000", edgecolor="none", alpha=0.04, zorder=0))
            ax.plot(t, y, color="#1F4E79", lw=0.7, zorder=2)
            if len(evs):
                ey = [float(y[np.argmin(np.abs(t - (ev + off)))]) for ev in evs]
                ax.scatter(np.asarray(evs) + off, ey, s=14, facecolor="white",
                           edgecolor="black", linewidths=0.6, zorder=3)
            if k > 0:
                ax.axvline(off, color="#BBBBBB", lw=0.6, ls="--", zorder=1)
        ax.set_ylim(ymin, ytop)
        ax.set_xlim(0, len(recs) * T)
        note = ROI_NOTE.get(rnum, "")
        note = f"  ({note})" if note else ""
        ax.set_ylabel(f"ROI.{rnum:02d}\ndF/F", fontsize=7.5)
        ax.text(0.004, 0.92, f"ROI.{rnum:02d}{note}", transform=ax.transAxes,
                va="top", ha="left", fontsize=7.5, weight="bold",
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.7, pad=1))
    # segment labels along the top
    for k, (_, _, _, _, label) in enumerate(recs):
        axes[0].text((k + 0.5) * T, axes[0].get_ylim()[1], label,
                     ha="center", va="bottom", fontsize=6.5,
                     color="#555" if label == "control" else "#666",
                     weight="bold" if label == "control" else "normal")
    axes[-1].set_xlabel("Concatenated time: 6 stim recordings + no-light control  "
                        "(red bands = 10 s stim windows; grey = control)")
    fig.suptitle("0714 single-color: representative ROI traces — 6 stim recordings + control",
                 y=0.995, fontsize=10, weight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    OUT.mkdir(parents=True, exist_ok=True)
    base = OUT / "fig_0714_A_example_traces"
    for ext, kw in [(".svg", {}), (".pdf", {}), (".png", {"dpi": 300})]:
        try: fig.savefig(base.with_suffix(ext), facecolor="white", **kw)
        except PermissionError: print(f"  locked: {base.with_suffix(ext).name}")
    plt.close(fig)
    return base.with_suffix(".svg")


# ----------------------------------------------------------------- Figure B
def collect_compare():
    """Per-ROI counts and per-event amps/lats for Control and Stim(pooled 6)."""
    out = {"Control": {"counts": [], "amps": [], "lats": []},
           "Stim": {"counts": [], "amps": [], "lats": []}}
    def add(label, path):
        tab, det = prep(path); sp = detect(tab, det)
        ti = tab["Time (s)"].to_numpy()
        for c in det:
            tms = sp.get(c, [])
            out[label]["counts"].append(len(tms))
            y = tab[c].to_numpy()
            for tt in tms:
                out[label]["amps"].append(float(y[np.argmin(np.abs(ti - tt))]))
        # latency is only defined for stimulated recordings (control has no stim)
        if label == "Stim":
            _, _, lat = bp.calculate_stim_onset_latencies(sp, WINDOWS, max_latency_window_s=60.0)
            if not lat.empty:
                out[label]["lats"].extend(lat["latency_s"].tolist())
    add("Control", CTRL_FILE)
    for f in STIM_FILES:
        add("Stim", f)
    return out


def figure_compare(data):
    metrics = [("counts", "Events / ROI", True), ("amps", "Event amplitude (dF/F)", True),
               ("lats", "Latency from onset (s)", False)]
    order = ["Control", "Stim"]
    colors = {"Control": "#7F7F7F", "Stim": STIM_COLOR}
    fig, axes = plt.subplots(1, 3, figsize=(8.6, 3.1))
    rng = np.random.default_rng(0)
    for ax, (key, ylabel, test_ctrl) in zip(axes, metrics):
        arrs = [np.asarray(data[o][key], float) for o in order]
        for x, (o, a) in enumerate(zip(order, arrs)):
            m = a.mean() if a.size else 0.0
            s = sps.sem(a) if a.size > 1 else 0.0
            if a.size == 0:
                ax.bar(x, 0, 0.6, facecolor="none", edgecolor=colors[o], hatch="///", lw=0.8)
                ax.text(x, 0, "n=0", ha="center", va="bottom", fontsize=6, color="#666")
            else:
                ax.bar(x, m, 0.6, color=colors[o], edgecolor="black", lw=0.7,
                       yerr=s, capsize=3, error_kw=dict(lw=0.7))
                ax.scatter(x + (rng.random(a.size) - 0.5) * 0.28, a, s=8, color="black",
                           alpha=0.35, linewidths=0, zorder=3)
        # significance Control vs Stim (count & amplitude)
        if test_ctrl and arrs[0].size and arrs[1].size:
            try:
                p = sps.mannwhitneyu(arrs[1], arrs[0], alternative="greater").pvalue
                top = max(a.max() for a in arrs if a.size)
                ax.plot([0, 0, 1, 1], [top*1.05, top*1.1, top*1.1, top*1.05], lw=0.7, c="black")
                star = "***" if p < 1e-3 else "**" if p < 1e-2 else "*" if p < 5e-2 else "ns"
                ax.text(0.5, top*1.1, f"{star}\np={p:.3g}", ha="center", va="bottom", fontsize=7)
            except ValueError:
                pass
        ax.set_xticks([0, 1]); ax.set_xticklabels(order)
        ax.set_ylabel(ylabel); ax.margins(x=0.2)
    fig.suptitle("0714 single-color: control vs red-uLED stimulation", y=1.0,
                 fontsize=10, weight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    OUT.mkdir(parents=True, exist_ok=True)
    base = OUT / "fig_0714_B_control_vs_stim"
    for ext, kw in [(".svg", {}), (".pdf", {}), (".png", {"dpi": 300})]:
        try: fig.savefig(base.with_suffix(ext), facecolor="white", **kw)
        except PermissionError: print(f"  locked: {base.with_suffix(ext).name}")
    plt.close(fig)
    # stats table
    rows = []
    for o in order:
        for key, ylabel, _ in metrics:
            a = np.asarray(data[o][key], float)
            rows.append({"group": o, "metric": key, "n": a.size,
                         "mean": a.mean() if a.size else np.nan,
                         "median": np.median(a) if a.size else np.nan})
    pd.DataFrame(rows).to_csv(OUT / "fig_0714_stats.csv", index=False)
    return base.with_suffix(".svg")


def main():
    a = figure_traces()
    data = collect_compare()
    b = figure_compare(data)
    print("Control events/ROI mean:", np.mean(data["Control"]["counts"]),
          "| total control events:", int(np.sum(data["Control"]["counts"])))
    print("Stim events/ROI mean:", round(np.mean(data["Stim"]["counts"]), 3),
          "| total stim events:", int(np.sum(data["Stim"]["counts"])))
    print("wrote:", a)
    print("wrote:", b)


if __name__ == "__main__":
    main()
