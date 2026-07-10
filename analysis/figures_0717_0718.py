"""Publication figures for 0717 + 0718 single-color red uLED sweeps.

Compares event count, amplitude, and latency across three condition groups
(duration, intensity, frequency), with no-light and far-light controls.

Pipeline (all defaults from the tuned BatchProcess config):
  - background = dimmest ROI, ΔF/F normalized by raw baseline
  - detection: mean + 6*sd threshold (validated: no-light control is silent),
    FWHM width >= 1.0 s, min spike distance 5 s
  - in-window events KEPT (single-color: continuous-stim responses count)
  - latency measured from stimulation ONSET (paper: L = t_event - t_stim_start),
    excluded above 60 s

Run:  python analysis/figures_0717_0718.py
Outputs SVG+PNG into figures/0717_0718_publication/.
"""
import os, sys, glob
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.abspath("."))
import analysis.dataset_quality as dq
import BatchProcess as bp

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats as sps

plt.rcParams.update({
    "font.family": "Arial", "svg.fonttype": "none", "pdf.fonttype": 42,
    "font.size": 9, "axes.linewidth": 0.8, "axes.spines.top": False,
    "axes.spines.right": False, "xtick.major.width": 0.8, "ytick.major.width": 0.8,
})

# sigma=3.5 is the lowest threshold at which the no-light control stays silent
# (0 spikes) — maximizes sensitivity to evoked events per the control-based strategy.
SIGMA, WIDTH, MINDIST, EXCLUDE = 3.5, 1.0, 5.0, "none"
# QC: drop ROIs whose ΔF/F ever exceeds this (saturation / motion artifacts; real
# GCaMP transients here are <0.1, artifacts blow up to ~20 = 2000%).
ARTIFACT_CAP = 5.0
DATASETS = ["data/raw/single_color_red/0717", "data/raw/single_color_red/0718"]

# map raw parsed group -> canonical condition label
DUR = {"5s": "5s", "5": "5s", "10s": "10s", "10": "10s", "20s": "20s", "20": "20s"}
INT = {"1mW": "1mW", "2mW": "2mW", "4mW": "4mW"}
FRQ = {"2Hz": "2Hz", "5Hz": "5Hz"}          # + constant (20s) added below
CTRL_NL, CTRL_FL = "No-light", "Far-light"

COLORS = {
    "No-light": "#636363", "Far-light": "#BDBDBD",
    "5s": "#9ECAE1", "10s": "#3182BD", "20s": "#08306B",
    "1mW": "#FDAE6B", "2mW": "#E6550D", "4mW": "#8C2D04",
    "constant": "#08306B", "2Hz": "#74C476", "5Hz": "#005A32",
}


def condition_of(fname):
    """Return canonical condition label for a file, or None to skip."""
    import re
    low = Path(fname).stem.strip().lower()
    # controls: Ctrl/Ctrl1 = no-light; Ctrl2/Ctrl3/Ctrl_far = far-light
    m = re.fullmatch(r"ctrl[_\- ]?(far)?(\d*)", low)
    if m:
        return CTRL_FL if (m.group(1) == "far" or m.group(2) not in ("", "1")) else CTRL_NL
    parsed = bp.parse_experiment_filename(Path(fname).name)
    if parsed is None:
        return None
    g = parsed[0]
    if g in DUR:
        return DUR[g]
    if g in INT:
        return INT[g]
    if g in FRQ:
        return FRQ[g]
    return None  # blue/test/bg etc. skipped


def collect():
    """Return dict[label] -> {counts:[per-ROI], amps:[per-event], lats:[per-event]}."""
    from collections import defaultdict
    data = defaultdict(lambda: {"counts": [], "amps": [], "lats": []})
    for ds in DATASETS:
        for f in sorted(glob.glob(os.path.join(ds, "*.csv"))):
            lab = condition_of(f)
            if lab is None:
                continue
            try:
                c = dq.prep(f)
            except Exception as e:  # noqa
                print("  [skip]", Path(f).name, str(e)[:50]); continue
            # QC: reject whole file if a field-wide bright artifact is present
            # (normal files have ~0% of ROIs above 0.3 ΔF/F; corrupted ones ~90%).
            tmax = np.array([float(np.nanmax(c["dff_table"][col].to_numpy())) for col in c["det_cols"]])
            if tmax.size and (tmax > 0.3).mean() > 0.30:
                print(f"  [QC] SKIP {Path(f).parent.name}/{Path(f).name}: "
                      f"field-wide artifact ({(tmax>0.3).mean()*100:.0f}% ROIs inflated)")
                continue
            ex = bp.should_exclude_spikes_in_stim(EXCLUDE, f)
            _, _, spikes = bp.detect_spikes_across_rois(
                c["dff_table"], c["det_cols"], "Time (s)", baseline_range=(10, 30),
                spike_z_sigma=SIGMA, min_distance_s=MINDIST, width_mode="fwhm",
                width_threshold_s=WIDTH, stim_windows=c["stim_windows"],
                exclude_spikes_in_windows=ex)
            _, _, lat_detailed = bp.calculate_stim_onset_latencies(
                spikes, c["stim_windows"], max_latency_window_s=60.0)
            ti = c["dff_table"]["Time (s)"].to_numpy()
            for col, tms in spikes.items():
                data[lab]["counts"].append(len(tms))
                y = c["dff_table"][col].to_numpy()
                for tt in tms:
                    data[lab]["amps"].append(float(y[np.argmin(np.abs(ti - tt))]))
            if not lat_detailed.empty:
                data[lab]["lats"].extend(lat_detailed["latency_s"].tolist())
            # 20s constant also feeds the frequency group as "constant"
            if lab == "20s":
                data["constant"]["counts"].extend([len(v) for v in spikes.values()])
                for col, tms in spikes.items():
                    y = c["dff_table"][col].to_numpy()
                    for tt in tms:
                        data["constant"]["amps"].append(float(y[np.argmin(np.abs(ti - tt))]))
                if not lat_detailed.empty:
                    data["constant"]["lats"].extend(lat_detailed["latency_s"].tolist())
    return data


