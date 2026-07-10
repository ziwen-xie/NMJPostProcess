"""Dataset quality + width-threshold tooling for the NMJ pipeline.

Reuses BatchProcess internals to run event detection consistently across many
files, so you can (a) tune the FWHM width threshold and (b) rank experiment
folders by evoked-response quality.

Run from the repo root:

    python analysis/dataset_quality.py rank                       # rank all data/raw folders
    python analysis/dataset_quality.py rank --glob "data/raw/single_color_red/0806*"
    python analysis/dataset_quality.py width --glob "data/raw/single_color_red/0806*"

Detection settings below mirror nmj_config.json.
"""
import argparse
import glob
import os
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.abspath("."))
import BatchProcess as bp  # noqa: E402

TIME_COL, ROI_KEY = "Axis [s]", "ROI"
# SIGMA=6 and dimmest-ROI background (bp.detect_bg_column default) match the
# tuned pipeline. REAL_AMP flags events large enough to be genuine transients.
BASE_RANGE, SIGMA, MIN_DIST, EXCLUDE_STIM, REAL_AMP = (10, 30), 6.0, 5.0, "all", 0.05


def load_csv(path):
    """Robust loader: try common encodings, skipping the units header row."""
    last = None
    for enc in ("utf-16", "utf-8-sig", "utf-8", "latin-1"):
        try:
            df = pd.read_csv(path, encoding=enc, skiprows=1)
            if TIME_COL in df.columns and any(ROI_KEY in c for c in df.columns):
                return df
        except Exception as e:  # noqa: BLE001
            last = e
    raise last if last else ValueError("no time/ROI columns")


def prep(path):
    """Compute ΔF/F once for a file and return a cache dict."""
    cfg = bp.Config()
    cfg.csv_path = path
    cfg.time_col = TIME_COL
    cfg.roi_key = ROI_KEY
    cfg.stim_preset_infer_from_name = True
    bp.apply_inferred_stim_preset(cfg, name_hint=Path(path).name)
    df = load_csv(path)
    t = df[TIME_COL].to_numpy(dtype=float)
    roi_cols = bp.find_roi_columns(df, ROI_KEY)
    bg_name = bp.detect_bg_column(df, ROI_KEY)
    bg = df[bg_name].to_numpy(dtype=float)
    dff_dict, f0s = {}, {}
    for col in roi_cols:
        f_raw = df[col].to_numpy(dtype=float)
        f_corr = f_raw - bg
        dff, f0 = bp.dff_percentile_window(
            f_corr, t, cfg.baseline_window_half_s, cfg.baseline_percentile,
            F_denom=(f_raw if getattr(cfg, "dff_normalize_by_raw", True) else None))
        dff_dict[col] = dff
        f0s[col] = float(np.median(f0))
    dff_table = pd.DataFrame(dff_dict)
    dff_table.insert(0, "Time (s)", t)
    parsed = bp.parse_experiment_filename(Path(path).name)
    return {
        "path": path, "t": t, "dff_table": dff_table,
        "det_cols": [c for c in roi_cols if c != bg_name],
        "stim_windows": cfg.stim_windows, "group": parsed[0] if parsed else None,
        "n_neg_f0": int(sum(1 for v in f0s.values() if v < 0)), "n_roi": len(roi_cols),
    }


def is_ctrl(group):
    return group is not None and (str(group).lower().startswith("ctrl") or group == "Far Light Control")


def detect(cache, width_threshold):
    """Returns (n_events, n_responding_rois, n_det_cols, event_amplitudes)."""
    exclude = bp.should_exclude_spikes_in_stim(EXCLUDE_STIM, cache["path"])
    _, _, spikes = bp.detect_spikes_across_rois(
        dff_table=cache["dff_table"], roi_cols=cache["det_cols"], time_col="Time (s)",
        baseline_range=BASE_RANGE, spike_z_sigma=SIGMA, min_distance_s=MIN_DIST,
        width_mode="fwhm", width_threshold_s=width_threshold,
        stim_windows=cache["stim_windows"], exclude_spikes_in_windows=exclude)
    ti = cache["dff_table"]["Time (s)"].to_numpy()
    amps = []
    for col, tms in spikes.items():
        if len(tms):
            y = cache["dff_table"][col].to_numpy()
            for tt in tms:
                amps.append(float(y[np.argmin(np.abs(ti - tt))]))
    n_ev = int(sum(len(v) for v in spikes.values()))
    n_resp = int(sum(1 for v in spikes.values() if len(v) > 0))
    return n_ev, n_resp, len(cache["det_cols"]), amps


