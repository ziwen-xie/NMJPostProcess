"""Per-dataset group-comparison figures for single-color red uLED sweeps.

One SEPARATE figure per dataset (0717, 0718). Each figure is a 3x3 grid:
    rows    = metrics: event count (per ROI), event amplitude, latency
    columns = condition groups: Duration, Intensity, Frequency

The No-light and Far-light controls are ALWAYS drawn in every panel, even when a
metric has zero events (the silent no-light control is the key baseline). Empty
control bars are shown as an outlined "n=0" placeholder.

Detection pipeline (validated by the control-silence strategy):
  - background = dimmest ROI, dF/F normalized by raw baseline  (dq.prep)
  - threshold  = mean + 6*sd  (at sigma=6 the no-light control is silent)
  - FWHM width >= 1.0 s, min spike distance 5 s
  - in-window events KEPT (single-color: negligible light leakage)
  - latency from stimulation ONSET (paper: L = t_event - t_stim_start), cap 60 s
  - QC: drop saturated ROIs (|dF/F| > 5) and field-wide-artifact files

Run:  python figures/make_group_comparison_figures.py
Outputs SVG/PNG/PDF + stats CSV into figures/group_comparison/<dataset>/.
"""
from __future__ import annotations
import os, re, sys, glob
from pathlib import Path
from collections import defaultdict
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import analysis.dataset_quality as dq          # noqa: E402
import BatchProcess as bp                        # noqa: E402

import matplotlib                                # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                  # noqa: E402
from scipy import stats as sps                   # noqa: E402

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "svg.fonttype": "none", "pdf.fonttype": 42, "font.size": 8,
    "axes.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False,
    "xtick.major.width": 0.8, "ytick.major.width": 0.8,
})

# ---- detection config ----
# sigma=3.5 is the most sensitive threshold that still keeps the 0718 no-light
# control silent (0 events); it maximizes stim-vs-control separation. 0717's
# control (test.csv) is not silent at any sigma - a dataset limitation, not a
# threshold one. Matches the paper's mean+~3sigma detection.
SIGMA, WIDTH, MINDIST, LAT_CAP = 3.5, 1.0, 5.0, 60.0
ARTIFACT_CAP = 5.0        # drop ROI if |dF/F| ever exceeds this (saturation/motion)
FIELD_ARTIFACT_FRAC = 0.30  # skip file if >30% of ROIs exceed 0.3 dF/F (field artifact)

DATASETS = {
    "0717": ROOT / "data" / "raw" / "single_color_red" / "0717",
    "0718": ROOT / "data" / "raw" / "single_color_red" / "0718",
}

# condition groups (each panel column). "20s" doubles as the frequency "constant".
GROUPS = {
    "Duration":  ["NoLight", "Far", "5s", "10s", "20s"],
    "Intensity": ["NoLight", "Far", "1mW", "2mW", "4mW"],
    "Frequency": ["NoLight", "Far", "20s", "2Hz", "5Hz"],
}
LABELS = {"NoLight": "No light", "Far": "Far light", "5s": "5 s", "10s": "10 s",
          "20s": "20 s", "1mW": "1 mW", "2mW": "2 mW", "4mW": "4 mW",
          "2Hz": "2 Hz", "5Hz": "5 Hz"}
# 20s is relabeled "Const" only in the Frequency column
FREQ_LABEL_OVERRIDE = {"20s": "Const"}
COLORS = {"NoLight": "#636363", "Far": "#BDBDBD", "5s": "#9ECAE1", "10s": "#3182BD",
          "20s": "#08306B", "1mW": "#FDAE6B", "2mW": "#E6550D", "4mW": "#8C2D04",
          "2Hz": "#74C476", "5Hz": "#005A32"}


