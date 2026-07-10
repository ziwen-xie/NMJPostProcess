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
BASE_RANGE, SIGMA, MIN_DIST, EXCLUDE_STIM = (10, 30), 3.0, 5.0, "all"


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
    exclude = bp.should_exclude_spikes_in_stim(EXCLUDE_STIM, cache["path"])
    _, _, spikes = bp.detect_spikes_across_rois(
        dff_table=cache["dff_table"], roi_cols=cache["det_cols"], time_col="Time (s)",
        baseline_range=BASE_RANGE, spike_z_sigma=SIGMA, min_distance_s=MIN_DIST,
        width_mode="fwhm", width_threshold_s=width_threshold,
        stim_windows=cache["stim_windows"], exclude_spikes_in_windows=exclude)
    n_ev = int(sum(len(v) for v in spikes.values()))
    n_resp = int(sum(1 for v in spikes.values() if len(v) > 0))
    return n_ev, n_resp, len(cache["det_cols"])


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
            ne, nr, _ = detect(c, thr)
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
        acc = dict(stim_ev=0, ctrl_ev=0, stim_roi=0, stim_resp=0, ctrl_roi=0,
                   ctrl_resp=0, neg=0, tot=0, nfiles=0, conds=set())
        for _, c in iter_caches([fol]):
            acc["nfiles"] += 1
            acc["conds"].add(c["group"])
            acc["neg"] += c["n_neg_f0"]; acc["tot"] += c["n_roi"]
            ne, nr, nd = detect(c, width)
            if is_ctrl(c["group"]):
                acc["ctrl_ev"] += ne; acc["ctrl_roi"] += nd; acc["ctrl_resp"] += nr
            else:
                acc["stim_ev"] += ne; acc["stim_roi"] += nd; acc["stim_resp"] += nr
        if acc["nfiles"] == 0:
            continue
        ev_ratio = acc["stim_ev"] / acc["ctrl_ev"] if acc["ctrl_ev"] else float("inf")
        n_conds = len([g for g in acc["conds"] if not is_ctrl(g)])
        rows.append(dict(exp_type=exp_type, name=name, ev_ratio=ev_ratio,
                         neg_pct=100 * acc["neg"] / max(acc["tot"], 1), n_conds=n_conds, **acc))

    def score(r):
        # Reward stim:control event ratio, condition breadth, and enough events.
        # neg_pct is reported for context but not penalized: once ΔF/F is
        # normalized by the raw baseline, a bright background (negative corrected
        # baseline) no longer distorts the traces.
        er = min(r["ev_ratio"], 20) if np.isfinite(r["ev_ratio"]) else 20
        return er * 2 + r["n_conds"] * 2 + min(r["stim_ev"], 500) / 100

    rows.sort(key=score, reverse=True)
    print(f"\n===== DATASET RANKING (width={width}s, by stim:control event ratio + coverage) =====", flush=True)
    print(f"{'#':>3} {'type':<17} {'folder':<11} {'files':>5} {'stimEv':>6} {'ctrlEv':>6} "
          f"{'evRatio':>7} {'#cond':>5} {'neg%':>5}", flush=True)
    for i, r in enumerate(rows, 1):
        er = f"{r['ev_ratio']:.1f}" if np.isfinite(r["ev_ratio"]) else "inf"
        print(f"{i:>3} {r['exp_type']:<17} {r['name']:<11} {r['nfiles']:>5} {r['stim_ev']:>6} "
              f"{r['ctrl_ev']:>6} {er:>7} {r['n_conds']:>5} {r['neg_pct']:>5.1f}", flush=True)


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