def iter_caches(folders):
    for fol in folders:
        for f in sorted(glob.glob(os.path.join(fol, "*.csv"))):
            if bp.parse_experiment_filename(Path(f).name) is None:
                continue
            try:
                yield fol, prep(f)
            except Exception as e:  # noqa: BLE001
                print(f"  [skip] {Path(f).name}: {str(e)[:60]}", flush=True)


def cmd_width(folders, thresholds):
    caches = [c for _, c in iter_caches(folders)]
    print(f"prepped {len(caches)} files", flush=True)
    print(f"\n{'thr':>5} | {'stim_ev':>7} {'ctrl_ev':>7} {'ratio':>6} | {'stimROI':>7} {'ctrlROI':>7}", flush=True)
    for thr in thresholds:
        se = ce = sr = cr = 0
        for c in caches:
            ne, nr, _, _ = detect(c, thr)
            if is_ctrl(c["group"]):
                ce += ne; cr += nr
            else:
                se += ne; sr += nr
        ratio = (se / ce) if ce else float("inf")
        print(f"{thr:5.1f} | {se:7d} {ce:7d} {ratio:6.2f} | {sr:7d} {cr:7d}", flush=True)


def cmd_rank(folders, width):
    rows = []
    for fol in folders:
        exp_type, name = Path(fol).parent.name, Path(fol).name
        acc = dict(stim_ev=0, ctrl_ev=0, stim_real=0, ctrl_real=0, nfiles=0, conds=set())
        amps = []
        for _, c in iter_caches([fol]):
            acc["nfiles"] += 1
            acc["conds"].add(c["group"])
            ne, nr, nd, ea = detect(c, width)
            real = sum(1 for a in ea if a >= REAL_AMP)
            if is_ctrl(c["group"]):
                acc["ctrl_ev"] += ne; acc["ctrl_real"] += real
            else:
                acc["stim_ev"] += ne; acc["stim_real"] += real; amps.extend(ea)
        if acc["nfiles"] == 0:
            continue
        # ratio uses REAL (large-amplitude) events, which reflect true transients
        real_ratio = acc["stim_real"] / acc["ctrl_real"] if acc["ctrl_real"] else (
            float("inf") if acc["stim_real"] else 0.0)
        med_amp = float(np.median([a for a in amps if a >= REAL_AMP])) if any(a >= REAL_AMP for a in amps) else 0.0
        n_conds = len([g for g in acc["conds"] if not is_ctrl(g)])
        rows.append(dict(exp_type=exp_type, name=name, real_ratio=real_ratio,
                         med_amp=med_amp, n_conds=n_conds, **acc))

    def score(r):
        rr = min(r["real_ratio"], 20) if np.isfinite(r["real_ratio"]) else 20
        return r["stim_real"] + rr * 3 + r["n_conds"] * 3

    rows.sort(key=score, reverse=True)
    print(f"\n===== DATASET RANKING (width={width}s, sigma={SIGMA}, real events >= {REAL_AMP:.0%} dF/F) =====", flush=True)
    print(f"{'#':>3} {'type':<17} {'folder':<11} {'files':>5} {'stimReal':>8} {'ctrlReal':>8} "
          f"{'ratio':>6} {'medAmp':>6} {'#cond':>5}", flush=True)
    for i, r in enumerate(rows, 1):
        rr = f"{r['real_ratio']:.1f}" if np.isfinite(r["real_ratio"]) else "inf"
        print(f"{i:>3} {r['exp_type']:<17} {r['name']:<11} {r['nfiles']:>5} {r['stim_real']:>8} "
              f"{r['ctrl_real']:>8} {rr:>6} {r['med_amp']:>6.2f} {r['n_conds']:>5}", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["width", "rank"])
    ap.add_argument("--glob", default="data/raw/*/*", help="folder glob (default: all raw folders)")
    ap.add_argument("--width", type=float, default=1.0, help="FWHM width threshold for rank mode")
    args = ap.parse_args()
    folders = sorted(f for f in glob.glob(args.glob) if os.path.isdir(f))
    if not folders:
        print(f"No folders match {args.glob!r}")
        return
    if args.mode == "width":
        cmd_width(folders, [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0])
    else:
        cmd_rank(folders, args.width)


if __name__ == "__main__":
    main()