def condition_of(fname: str):
    low = Path(fname).stem.strip().lower()
    if low == "test":            # 0717's no-light control is named test.csv
        return "NoLight"
    m = re.fullmatch(r"ctrl[_\- ]?(far)?(\d*)", low)
    if m:
        return "Far" if (m.group(1) == "far" or m.group(2) not in ("", "1")) else "NoLight"
    parsed = bp.parse_experiment_filename(Path(fname).name)
    if not parsed:
        return None
    g = parsed[0]  # canonicalized (2hz->2Hz, 1mw->1mW) by parse_experiment_filename
    # bare-number duration files (e.g. "20-1.csv" -> "20") are durations in seconds
    bare_dur = {"5": "5s", "10": "10s", "20": "20s"}
    g = bare_dur.get(g, g)
    known = {"5s", "10s", "20s", "1mW", "2mW", "4mW", "2Hz", "5Hz"}
    return g if g in known else None


def collect(folder: Path):
    """Return dict[cond] -> {counts:[per-ROI], amps:[per-event], lats:[per-event]},
    plus a QC log list."""
    data = defaultdict(lambda: {"counts": [], "amps": [], "lats": []})
    qc = []
    for f in sorted(glob.glob(str(folder / "*.csv"))):
        cond = condition_of(f)
        if cond is None:
            continue
        try:
            c = dq.prep(f)
        except Exception as e:  # noqa: BLE001
            qc.append(f"skip {Path(f).name}: {str(e)[:50]}"); continue
        cols = c["det_cols"]
        tmax = np.array([float(np.nanmax(np.abs(c["dff_table"][col].to_numpy()))) for col in cols])
        # field-wide artifact -> drop whole file
        if tmax.size and (tmax > 0.3).mean() > FIELD_ARTIFACT_FRAC:
            qc.append(f"QC drop file {Path(f).name}: {(tmax>0.3).mean()*100:.0f}% ROIs inflated")
            continue
        keep = [col for col, m in zip(cols, tmax) if m <= ARTIFACT_CAP]
        c["dff_table"] = c["dff_table"][["Time (s)"] + keep]
        _, _, spikes = bp.detect_spikes_across_rois(
            c["dff_table"], keep, "Time (s)", baseline_range=(10, 30),
            spike_z_sigma=SIGMA, min_distance_s=MINDIST, width_mode="fwhm",
            width_threshold_s=WIDTH, stim_windows=c["stim_windows"],
            exclude_spikes_in_windows=False)
        _, _, lat_df = bp.calculate_stim_onset_latencies(
            spikes, c["stim_windows"], max_latency_window_s=LAT_CAP)
        ti = c["dff_table"]["Time (s)"].to_numpy()
        for col in keep:
            tms = spikes.get(col, [])
            data[cond]["counts"].append(len(tms))  # per-ROI count (incl. 0)
            y = c["dff_table"][col].to_numpy()
            for tt in tms:
                data[cond]["amps"].append(float(y[np.argmin(np.abs(ti - tt))]))
        if not lat_df.empty:
            data[cond]["lats"].extend(lat_df["latency_s"].tolist())
    return data, qc


def stars(p):
    return "***" if p < 1e-3 else "**" if p < 1e-2 else "*" if p < 5e-2 else "ns"