def stars(p):
    return "***" if p < 1e-3 else "**" if p < 1e-2 else "*" if p < 5e-2 else "ns"


def panel(ax, data, order, key, ylabel, title, ctrl_ref="No-light"):
    xs = list(range(len(order)))
    means, sems, arrs = [], [], []
    for lab in order:
        a = np.array(data.get(lab, {}).get(key, []), float)
        arrs.append(a)
        means.append(np.mean(a) if a.size else 0.0)
        sems.append(sps.sem(a) if a.size > 1 else 0.0)
    for x, lab, m, s in zip(xs, order, means, sems):
        ax.bar(x, m, 0.68, color=COLORS.get(lab, "#888"), edgecolor="black",
               linewidth=0.8, yerr=s, capsize=3, error_kw=dict(lw=0.8), zorder=2)
    rng = np.random.default_rng(0)
    for x, a in zip(xs, arrs):
        if a.size:
            jx = x + (rng.random(a.size) - 0.5) * 0.28
            ax.scatter(jx, a, s=7, color="black", alpha=0.35, linewidths=0, zorder=3)
    # significance vs control reference (if present in this panel)
    if ctrl_ref in order:
        ci = order.index(ctrl_ref)
        base = arrs[ci]
        top = max((a.max() if a.size else 0) for a in arrs)
        h = top * 0.06 + 1e-6
        lvl = top + h
        for x, lab, a in zip(xs, order, arrs):
            if lab == ctrl_ref or a.size == 0 or base.size == 0:
                continue
            try:
                p = sps.mannwhitneyu(a, base, alternative="two-sided").pvalue
            except ValueError:
                continue
            ax.plot([ci, ci, x, x], [lvl, lvl + h, lvl + h, lvl], lw=0.7, c="black")
            ax.text((ci + x) / 2, lvl + h, stars(p), ha="center", va="bottom", fontsize=8)
            lvl += 3 * h
    ax.set_xticks(xs); ax.set_xticklabels(order, rotation=0)
    ax.set_ylabel(ylabel); ax.set_title(title, fontsize=10, weight="bold")
    ax.margins(x=0.04)


def make_figure(data, groupname, stim_labels, fname):
    # count panel includes controls; amp/lat panels use far-light + stim (control has ~no events)
    count_order = [CTRL_NL, CTRL_FL] + stim_labels
    al_order = [CTRL_FL] + stim_labels
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.4))
    panel(axes[0], data, count_order, "counts", "Events per ROI",
          f"{groupname} — Event count", ctrl_ref=CTRL_NL)
    panel(axes[1], data, al_order, "amps", "Peak ΔF/F",
          f"{groupname} — Amplitude", ctrl_ref=CTRL_FL)
    panel(axes[2], data, al_order, "lats", "Latency (s)",
          f"{groupname} — Latency", ctrl_ref=CTRL_FL)
    fig.tight_layout()
    outdir = Path("figures/0717_0718_publication"); outdir.mkdir(parents=True, exist_ok=True)
    fig.savefig(outdir / f"{fname}.svg")
    fig.savefig(outdir / f"{fname}.png", dpi=300)
    plt.close(fig)
    print(f"  wrote {outdir/fname}.svg/.png")


def main():
    print("Collecting events from 0717 + 0718 ...", flush=True)
    data = collect()
    print("\nPer-condition summary (pooled 0717+0718):")
    print(f"{'condition':<12} {'ROIs':>5} {'events':>7} {'ev/ROI':>7} {'medAmp':>7} {'medLat':>7}")
    for lab in [CTRL_NL, CTRL_FL, "5s", "10s", "20s", "1mW", "2mW", "4mW", "constant", "2Hz", "5Hz"]:
        d = data.get(lab, {"counts": [], "amps": [], "lats": []})
        nroi = len(d["counts"]); ev = int(np.sum(d["counts"]))
        evroi = ev / nroi if nroi else 0
        ma = np.median(d["amps"]) if d["amps"] else 0
        ml = np.median(d["lats"]) if d["lats"] else 0
        print(f"{lab:<12} {nroi:>5} {ev:>7} {evroi:>7.2f} {ma:>7.3f} {ml:>7.1f}")
    print("\nGenerating figures ...")
    make_figure(data, "Duration", ["5s", "10s", "20s"], "fig_duration")
    make_figure(data, "Intensity", ["1mW", "2mW", "4mW"], "fig_intensity")
    make_figure(data, "Frequency", ["constant", "2Hz", "5Hz"], "fig_frequency")
    print("done.")


if __name__ == "__main__":
    main()
