# -*- coding: utf-8 -*-
"""
ΔF/F processing + 10 s spike detection + plot with red stim windows
- Baseline: first 59 frames
- Spike rule: peak-to-peak change > threshold within a sliding time window
- Labels shown ABOVE the plot; legend is the normal in-figure legend
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.signal import find_peaks, peak_widths
from datetime import datetime

from scipy.signal import savgol_filter, butter, filtfilt
# ========================= m
00
# USER SETTINGS
# =========================
CSV_PATH = "./0806/blue3.csv"          # <-- put your CSV name here
ENCODING = "utf-16"                  # files from UV-3600/Fiji often are UTF-16
SKIP_FIRST_ROW = True                # first line is "Channel.001" in your files
TIME_COL_NAME = "Axis [s]"           # time column name in your CSV
ROI_KEY = "ROI"                      # columns containing this substring are ROIs

CONTROL_CSV_PATH = "./0826/Ctrl.csv"  # path to control CSV (same format as experiment)
CONTROL_SEGMENT_S = (0.0, 30.0)                    # time window in control used to estimate noise
CONTROL_POOL_MODE = "mad"                          # "mad" (robust) or "std"
CONTROL_AGG = "mean"                             # aggregate ROI σ via "median" or "mean"
PROM_FROM_CONTROL = True                           # also scale min_prominence from control?
PROM_FACTOR = 1.0                                  # min_prominence = PROM_FACTOR * control_threshold



STIM_COLOR = "blue"
STIM_ALPHA = 0.30
ylim_max = 0.02

# ΔF/F baseline frames
BASELINE_FRAMES = 29                 # first 59 frames as baseline

# Spike detection parameters
WINDOW_SEC = 10                      # sliding window length in seconds
THRESHOLD = ylim_max/3                 # peak-to-peak threshold for "spike"

# Stimulation windows (seconds)
STIM_WINDOWS_20 = [(30, 50), (80, 100), (130, 150)]
STIM_WINDOWS_10 = [(30, 40), (70, 80), (110, 120)]
STIM_WINDOWS_5 = [(30, 35), (65, 70), (100, 105)]
STIM_WINDOWS_n = [(30, 40), (80, 90), (130, 140)]
STIM_WINDOWS = STIM_WINDOWS_20
# Output files
OUT_FIG = "deltaF_F_plot_10s_spikes_thr0015_red_labels_above_default_legend.png"
OUT_CSV = "spikes_10s_thr0015.csv"   # set to None if you don’t want a CSV

MASTER_CSV = "roi_spike_summary_master.csv"   # <- change path if you want
RUN_ID = Path(CSV_PATH).name                  # identify this run by input filename
RUN_TS = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ---- SciPy peak detection parameters (tune as needed) ----
MIN_PROMINENCE = 0.003     # ΔF/F min prominence for a peak (try 0.003–0.01)
MIN_HEIGHT     = 0    # ΔF/F min absolute height (None to disable)
MIN_DISTANCE_S = 5       # min peak-to-peak distance in seconds
PEAK_WIDTH_S   = 5     # optional: min width in seconds (None disables)
PLOT_PEAK_MARKERS = True   # show small markers at detected peaks

# ---- Smoothing parameters ----
SMOOTH_METHOD   = "butter"   # one of: "savgol", "moving_avg", "butter"
SMOOTH_WIN_S    = 4.0        # window length in seconds (for savgol/moving_avg)
SMOOTH_POLY     = 4          # Savitzky-Golay polynomial order (<= window_len-1)
BUTTER_CUTOFF_HZ = 0.9       # low-pass cutoff (Hz) if using "butter"
BUTTER_ORDER     = 2
PLOT_RAW_OVERLAY = True     # set True to show faint raw traces underneath

# =========================
# LOAD DATA
# =========================
def load_fluo_csv(path: str, encoding="utf-16", skip_first_row=True) -> pd.DataFrame:
    path = Path(path)
    if skip_first_row:
        return pd.read_csv(path, encoding=encoding, skiprows=1)
    else:
        # Try UTF-8 first, fallback to UTF-16
        try:
            return pd.read_csv(path)
        except UnicodeDecodeError:
            return pd.read_csv(path, encoding=encoding)

df = load_fluo_csv(CSV_PATH, encoding=ENCODING, skip_first_row=SKIP_FIRST_ROW)



def _ensure_dff_sm_from_csv(csv_path: str) -> tuple[pd.DataFrame, list[str]]:
    """Load a CSV like your experiment, compute ΔF/F, then smooth. Returns (dff_sm, roi_cols)."""
    _df = load_fluo_csv(csv_path, encoding=ENCODING, skip_first_row=SKIP_FIRST_ROW)
    if TIME_COL_NAME not in _df.columns:
        raise ValueError(f"[CONTROL] Time column '{TIME_COL_NAME}' not in {csv_path}")

    _time = _df[TIME_COL_NAME].values

    _roi_cols = [c for c in _df.columns if ROI_KEY in c]
    if not _roi_cols:
        raise ValueError(f"[CONTROL] No ROI columns found in {csv_path} containing '{ROI_KEY}'")

    # ΔF/F with your same method
    _dff_dict = {}
    for col in _roi_cols:
        _dff_vals, _ = compute_dff_8percent_15s(_df[col].to_numpy(), _time, window_half=15.0, perc=8.0)
        _dff_dict[col] = _dff_vals
    _dff_df = pd.DataFrame(_dff_dict)
    _dff_df.insert(0, "Time (s)", _time)

    # absolute (as you do)
    for col in _roi_cols:
        _dff_df[col] = np.abs(_dff_df[col])

    # smooth, using your selected method
    _dff_sm = smooth_dff(_dff_df, time_col="Time (s)", roi_columns=_roi_cols, method=SMOOTH_METHOD)
    return _dff_sm, _roi_cols

# >>> NEW: robust σ per ROI and pooled threshold
def _robust_sigma(x: np.ndarray, mode: str = "mad") -> float:
    """Return noise sigma estimate of x using MAD (default) or std."""
    x = np.asarray(x)
    if mode == "mad":
        med = np.median(x)
        mad = np.median(np.abs(x - med))
        return 1.4826 * mad  # Gaussian-consistent
    elif mode == "std":
        return float(np.std(x, ddof=1)) if x.size > 1 else float(np.std(x))
    else:
        raise ValueError("mode must be 'mad' or 'std'")

def compute_control_noise_threshold(
    control_csv_path: str,
    segment_s: tuple[float, float] = CONTROL_SEGMENT_S,
    sigma_mode: str = CONTROL_POOL_MODE,
    agg: str = CONTROL_AGG
) -> dict:
    """
    Loads control, computes ΔF/F and smoothing like experiment, then estimates noise σ from a time segment.
    Returns dict with per-ROI σ, pooled σ, and threshold = 2 * pooled σ.
    """
    dff_sm_c, roi_cols_c = _ensure_dff_sm_from_csv(control_csv_path)
    t = dff_sm_c["Time (s)"].to_numpy()
    mask = np.ones_like(t, dtype=bool)
    if segment_s is not None:
        s0, s1 = segment_s
        mask = (t >= s0) & (t <= s1)

    sigmas = {}
    for roi in roi_cols_c:
        sigmas[roi] = _robust_sigma(dff_sm_c.loc[mask, roi].to_numpy(), mode=sigma_mode)

    # pool across ROIs
    if agg == "median":
        pooled_sigma = float(np.median(list(sigmas.values())))
    elif agg == "mean":
        pooled_sigma = float(np.mean(list(sigmas.values())))
    else:
        raise ValueError("agg must be 'median' or 'mean'")

    threshold = 3.0 * pooled_sigma  # 2·SD rule
    return {
        "per_roi_sigma": sigmas,
        "pooled_sigma": pooled_sigma,
        "threshold_2sd": threshold,
        "segment": segment_s,
        "sigma_mode": sigma_mode,
        "agg": agg
    }

# >>> NEW: wrapper that runs detection using control-driven thresholds
def detect_spikes_with_control(
    dff_df: pd.DataFrame,
    time_col: str,
    roi_columns: list[str],
    control_csv_path: str,
    min_distance_s: float = MIN_DISTANCE_S,
    min_width_s = PEAK_WIDTH_S,
    base_min_prominence: float = MIN_PROMINENCE,
    prom_from_control: bool = PROM_FROM_CONTROL,
    prom_factor: float = PROM_FACTOR
):
    """
    Uses control to set min_height = 2*SD(control). Optionally sets min_prominence accordingly.
    Spikes are those peaks in experiment exceeding control 2·SD threshold.
    """
    ctrl = compute_control_noise_threshold(control_csv_path)
    control_thr = ctrl["threshold_2sd"]
    print(control_thr)

    min_height = control_thr
    min_prom = control_thr * prom_factor if prom_from_control else base_min_prominence

    return detect_peaks_scipy(
        dff_df=dff_df,
        time_col=time_col,
        roi_columns=roi_columns,
        min_prominence=min_prom,
        min_height=min_height,
        min_distance_s=min_distance_s,
        min_width_s=min_width_s
    ), ctrl

# Identify ROI columns & time column
roi_cols = [c for c in df.columns if ROI_KEY in c]
if TIME_COL_NAME not in df.columns:
    raise ValueError(f"Time column '{TIME_COL_NAME}' not found. Columns: {list(df.columns)}")

time = df[TIME_COL_NAME].values

def compute_dff_8percent_15s(F: np.ndarray, t: np.ndarray, window_half: float = 15.0, perc: float = 8.0):
    n = F.size
    F0 = np.zeros_like(F, dtype=float)
    for i in range(n):
        t0 = max(t[0], t[i] - window_half)
        t1 = min(t[-1], t[i] + window_half)
        idx = (t >= t0) & (t <= t1)
        F0[i] = np.percentile(F[idx], perc)
    dff = (F - F0) / F0
    return dff, F0

dff_dict = {}
for col in roi_cols:
    dff_vals, _ = compute_dff_8percent_15s(df[col].to_numpy(), time, window_half=15.0, perc=8.0)
    dff_dict[col] = dff_vals

dff_8pct_15s = pd.DataFrame(dff_dict)
dff_8pct_15s.insert(0, "Time (s)", time)

dff = dff_8pct_15s.copy()
for col in roi_cols:
    dff[col] = np.abs(dff[col])

# =========================
# SPIKE DETECTION (SciPy find_peaks)
# =========================
def _nan_safe(array):
    """Replace NaNs with linear interp; ends with nearest non-NaN."""
    x = np.arange(array.size)
    y = array.astype(float).copy()
    nans = np.isnan(y)
    if nans.any():
        y[nans] = np.interp(x[nans], x[~nans], y[~nans])
    return y

def _make_savgol_window(win_s, t, poly):
    # Convert seconds to nearest odd number of samples >= poly+2
    dt = np.median(np.diff(t))
    n = max(3, int(round(win_s / dt)))
    if n % 2 == 0:
        n += 1
    n = max(n, poly + 2 | 1)  # ensure odd and > poly
    if n % 2 == 0:
        n += 1
    return n

def _make_mavg_kernel(win_s, t):
    dt = np.median(np.diff(t))
    n = max(1, int(round(win_s / dt)))
    return max(1, n)

def _butter_lowpass(cutoff_hz, fs_hz, order):
    b, a = butter(order, cutoff_hz / (0.5 * fs_hz), btype='low', analog=False)
    return b, a

def smooth_dff(dff_df: pd.DataFrame,
               time_col: str,
               roi_columns: list[str],
               method: str = "savgol") -> pd.DataFrame:
    """
    Returns a copy of dff_df where ROI columns are smoothed.
    """
    t = dff_df[time_col].to_numpy()
    dt = np.median(np.diff(t))
    fs = 1.0 / dt
    out = dff_df.copy()

    if method == "savgol":
        win = _make_savgol_window(SMOOTH_WIN_S, t, SMOOTH_POLY)
        for roi in roi_columns:
            y = _nan_safe(out[roi].to_numpy())
            out[roi] = savgol_filter(y, window_length=win, polyorder=min(SMOOTH_POLY, win-1))
    elif method == "moving_avg":
        k = _make_mavg_kernel(SMOOTH_WIN_S, t)
        kernel = np.ones(k) / k
        for roi in roi_columns:
            y = _nan_safe(out[roi].to_numpy())
            # Centered moving average via same-length convolution padding
            pad = k // 2
            ypad = np.pad(y, (pad, pad), mode='edge')
            out[roi] = np.convolve(ypad, kernel, mode='valid')
    elif method == "butter":
        b, a = _butter_lowpass(BUTTER_CUTOFF_HZ, fs, BUTTER_ORDER)
        for roi in roi_columns:
            y = _nan_safe(out[roi].to_numpy())
            out[roi] = filtfilt(b, a, y, method="gust")
    else:
        raise ValueError("SMOOTH_METHOD must be one of: 'savgol', 'moving_avg', 'butter'")

    return out

# ---- Apply smoothing
dff_sm = smooth_dff(dff, time_col="Time (s)", roi_columns=roi_cols, method=SMOOTH_METHOD)

def _sec_to_samples(seconds: float, t: np.ndarray) -> int:
    """Convert seconds to nearest integer samples using median dt."""
    if seconds is None:
        return None
    if len(t) < 2:
        return 1
    dt = np.median(np.diff(t))
    return max(1, int(round(seconds / dt)))
def detect_peaks_scipy(
    dff_df,
    time_col,
    roi_columns,
    min_prominence = 0.004,
    min_height = 0.003,
    min_distance_s = 2.0,
    min_width_s = None
):
    """
    Detects peaks in ΔF/F using scipy.signal.find_peaks for each ROI.
    Returns dict[roi] -> pd.DataFrame with columns:
       ['time_s','amp','prom','left_ips_s','right_ips_s','width_s','index']
    """
    results = {}
    t = dff_df[time_col].to_numpy()
    distance = _sec_to_samples(min_distance_s, t)
    width = _sec_to_samples(min_width_s, t) if min_width_s is not None else None

    for roi in roi_columns:
        y = dff_df[roi].to_numpy()

        # find_peaks args (only pass height/width/distance if not None)
        kwargs = dict(prominence=min_prominence)
        if min_height is not None:
            kwargs["height"] = min_height
        if distance is not None:
            kwargs["distance"] = distance
        if width is not None:
            kwargs["width"] = width

        idx, props = find_peaks(y, **kwargs)

        # Peak widths in samples at half-prominence; convert to seconds
        if len(idx) > 0:
            w_results = peak_widths(y, idx, rel_height=0.5)
            widths_s = w_results[0] * np.median(np.diff(t))
            left_ips_s = w_results[2] * np.median(np.diff(t)) + t[0]
            right_ips_s = w_results[3] * np.median(np.diff(t)) + t[0]
        else:
            widths_s = np.array([])
            left_ips_s = np.array([])
            right_ips_s = np.array([])

        df_peaks = pd.DataFrame({
            "index": idx,
            "time_s": t[idx] if len(idx) else np.array([]),
            "amp": y[idx] if len(idx) else np.array([]),
            "prom": props.get("prominences", np.array([])),
            "left_ips_s": left_ips_s,
            "right_ips_s": right_ips_s,
            "width_s": widths_s,
        })
        results[roi] = df_peaks

    return results

def summarize_peak_counts(peaks_dict,
                          stim_windows=None,
                          exclude_before=30.0,
                          save_csv_path="spike_counts_summary.csv"):
    """
    peaks_dict: {roi: DataFrame from detect_peaks_scipy()}
    stim_windows: list[(s,e)] in seconds or None
    exclude_before: ignore peaks with time < this (s)
    """
    rows = []
    for roi, d in peaks_dict.items():
        if d.empty:
            rows.append({"ROI": roi, "n_spikes_all": 0, "n_spikes_in_stim": 0 if stim_windows else None,
                         "n_spikes_outside": 0 if stim_windows else None})
            continue

        d2 = d[d["time_s"] >= exclude_before].copy()

        if stim_windows:
            in_stim = 0
            for _, r in d2.iterrows():
                if any(ss <= r["time_s"] <= se for (ss, se) in stim_windows):
                    in_stim += 1
            out_stim = len(d2) - in_stim
        else:
            in_stim = None
            out_stim = None

        rows.append({
            "ROI": roi,
            "n_spikes_all": len(d2),
            "n_spikes_in_stim": in_stim,
            "n_spikes_outside": out_stim
        })

    summary = pd.DataFrame(rows).sort_values("ROI")
    summary.to_csv(save_csv_path, index=False)
    return summary

# ---- Run detection & summary ----
peaks, control_info = detect_spikes_with_control(
    dff_df=dff_sm,
    time_col="Time (s)",
    roi_columns=roi_cols,
    control_csv_path=CONTROL_CSV_PATH,
    min_distance_s=MIN_DISTANCE_S,
    min_width_s=PEAK_WIDTH_S,
    base_min_prominence=MIN_PROMINENCE,
    prom_from_control=PROM_FROM_CONTROL,
    prom_factor=PROM_FACTOR
)

print(f"[CONTROL] pooled σ = {control_info['pooled_sigma']:.6g}, 2·SD threshold = {control_info['threshold_2sd']:.6g}, segment={control_info['segment']}")

spike_summary = summarize_peak_counts(
    peaks_dict=peaks,
    stim_windows=STIM_WINDOWS,
    exclude_before=30.0,
    save_csv_path="spike_counts_summary.csv"
)
print(spike_summary)



# =========================
# PLOTTING (clean & readable)
# =========================
fig = plt.figure(figsize=(11, 6))
ax = fig.add_subplot(111)

# Choose which ROIs to show in legend: only those with peaks (fallback to all)
active_rois = [r for r in roi_cols if not peaks[r].empty]
if not active_rois:  # fallback if no peaks at all
    active_rois = roi_cols[:]

# Color map stays stable per ROI
colors = plt.cm.tab10.colors
color_map = {roi_cols[i]: colors[i % len(colors)] for i in range(len(roi_cols))}

# Robust y-limits (ignore extreme outliers)
all_vals = np.concatenate([dff[r].values for r in active_rois]) if active_rois else np.concatenate([dff[r].values for r in roi_cols])
y_lo = np.percentile(all_vals, 1)
y_hi = np.percentile(all_vals, 99)
if 'ylim_max' in globals() and ylim_max is not None:
    y_hi = min(y_hi, ylim_max)
y_lo = min(0, y_lo)  # keep 0 visible baseline

# Draw stimulation windows behind traces
for (s, e) in STIM_WINDOWS:
    ax.axvspan(s, e, color=STIM_COLOR, alpha=STIM_ALPHA, zorder=0)

# Plot ΔF/F traces once (thinner lines, slight alpha)
for col in roi_cols:
    ax.plot(
        dff_sm["Time (s)"], dff_sm[col],
        label=col if col in active_rois else None,     # only label active ones
        linewidth=1.1,
        alpha=0.9,
        color=color_map[col],
        zorder=1
    )
    # Optional raw overlay faint
    if PLOT_RAW_OVERLAY:
        ax.plot(dff["Time (s)"], dff[col], linewidth=0.8, alpha=0.25,
                color=color_map[col], zorder=0.8)

    # Peak markers for active ROIs
    df_peaks = peaks[col]
    if PLOT_PEAK_MARKERS and not df_peaks.empty:
        ax.scatter(
            df_peaks["time_s"].values,
            dff_sm.set_index("Time (s)").loc[df_peaks["time_s"].values, col].values,
            s=26, marker="o",
            facecolors="none", edgecolors=color_map[col],
            linewidths=1.0, alpha=0.95, zorder=2
        )

# Styling
ax.axhline(0, linestyle="--", linewidth=1, alpha=0.6, zorder=0.5)
ax.set_ylim(y_lo, y_hi)
ax.set_xlabel("Time (s)")
ax.set_ylabel("ΔF/F")
ax.set_title("ΔF/F with detected peaks")

# Light grid for readability
ax.grid(True, which="both", axis="both", alpha=0.25, linewidth=0.7)

# Legend outside (only active rois listed)
handles, labels = ax.get_legend_handles_labels()
if handles:
    ax.legend(handles, labels, loc="upper left", bbox_to_anchor=(1.02, 1),
              borderaxespad=0., frameon=False)

plt.tight_layout(rect=[0, 0, 0.85, 1])  # leave room for right-side legend
if OUT_FIG:
    plt.savefig(OUT_FIG, dpi=300, bbox_inches="tight")
plt.show()

def plot_summary_table(summary_df, title="Spike Summary", out_file="spike_summary_table.png"):
    fig, ax = plt.subplots(figsize=(6, 0.5 + 0.4*len(summary_df)))
    ax.axis("off")
    ax.axis("tight")

    # Convert DataFrame to table
    table = ax.table(
        cellText=summary_df.values,
        colLabels=summary_df.columns,
        loc="center",
        cellLoc="center"
    )

    # Style
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.2, 1.2)   # scale w,h
    ax.set_title(title, fontsize=12, pad=12)

    plt.tight_layout()
    if out_file:
        plt.savefig(out_file, dpi=300, bbox_inches="tight")
    plt.show()

# ---- call it ----
plot_summary_table(spike_summary, title="ΔF/F Peak Counts per ROI", out_file="summary_table.png")

def append_roi_table(summary_df: pd.DataFrame,
                     source_label: str = None,
                     master_path: str = MASTER_CSV) -> pd.DataFrame:
    """
    Append the per-run ROI table (summary_df) to a master CSV.
    Creates the file if it doesn't exist. Returns the updated master DataFrame.
    """
    df = summary_df.copy()
    # Keep zeros (don’t filter) so totals are accurate across runs
    df.insert(0, "source", source_label if source_label else RUN_ID)
    df.insert(1, "run_timestamp", RUN_TS)

    # Ensure ROI is string for consistent grouping later
    df["ROI"] = df["ROI"].astype(str)

    if Path(master_path).exists():
        master = pd.read_csv(master_path)
        # Align columns in case schema changes
        all_cols = list(dict.fromkeys(list(master.columns) + list(df.columns)))
        master = master.reindex(columns=all_cols)
        df = df.reindex(columns=all_cols)
        master = pd.concat([master, df], ignore_index=True)
    else:
        master = df

    master.to_csv(master_path, index=False)
    return master

def summarize_totals(master_path: str = MASTER_CSV) -> pd.DataFrame:
    """
    Read the master CSV and return totals per ROI:
    - n_spikes_all (sum across runs)
    - n_spikes_in_stim (sum)
    - n_spikes_outside (sum)
    - n_runs (how many runs contributed rows for that ROI)
    """
    if not Path(master_path).exists():
        raise FileNotFoundError(f"No master file found at {master_path}. Run append_roi_table() first.")

    master = pd.read_csv(master_path)

    # Ensure expected columns exist; if not, create as zeros for safety
    for col in ["n_spikes_all", "n_spikes_in_stim", "n_spikes_outside"]:
        if col not in master.columns:
            master[col] = 0

    # Clean types
    master["ROI"] = master["ROI"].astype(str)
    for col in ["n_spikes_all", "n_spikes_in_stim", "n_spikes_outside"]:
        master[col] = pd.to_numeric(master[col], errors="coerce").fillna(0).astype(int)

    totals = (
        master
        .groupby("ROI", dropna=False)
        .agg(
            n_spikes_all=("n_spikes_all", "sum"),
            n_spikes_in_stim=("n_spikes_in_stim", "sum"),
            n_spikes_outside=("n_spikes_outside", "sum"),
            n_runs=("ROI", "size")  # count rows per ROI
        )
        .reset_index()
        .sort_values("ROI")
    )
    return totals

# ---- Append this run to the master, then (optionally) compute totals ----
master_df = append_roi_table(spike_summary, source_label=RUN_ID, master_path=MASTER_CSV)

# Example usage: get totals and (optionally) save them
totals_df = summarize_totals(MASTER_CSV)
totals_df.to_csv("roi_spike_totals_across_runs.csv", index=False)
print("Updated master table:", MASTER_CSV)
print("Wrote totals to: roi_spike_totals_across_runs.csv")

csv_path = "roi_spike_totals_across_runs.csv"


# Load the CSV
df = pd.read_csv(csv_path)

# Optionally filter out ROIs with 0 spikes
df = df[df["n_spikes_all"] > 0]

# Display dataframe for inspection
print(df)

# Plot bar chart of total spikes per ROI
plt.figure(figsize=(10, 6))
plt.bar(df["ROI"], df["n_spikes_all"], color="steelblue")
plt.xlabel("ROI")
plt.ylabel("Total Spikes")
plt.title("Total Spikes per ROI Across Runs")
plt.xticks(rotation=45, ha="right")
plt.tight_layout()
plt.show()