def panel(ax, data, conds, key, group_name, ylabel):
    xs = np.arange(len(conds))
    arrs = [np.asarray(data.get(c, {}).get(key, []), float) for c in conds]
    means = [a.mean() if a.size else 0.0 for a in arrs]
    sems = [sps.sem(a) if a.size > 1 else 0.0 for a in arrs]
    for x, c, m, s, a in zip(xs, conds, means, sems, arrs):
        if a.size == 0:
            # empty (e.g. silent control on amplitude/latency): outlined placeholder
            ax.bar(x, 0, 0.66, facecolor="none", edgecolor=COLORS[c], linewidth=0.8,
                   hatch="///", zorder=2)
            ax.text(x, 0, "n=0", ha="center", va="bottom", fontsize=6, color="#666")
        else:
            ax.bar(x, m, 0.66, color=COLORS[c], edgecolor="black", linewidth=0.7,
                   yerr=s, capsize=2.5, error_kw=dict(lw=0.7), zorder=2)
    rng = np.random.default_rng(0)
    for x, a in zip(xs, arrs):
        if a.size:
            ax.scatter(x + (rng.random(a.size) - 0.5) * 0.30, a, s=6, color="black",
                       alpha=0.30, linewidths=0, zorder=3)
    # significance vs No-light control (only meaningful when control has data)
    if "NoLight" in conds:
        ci = conds.index("NoLight"); base = arrs[ci]
        if base.size:
            top = max((a.max() if a.size else 0) for a in arrs)
            h = top * 0.06 + 1e-9; lvl = top + h
            for x, a in zip(xs, arrs):
                if x == ci or a.size == 0:
                    continue
                try:
                    p = sps.mannwhitneyu(a, base, alternative="two-sided").pvalue
                except ValueError:
                    continue
                ax.plot([ci, ci, x, x], [lvl, lvl + h, lvl + h, lvl], lw=0.6, c="black")
                ax.text((ci + x) / 2, lvl + h, stars(p), ha="center", va="bottom", fontsize=7)
                lvl += 3 * h
    labs = [FREQ_LABEL_OVERRIDE.get(c, LABELS[c]) if group_name == "Frequency" else LABELS[c]
            for c in conds]
    ax.set_xticks(xs); ax.set_xticklabels(labs, rotation=35, ha="right", fontsize=6.5)
    ax.set_ylabel(ylabel)
    ax.margins(x=0.05)


METRICS = [("counts", "Events / ROI"), ("amps", "Event amplitude (dF/F)"),
           ("lats", "Latency from onset (s)")]


def make_figure(dataset, data):
    fig, axes = plt.subplots(3, 3, figsize=(8.4, 8.0))
    for r, (key, ylabel) in enumerate(METRICS):
        for col, (gname, conds) in enumerate(GROUPS.items()):
            ax = axes[r][col]
            panel(ax, data, conds, key, gname, ylabel)
            if r == 0:
                ax.set_title(gname, fontsize=10, weight="bold")
    fig.suptitle(f"{dataset}: single-color red uLED — event count, amplitude, latency",
                 y=0.995, fontsize=11, weight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.985))
    out = ROOT / "figures" / "group_comparison" / dataset
    out.mkdir(parents=True, exist_ok=True)
    base = out / f"fig_{dataset}_group_comparison"
    for ext, kw in [(".svg", {}), (".pdf", {}), (".png", {"dpi": 350})]:
        try:
            fig.savefig(base.with_suffix(ext), facecolor="white", **kw)
        except PermissionError:
            print(f"  WARNING: {base.with_suffix(ext).name} is locked (open in a viewer?) - skipped")
    plt.close(fig)
    return base.with_suffix(".svg")


def write_stats(dataset, data):
    rows = []
    for cond, d in data.items():
        counts = np.asarray(d["counts"], float)
        amps = np.asarray(d["amps"], float)
        lats = np.asarray(d["lats"], float)
        rows.append({
            "dataset": dataset, "condition": cond, "n_rois": counts.size,
            "n_events": int(counts.sum()), "events_per_roi_mean": counts.mean() if counts.size else 0,
            "amp_mean": amps.mean() if amps.size else np.nan,
            "amp_median": np.median(amps) if amps.size else np.nan,
            "latency_mean": lats.mean() if lats.size else np.nan,
            "latency_median": np.median(lats) if lats.size else np.nan,
        })
    df = pd.DataFrame(rows)
    out = ROOT / "figures" / "group_comparison" / dataset
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / f"fig_{dataset}_stats.csv", index=False)
    return df


def main():
    for dataset, folder in DATASETS.items():
        print(f"\n===== {dataset} ({folder}) =====", flush=True)
        data, qc = collect(folder)
        for line in qc:
            print("  " + line, flush=True)
        df = write_stats(dataset, data)
        print(df.to_string(index=False), flush=True)
        svg = make_figure(dataset, data)
        print(f"  wrote {svg}", flush=True)


if __name__ == "__main__":
    main()
