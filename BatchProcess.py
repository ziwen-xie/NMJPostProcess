# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Tuple, List, Optional, Dict
import re
import copy

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

try:
    from tqdm import tqdm

    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False


# =========================
# Configuration
# =========================
@dataclass
class Config:
    # I/O
    csv_path: str = "./0718/20-6.csv"
    encoding: str = "utf-16"
    skip_first_row: bool = True
    time_col: str = "Axis [s]"
    roi_key: str = "ROI"

    # Background options
    bg_source: str = "roi_column"
    bg_column_name: str = "ROI.01 []"
    bg_csv_path: str = "./0718/bg.csv"
    bg_csv_col_name: Optional[str] = None

    # Plot behavior
    exclude_bg_roi_from_plot: bool = True
    ylim_max: float = 0.3
    fig_size: Tuple[float, float] = (10, 6)
    cmap_name: str = "tab10"
    stim_color: str = "red"
    stim_alpha: float = 0.30
    use_auto_ylim: bool = True  # Changed default to True
    auto_ylim_include_zero: bool = False
    auto_ylim_pad_frac: float = 0.05
    ylim_min: Optional[float] = 0.0

    # ΔF/F baseline
    baseline_window_half_s: float = 15.0
    baseline_percentile: float = 8.0

    # Stimulation windows
    stim_preset: str = "20s"
    stim_windows_custom: Optional[List[Tuple[float, float]]] = None
    stim_windows: List[Tuple[float, float]] = None

    # Outputs
    out_fig: Optional[str] = "deltaF_F_plot_bgselect.png"
    out_csv: Optional[str] = None

    # Spike detection
    baseline_index_start: int = 10
    baseline_index_end: int = 20
    baseline_frames_for_spike: int = 29
    spike_z_sigma: float = 5.0
    min_spike_distance_s: Optional[float] = 3.0  # Changed default to 3 seconds
    exclude_bg_roi_from_detection: bool = True
    out_spike_csv: Optional[str] = "spike_summary.csv"
    out_spike_stats_csv: Optional[str] = "spike_baseline_stats.csv"

    # Spike latency calculation
    calculate_spike_latencies: bool = False
    latency_method: str = "nearest"   # "nearest", "first_spike", "stim_onset", "glm"
    max_latency_window_s: Optional[float] = None
    out_spike_latency_stats_csv: Optional[str] = "spike_latency_stats.csv"
    out_spike_latency_detailed_csv: Optional[str] = "spike_latency_detailed.csv"

    # Shared baseline options
    baseline_mode: str = "standard"  # Options: "standard", "shared_control", "shared_per_condition"
    shared_baseline_start_frame: int = 10  # Start frame for shared baseline (e.g., 10)
    shared_baseline_end_frame: int = 30    # End frame for shared baseline - Changed default to 30
    control_file_pattern: str = "Ctrl1"    # Pattern to identify control files - Changed to "Ctrl1"
    shared_baseline_values: Optional[Dict[str, float]] = None  # Computed baseline values {ROI: F0}

    # Plot: spike overlay
    show_spike_markers: bool = True
    spike_marker: str = "o"
    spike_marker_size: int = 36
    spike_marker_face: str = "none"
    spike_marker_edgecolor: str = "k"
    annotate_spike_counts: bool = True
    annotate_spike_counts_max: int = 6
    annotate_spike_counts_loc: str = "upper right"

    label_spike_numbers: bool = False
    label_fontsize: int = 8
    label_offset_y: float = 0.02

    # Second figure with only spiking ROIs
    show_spiking_only_figure: bool = True
    out_fig_spiking_only: Optional[str] = "deltaF_F_spiking_only.png"

    # Spike width filter
    width_mode: str = "rough"
    width_threshold_s: float = 2.0  # Changed default to 2 seconds

    # ROIs to exclude from plotting
    exclude_roi_map: Dict[str, bool] = field(default_factory=dict)

    # Stimulation windows
    stim_preset: str = "20s"
    stim_windows_custom: Optional[List[Tuple[float, float]]] = None
    stim_windows: List[Tuple[float, float]] = None

    ### NEW — spike exclusion w.r.t. stim windows
    # Options: "none", "all", "blue"
    # "none" = don't exclude any spikes
    # "all" = exclude spikes in all stim windows
    # "blue" = exclude spikes only in files with "blue" in the name
    exclude_spikes_in_stim: str = "none"
    stim_exclusion_pad_s: float = 0.0  # +/- padding (seconds) around each window for exclusion

    ### NEW — auto infer stim preset from filename (e.g., "20s-1.csv", "10-2.csv", "5s_x.csv")
    stim_preset_infer_from_name: bool = True  # if True, infer from csv filename; otherwise honor stim_preset

    def __post_init__(self):
        presets = {
            "20s": [(30, 50), (80, 100), (130, 150)],
            "10s": [(30, 40), (70, 80), (110, 120)],
            "5s": [(30, 35), (65, 70), (100, 105)],
            "none": [],
        }
        if self.stim_preset == "custom":
            if not self.stim_windows_custom:
                raise ValueError("stim_preset='custom' but stim_windows_custom is not provided.")
            self.stim_windows = self.stim_windows_custom
        else:
            if self.stim_preset not in presets:
                raise ValueError("stim_preset must be one of: '20s','10s','5s','none','custom'.")
            self.stim_windows = presets[self.stim_preset]

        if self.bg_source not in {"roi_column", "csv_file"}:
            raise ValueError("bg_source must be 'roi_column' or 'csv_file'.")


@dataclass
class BatchConfig:
    input_folder: str
    file_pattern: str = "*.csv"
    output_root: str = "./batch_results"
    shared_config: Config = None
    per_file_overrides: Dict[str, Dict] = field(default_factory=dict)
    summary_table_path: str = "spike_summary_table.csv"
    summary_table_excel: Optional[str] = "spike_summary_table.xlsx"
    include_zero_spike_rois: bool = False
    continue_on_error: bool = True
    verbose: bool = True


def load_fluo_csv(path: str, encoding: str, skip_first_row: bool) -> pd.DataFrame:
    p = Path(path)
    if skip_first_row:
        return pd.read_csv(p, encoding=encoding, skiprows=1)
    try:
        return pd.read_csv(p)
    except UnicodeDecodeError:
        return pd.read_csv(p, encoding=encoding)


def find_roi_columns(df: pd.DataFrame, roi_key: str) -> List[str]:
    return [c for c in df.columns if roi_key in c]


def select_background(df_main: pd.DataFrame, cfg: Config) -> np.ndarray:
    if cfg.time_col not in df_main.columns:
        raise ValueError(f"Time column '{cfg.time_col}' not found in main CSV.")
    t_main = df_main[cfg.time_col].to_numpy()

    if cfg.bg_source == "roi_column":
        if cfg.bg_column_name not in df_main.columns:
            raise ValueError(
                f"Background column '{cfg.bg_column_name}' not found in main CSV.\n"
                f"Available columns: {list(df_main.columns)}"
            )
        bg_vals = df_main[cfg.bg_column_name].to_numpy(dtype=float)
        if bg_vals.shape[0] != t_main.shape[0]:
            raise ValueError("Background column length does not match main time length.")
        return bg_vals

    df_bg = load_fluo_csv(cfg.bg_csv_path, encoding=cfg.encoding, skip_first_row=cfg.skip_first_row)
    if cfg.time_col not in df_bg.columns:
        raise ValueError(
            f"Time column '{cfg.time_col}' not found in BG CSV. "
            f"BG CSV columns: {list(df_bg.columns)}"
        )

    if cfg.bg_csv_col_name and cfg.bg_csv_col_name in df_bg.columns:
        bg_col = cfg.bg_csv_col_name
    else:
        roi_like = [c for c in df_bg.columns if cfg.roi_key in c]
        if roi_like:
            bg_col = roi_like[0]
        else:
            numeric_candidates = [c for c in df_bg.select_dtypes(include=np.number).columns if c != cfg.time_col]
            if not numeric_candidates:
                raise ValueError("No suitable background column found in BG CSV.")
            bg_col = numeric_candidates[0]

    t_bg = df_bg[cfg.time_col].to_numpy()
    bg_raw = df_bg[bg_col].to_numpy(dtype=float)

    order = np.argsort(t_bg)
    t_bg_sorted = t_bg[order]
    bg_sorted = bg_raw[order]
    return np.interp(t_main, t_bg_sorted, bg_sorted)


def background_subtraction(F: np.ndarray, bg: np.ndarray) -> np.ndarray:
    if F.shape[0] != bg.shape[0]:
        raise ValueError("F and background must have the same length.")
    return F - bg


def dff_percentile_window(
        F: np.ndarray,
        t: np.ndarray,
        window_half_s: float,
        percentile: float
) -> Tuple[np.ndarray, np.ndarray]:
    n = F.size
    F0 = np.zeros_like(F, dtype=float)
    for i in range(n):
        t0 = max(t[0], t[i] - window_half_s)
        t1 = min(t[-1], t[i] + window_half_s)
        idx = (t >= t0) & (t <= t1)
        F0[i] = np.percentile(F[idx], percentile)
    # Use abs(F0) to prevent signal inversion when F0 is negative (after background subtraction)
    # Small epsilon added to avoid division by zero
    dff = (F - F0) / (np.abs(F0) + 1e-9)
    return dff, F0


def dff_fixed_baseline(
        F: np.ndarray,
        F0_value: float
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute ΔF/F using a fixed baseline value.

    Parameters
    ----------
    F : np.ndarray
        Fluorescence trace
    F0_value : float
        Fixed baseline value (F0)

    Returns
    -------
    dff : np.ndarray
        ΔF/F trace
    F0 : np.ndarray
        Baseline array (all same value)

    Notes
    -----
    When F0 is negative (after background subtraction), we use abs(F0) in the
    denominator to prevent signal inversion. The numerator (F - F0) correctly
    represents the change from baseline.
    """
    F0 = np.full_like(F, F0_value, dtype=float)
    # Use abs(F0_value) to prevent signal inversion when F0 is negative
    # Small epsilon added to avoid division by zero
    dff = (F - F0) / (abs(F0_value) + 1e-9)
    return dff, F0


def compute_all_dff(
        df_main: pd.DataFrame,
        roi_cols: Iterable[str],
        bg_vec: np.ndarray,
        t: np.ndarray,
        cfg: Config
) -> pd.DataFrame:
    dff_dict = {}

    # Check if using shared baseline
    use_shared_baseline = (cfg.shared_baseline_values is not None and
                          len(cfg.shared_baseline_values) > 0)

    if use_shared_baseline:
        print(f"\nUsing shared baseline for {len(cfg.shared_baseline_values)} ROIs")

    for col in roi_cols:
        F_corr = background_subtraction(df_main[col].to_numpy(dtype=float), bg_vec)

        if use_shared_baseline and col in cfg.shared_baseline_values:
            # Use fixed baseline from shared baseline values
            F0_value = cfg.shared_baseline_values[col]
            dff_vals, _ = dff_fixed_baseline(F_corr, F0_value)

            # Debug: Check if dF/F values are reasonable
            if np.isnan(dff_vals).any() or (abs(dff_vals.mean()) > 10):
                print(f"  WARNING: {col} has unusual dF/F values:")
                print(f"    F0_shared = {F0_value:.3f}")
                print(f"    F_corr mean = {F_corr.mean():.3f}")
                print(f"    dF/F mean = {dff_vals.mean():.3f}, std = {dff_vals.std():.3f}")
        else:
            # Use standard sliding window baseline
            dff_vals, _ = dff_percentile_window(
                F_corr, t,
                window_half_s=cfg.baseline_window_half_s,
                percentile=cfg.baseline_percentile,
            )

        dff_dict[col] = dff_vals

    out = pd.DataFrame(dff_dict)
    out.insert(0, "Time (s)", t)
    return out


def apply_roi_exclusions(roi_cols: List[str], cfg: Config) -> List[str]:
    excluded = {k for k, v in cfg.exclude_roi_map.items() if v}
    return [c for c in roi_cols if c not in excluded]


def compute_auto_ylim(
        dff_table: pd.DataFrame,
        columns: List[str],
        include_zero: bool = True,
        pad_frac: float = 0.05,
) -> Tuple[float, float]:
    arrays = [dff_table[c].to_numpy(dtype=float) for c in columns if c in dff_table.columns]
    if not arrays:
        return (0.0, 1.0)

    vals = np.concatenate(arrays)
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        return (0.0, 1.0)

    y_min = float(np.min(vals))
    y_max = float(np.max(vals))
    if include_zero:
        y_min = min(y_min, 0.0)
        y_max = max(y_max, 0.0)

    span = y_max - y_min
    if span <= 0:
        pad = 0.1 * (abs(y_max) if y_max != 0 else 1.0)
    else:
        pad = span * pad_frac

    return (0, y_max + pad)


def overlay_spikes_on_axes(
        ax: plt.Axes,
        dff_table: pd.DataFrame,
        roi_cols_for_plot: List[str],
        spike_times: Dict[str, np.ndarray],
        color_map: Dict[str, tuple],
        cfg: Config,
) -> None:
    if not cfg.show_spike_markers and not cfg.annotate_spike_counts:
        return

    t_vals = dff_table["Time (s)"].to_numpy()
    annotated_rows = []

    for col in roi_cols_for_plot:
        times = spike_times.get(col, np.array([], dtype=float))
        if times.size == 0:
            continue

        mask = np.isin(t_vals, times)
        idxs = np.nonzero(mask)[0]
        if idxs.size == 0:
            continue

        x = t_vals[idxs]
        y = dff_table[col].to_numpy()[idxs]

        if cfg.show_spike_markers:
            face = color_map[col] if cfg.spike_marker_face != "none" else "none"
            ax.scatter(
                x, y,
                s=cfg.spike_marker_size,
                marker=cfg.spike_marker,
                facecolors=face,
                edgecolors=cfg.spike_marker_edgecolor,
                linewidths=1.0,
                zorder=5,
            )
        if cfg.label_spike_numbers:
            for j, (xx, yy) in enumerate(zip(x, y), 1):
                ax.text(xx, yy + cfg.label_offset_y, str(j),
                        ha="center", va="bottom", fontsize=cfg.label_fontsize)

        annotated_rows.append((col, len(x)))

    if cfg.annotate_spike_counts and annotated_rows:
        annotated_rows.sort(key=lambda kv: kv[1], reverse=True)
        annotated_rows = annotated_rows[:cfg.annotate_spike_counts_max]
        summary_text = "\n".join(f"{roi}: {cnt}" for roi, cnt in annotated_rows)

        loc_map = {
            "upper right": (1.0, 1.0, "right", "top"),
            "upper left": (0.0, 1.0, "left", "top"),
            "lower right": (1.0, 0.0, "right", "bottom"),
            "lower left": (0.0, 0.0, "left", "bottom"),
        }
        xA, yA, ha, va = loc_map.get(cfg.annotate_spike_counts_loc, (1.0, 1.0, "right", "top"))

        ax.text(
            xA, yA, f"Spikes (top {cfg.annotate_spike_counts_max}):\n" + summary_text,
            transform=ax.transAxes,
            ha=ha, va=va,
            fontsize=9,
            bbox=dict(boxstyle="round,pad=0.35", facecolor="white", alpha=0.8, linewidth=0.8),
        )


def plot_dff(
        dff_table: pd.DataFrame,
        roi_cols: List[str],
        cfg: Config,
        bg_was_roi: bool,
        spike_times: Optional[Dict[str, np.ndarray]] = None,
) -> plt.Figure:
    roi_cols_for_plot = apply_roi_exclusions(list(roi_cols), cfg)

    if bg_was_roi and cfg.exclude_bg_roi_from_plot:
        roi_cols_for_plot = [c for c in roi_cols_for_plot if c != cfg.bg_column_name]

    fig, ax = plt.subplots(figsize=cfg.fig_size)

    colors = plt.get_cmap(cfg.cmap_name).colors
    color_map = {roi_cols_for_plot[i]: colors[i % len(colors)] for i in range(len(roi_cols_for_plot))}

    for col in roi_cols_for_plot:
        ax.plot(dff_table["Time (s)"], dff_table[col], label=col, linewidth=1.2, color=color_map[col])

    for s, e in cfg.stim_windows:
        ax.axvspan(s, e, color=cfg.stim_color, alpha=cfg.stim_alpha)

    if spike_times is not None:
        overlay_spikes_on_axes(ax, dff_table, roi_cols_for_plot, spike_times, color_map, cfg)

    ax.axhline(0, linestyle="--", linewidth=1)

    if cfg.use_auto_ylim:
        y0, y1 = compute_auto_ylim(
            dff_table,
            roi_cols_for_plot,
            include_zero=cfg.auto_ylim_include_zero,
            pad_frac=cfg.auto_ylim_pad_frac,
        )
        ax.set_ylim(y0, y1)
    else:
        ymin = 0.0 if cfg.ylim_min is None else cfg.ylim_min
        ymax = 1.0 if cfg.ylim_max is None else cfg.ylim_max
        ax.set_ylim(ymin, ymax)

    ax.set_xlabel("Time (s)")
    ax.set_ylabel("ΔF/F")
    ax.set_title("ΔF/F")
    if roi_cols_for_plot:
        ax.legend()

    fig.tight_layout()
    return fig

def infer_stim_preset_from_string(s: str) -> str:
    """
    Infer '20s' / '10s' / '5s' from a string (filename or group name).
    Rules:
      - If it contains a 20s token (e.g. '20s', '20s1', '20-2') -> '20s'
      - If it contains a 10s token (e.g. '10s', '10s2', '10-3') -> '10s'
      - If it contains a 5s token  (e.g. '5s',  '5s1',  '5-4')  -> '5s'
      - Otherwise default to '20s'
    Matching is case-insensitive.
    """
    s_low = s.lower()

    # Explicit compact tokens first (20s1 / 10s2 / 5s3 / 20-1 / 10_2 / 5-4)
    token_rules = [
        ("20s", [r"(?<!\d)20s\d*(?!\d)", r"(?<!\d)20[-_]\d*(?!\d)"]),
        ("10s", [r"(?<!\d)10s\d*(?!\d)", r"(?<!\d)10[-_]\d*(?!\d)"]),
        ("5s", [r"(?<!\d)5s\d*(?!\d)",  r"(?<!\d)5[-_]\d*(?!\d)"]),
    ]
    for preset, patterns in token_rules:
        if any(re.search(pat, s_low) for pat in patterns):
            return preset

    # Backward-compatible fallback for plain tokens.
    if "20s" in s_low:
        return "20s"
    if "10s" in s_low:
        return "10s"
    if "5s" in s_low:
        return "5s"
    return "20s"

def apply_inferred_stim_preset(cfg: Config, name_hint: Optional[str] = None) -> None:
    """
    If cfg.stim_preset_infer_from_name is True, infer from csv filename (or provided name_hint),
    then update cfg.stim_preset and cfg.stim_windows accordingly.
    """
    if not cfg.stim_preset_infer_from_name:
        return

    source = name_hint if name_hint else Path(cfg.csv_path).name
    inferred = infer_stim_preset_from_string(source)

    # Rebuild preset windows exactly like __post_init__ does
    presets = {
        "20s": [(30, 50), (80, 100), (130, 150)],
        "10s": [(30, 40), (70, 80), (110, 120)],
        "5s":  [(30, 35), (65, 70), (100, 105)],
        "none": [],
    }

    cfg.stim_preset = inferred
    cfg.stim_windows = presets[cfg.stim_preset]


def should_exclude_spikes_in_stim(mode: str, filename: str) -> bool:
    """
    Determine if spikes should be excluded from stim windows based on mode and filename.

    Args:
        mode: "none", "all", or "blue"
        filename: Path to the file being processed

    Returns:
        True if spikes should be excluded, False otherwise
    """
    if mode == "none":
        return False
    elif mode == "all":
        return True
    elif mode == "blue":
        # Check if filename contains "blue" (case-insensitive)
        from pathlib import Path
        name = Path(filename).name.lower()
        return "blue" in name
    else:
        # Default to not excluding if mode is unrecognized
        return False


def filter_times_outside_windows(
    times: np.ndarray,
    windows: Optional[List[Tuple[float, float]]],
    pad: float = 0.0
) -> np.ndarray:
    """
    Return times that are NOT inside any [start-pad, end+pad] window.
    """
    if times.size == 0 or not windows:
        return times
    keep_mask = np.ones(times.shape[0], dtype=bool)
    for (s, e) in windows:
        in_win = (times >= (s - pad)) & (times <= (e + pad))
        keep_mask &= ~in_win
    return times[keep_mask]


def _segments_above_threshold(y: np.ndarray, thr: float) -> List[np.ndarray]:
    above = y > thr
    idx = np.flatnonzero(above)
    if idx.size == 0:
        return []
    splits = np.where(np.diff(idx) > 1)[0] + 1
    return np.split(idx, splits)


def _interp_time_at_y(t1, y1, t2, y2, y_target) -> float:
    if y2 == y1:
        return float(t1)
    alpha = (y_target - y1) / (y2 - y1)
    return float(t1 + alpha * (t2 - t1))


def _measure_run_widths(
        y: np.ndarray, t: np.ndarray, run: np.ndarray, k_peak: int, baseline_mean: float
) -> Tuple[float, float]:
    rough_w = float(t[run[-1]] - t[run[0]])

    peak_val = float(y[k_peak])
    half_lvl = 0.5 * (peak_val + float(baseline_mean))

    t_left = float(t[run[0]])
    for j in range(k_peak, run[0], -1):
        if (y[j - 1] < half_lvl) and (y[j] >= half_lvl):
            t_left = _interp_time_at_y(t[j - 1], y[j - 1], t[j], y[j], half_lvl)
            break

    t_right = float(t[run[-1]])
    for j in range(k_peak + 1, run[-1] + 1):
        if (y[j] < half_lvl) and (y[j - 1] >= half_lvl):
            t_right = _interp_time_at_y(t[j - 1], y[j - 1], t[j], y[j], half_lvl)
            break

    fwhm_w = max(0.0, float(t_right - t_left))
    return rough_w, fwhm_w


def _baseline_stats_frame_range(
        y: np.ndarray, spike_z_sigma: float, start_idx: int, end_idx: int,
        iterative_clean: bool = True, outlier_sigma: float = 2.0,
        outlier_pad: int = 2, max_iterations: int = 3
) -> Tuple[float, float, float]:
    n = y.size
    if n == 0:
        return 0.0, 0.0, 0.0
    s = max(0, min(start_idx, end_idx))
    e = min(n - 1, max(start_idx, end_idx))
    base = y[s:e + 1]
    if base.size == 0:
        base = y[:1]

    # Iterative baseline cleaning: if outlier points exist in the baseline
    # region (e.g. a spike contaminating the first 30s), exclude them and
    # recompute to avoid inflating the threshold.
    # Uses MAD (median absolute deviation) for robust outlier detection,
    # since mean/sd-based detection is itself corrupted by the outliers.
    if iterative_clean and base.size > 5:
        mask = np.ones(base.size, dtype=bool)
        for _iteration in range(max_iterations):
            clean = base[mask]
            if clean.size < 3:
                break
            med = float(np.median(clean))
            mad = float(np.median(np.abs(clean - med)))
            # Convert MAD to sd-equivalent (factor 1.4826 for normal dist)
            mad_sd = mad * 1.4826
            if mad_sd <= 1e-12:
                break
            outlier_thr = med + outlier_sigma * mad_sd
            new_outliers = np.where((base > outlier_thr) & mask)[0]
            if new_outliers.size == 0:
                break
            # Exclude outlier points plus a small buffer around them
            for o in new_outliers:
                for d in range(-outlier_pad, outlier_pad + 1):
                    idx = o + d
                    if 0 <= idx < mask.size:
                        mask[idx] = False
        base = base[mask] if np.any(mask) else base

    mean0 = float(np.mean(base))
    sd0 = float(np.std(base, ddof=1)) if base.size > 1 else 0.0
    thr = mean0 + spike_z_sigma * (sd0 if sd0 > 0 else 1e-12)
    return mean0, sd0, thr


def _baseline_stats_first_n(y: np.ndarray, spike_z_sigma: float, n: int,
                            iterative_clean: bool = True, outlier_sigma: float = 2.0,
                            outlier_pad: int = 2, max_iterations: int = 3
                            ) -> Tuple[float, float, float]:
    n_eff = min(n, y.size)
    base = y[:n_eff]

    if iterative_clean and base.size > 5:
        mask = np.ones(base.size, dtype=bool)
        for _iteration in range(max_iterations):
            clean = base[mask]
            if clean.size < 3:
                break
            med = float(np.median(clean))
            mad = float(np.median(np.abs(clean - med)))
            mad_sd = mad * 1.4826
            if mad_sd <= 1e-12:
                break
            outlier_thr = med + outlier_sigma * mad_sd
            new_outliers = np.where((base > outlier_thr) & mask)[0]
            if new_outliers.size == 0:
                break
            for o in new_outliers:
                for d in range(-outlier_pad, outlier_pad + 1):
                    idx = o + d
                    if 0 <= idx < mask.size:
                        mask[idx] = False
        base = base[mask] if np.any(mask) else base

    mean0 = float(np.mean(base))
    sd0 = float(np.std(base, ddof=1)) if base.size > 1 else 0.0
    thr = mean0 + spike_z_sigma * (sd0 if sd0 > 0 else 1e-12)
    return mean0, sd0, thr


def _enforce_min_distance(idxs: np.ndarray, t: np.ndarray, min_distance_s: Optional[float]) -> np.ndarray:
    if min_distance_s is None or idxs.size == 0:
        return idxs
    keep = [idxs[0]]
    last_t = t[idxs[0]]
    for k in idxs[1:]:
        if (t[k] - last_t) >= min_distance_s:
            keep.append(k)
            last_t = t[k]
    return np.array(keep, dtype=int)


def _split_run_at_stim_boundaries(t, run, stim_windows, y=None):
    """Split a contiguous run at stim window end boundaries.

    When a low threshold causes the stim artifact and a post-stim biological
    spike to form one merged run, this function splits them so each portion
    can be evaluated independently by the width filter and peak detector.

    If *y* (the signal array) is provided, post-stim sub-runs are further
    split at the first local minimum after a large light-leakage drop.  This
    separates the decaying artifact tail from a genuine biological spike that
    stays above threshold.

    Returns a list of sub-runs (numpy arrays of indices).
    """
    if not stim_windows or len(run) < 2:
        return [run]

    run_times = t[run]
    # Find stim window ends that fall inside this run
    cut_points = []
    for (_ws, we) in stim_windows:
        if run_times[0] <= we < run_times[-1]:
            cut_points.append(we)

    if not cut_points:
        return [run]

    sub_runs = []
    remaining = run
    for we in sorted(cut_points):
        # Split: indices with t <= we go to one sub-run, t > we to next
        rem_times = t[remaining]
        in_stim = remaining[rem_times <= we]
        after_stim = remaining[rem_times > we]
        if len(in_stim) > 0:
            sub_runs.append(in_stim)
        # Further split the post-stim portion at the local minimum between
        # the light-leakage tail and any biological spike
        if y is not None and len(after_stim) >= 3:
            vals = y[after_stim]
            # Find the first local minimum (where derivative goes from
            # negative to non-negative).  This marks the valley between
            # the decaying artifact and a rising biological spike.
            diffs = np.diff(vals)
            min_idx = None
            for j in range(len(diffs) - 1):
                if diffs[j] <= 0 and diffs[j + 1] > 0:
                    min_idx = j + 1  # index within after_stim
                    break
            if min_idx is not None and min_idx > 0 and min_idx < len(after_stim) - 1:
                artifact_tail = after_stim[:min_idx]
                bio_spike = after_stim[min_idx:]
                if len(artifact_tail) > 0:
                    sub_runs.append(artifact_tail)
                remaining = bio_spike
                continue
        remaining = after_stim
        if len(remaining) == 0:
            break
    if len(remaining) > 0:
        sub_runs.append(remaining)

    return sub_runs


def _run_straddles_stim_end(t, run, stim_windows):
    """Check if a run of above-threshold indices crosses a stim window end boundary.
    Returns (True, window_end_time, post_stim_indices) or (False, None, None)."""
    if not stim_windows:
        return False, None, None
    run_start_t = t[run[0]]
    run_end_t = t[run[-1]]
    for (ws, we) in stim_windows:
        # Run must start during or before stim and extend past stim end
        if run_start_t <= we and run_end_t > we:
            post_mask = t[run] > we
            post_idxs = run[post_mask]
            if len(post_idxs) > 0:
                return True, we, post_idxs
    return False, None, None


def detect_spikes_across_rois(
        dff_table: pd.DataFrame,
        roi_cols: List[str],
        time_col: str = "Time (s)",
        baseline_frames: Optional[int] = None,
        baseline_range: Optional[Tuple[int, int]] = None,
        spike_z_sigma: float = 3.0,
        min_distance_s: Optional[float] = None,
        width_mode: str = "rough",
        width_threshold_s: float = 0.50,
        stim_windows: Optional[List[Tuple[float, float]]] = None,
        exclude_spikes_in_windows: bool = False,
        stim_exclusion_pad_s: float = 0.0,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, np.ndarray]]:
    t = dff_table[time_col].to_numpy(dtype=float)

    stats_rows, summary_rows = [], []
    spike_times = {}

    for col in roi_cols:
        y = dff_table[col].to_numpy(dtype=float)

        if baseline_range is not None:
            mean0, sd0, thr = _baseline_stats_frame_range(
                y, spike_z_sigma, baseline_range[0], baseline_range[1]
            )
        else:
            n = 59 if baseline_frames is None else baseline_frames
            mean0, sd0, thr = _baseline_stats_first_n(y, spike_z_sigma, n)

        runs = _segments_above_threshold(y, thr)

        # Split runs at stim window boundaries so that post-stim biological
        # spikes merged with the stim artifact are detected independently.
        if stim_windows:
            split_runs = []
            for run in runs:
                sub_runs = _split_run_at_stim_boundaries(t, run, stim_windows, y=y)
                split_runs.extend(sub_runs)
            runs = split_runs

        accepted_peak_idxs = []

        for run in runs:
            k_peak = run[np.argmax(y[run])]
            rough_w, fwhm_w = _measure_run_widths(y, t, run, k_peak, baseline_mean=mean0)
            measured = rough_w if width_mode.lower() == "rough" else fwhm_w
            if np.isfinite(measured) and (measured >= width_threshold_s):
                accepted_peak_idxs.append(int(k_peak))

        if accepted_peak_idxs:
            accepted_peak_idxs = np.array(sorted(accepted_peak_idxs), dtype=int)
            peak_times = t[accepted_peak_idxs]

            # Exclude spikes before 10 seconds
            peak_times = peak_times[peak_times >= 10.0]

            # Exclude spikes inside stim windows BEFORE min-distance filtering.
            # This prevents a stim-artifact peak from blocking a nearby
            # biological spike via the min-distance rule.
            if exclude_spikes_in_windows and stim_windows:
                peak_times = filter_times_outside_windows(
                    peak_times, stim_windows, pad=stim_exclusion_pad_s
                )

            # Now apply min-distance filter on the remaining biological spikes
            if min_distance_s is not None and peak_times.size > 1:
                keep = [peak_times[0]]
                for pt in peak_times[1:]:
                    if (pt - keep[-1]) >= min_distance_s:
                        keep.append(pt)
                peak_times = np.array(keep, dtype=float)
        else:
            peak_times = np.array([], dtype=float)

        stats_rows.append({"ROI": col, "mean0": mean0, "sd0": sd0, "thr": thr})
        spike_times[col] = peak_times
        if peak_times.size > 0:
            summary_rows.append({"ROI": col, "n_spikes": int(peak_times.size)})

    stats_df = pd.DataFrame(stats_rows)
    summary_df = pd.DataFrame(summary_rows, columns=["ROI", "n_spikes"])
    if not summary_df.empty:
        summary_df = summary_df.sort_values("n_spikes", ascending=False).reset_index(drop=True)
    return summary_df, stats_df, spike_times


def calculate_spike_latencies(
    spike_times: Dict[str, np.ndarray],
    stim_windows: List[Tuple[float, float]],
    max_latency_window_s: Optional[float] = None
) -> Tuple[Dict[str, np.ndarray], pd.DataFrame, pd.DataFrame]:
    """
    Calculate spike latencies relative to preceding stimulation windows.

    For each spike, find the most recent stimulation window that ENDS before the spike,
    then calculate latency = spike_time - stim_window_end.

    Parameters
    ----------
    spike_times : Dict[str, np.ndarray]
        Dictionary mapping ROI names to arrays of spike times (in seconds).
    stim_windows : List[Tuple[float, float]]
        List of stimulation windows as (start, end) tuples in seconds.
    max_latency_window_s : Optional[float]
        Maximum time window after stim end to consider for latency calculation.
        If specified, spikes occurring more than this time after the stim window
        will be excluded. If None, all spikes are considered.

    Returns
    -------
    latencies_dict : Dict[str, np.ndarray]
        Dictionary mapping ROI names to arrays of spike latencies (in seconds).
        Only includes spikes that have a valid preceding stimulation window.
    stats_df : pd.DataFrame
        DataFrame with columns ["ROI", "n_latencies", "mean_latency_s", "median_latency_s",
        "std_latency_s", "min_latency_s", "max_latency_s"].
        Summary statistics for each ROI.
    detailed_df : pd.DataFrame
        DataFrame with columns ["ROI", "spike_time_s", "latency_s", "stim_window_start_s",
        "stim_window_end_s"].
        One row per spike with valid latency.
    """
    if not stim_windows:
        # No stimulation windows - return empty results
        empty_dict = {roi: np.array([], dtype=float) for roi in spike_times.keys()}
        empty_stats = pd.DataFrame(columns=["ROI", "n_latencies", "mean_latency_s",
                                             "median_latency_s", "std_latency_s",
                                             "min_latency_s", "max_latency_s"])
        empty_detailed = pd.DataFrame(columns=["ROI", "spike_time_s", "latency_s",
                                                "stim_window_start_s", "stim_window_end_s"])
        return empty_dict, empty_stats, empty_detailed

    # Sort stimulation windows by end time for efficient lookup
    sorted_windows = sorted(stim_windows, key=lambda x: x[1])

    latencies_dict = {}
    detailed_rows = []
    stats_rows = []

    for roi_name, spikes in spike_times.items():
        roi_latencies = []

        for spike_time in spikes:
            # First check if spike is INSIDE any stimulation window
            inside_window = False
            for window_start, window_end in sorted_windows:
                if window_start <= spike_time <= window_end:
                    # Spike is inside this stim window - latency is 0
                    latency = 0.0
                    inside_window = True
                    break

            if inside_window:
                # Spike is inside stim window - latency is 0
                # Use this window for recording
                pass  # latency and window_start/window_end already set
            else:
                # Find all windows that END before this spike
                preceding_windows = [w for w in sorted_windows if w[1] < spike_time]

                if not preceding_windows:
                    # No stimulation window before this spike - skip it
                    continue

                # Get the most recent window (maximum end time)
                most_recent_window = max(preceding_windows, key=lambda x: x[1])
                window_start, window_end = most_recent_window

                # Calculate latency from end of stimulation to spike
                latency = spike_time - window_end

            # Apply max latency window filter if specified
            if max_latency_window_s is not None and latency > max_latency_window_s:
                continue

            roi_latencies.append(latency)
            detailed_rows.append({
                "ROI": roi_name,
                "spike_time_s": spike_time,
                "latency_s": latency,
                "stim_window_start_s": window_start,
                "stim_window_end_s": window_end
            })

        # Store latencies for this ROI
        latencies_array = np.array(roi_latencies, dtype=float)
        latencies_dict[roi_name] = latencies_array

        # Calculate statistics if we have latencies
        if len(roi_latencies) > 0:
            stats_rows.append({
                "ROI": roi_name,
                "n_latencies": len(roi_latencies),
                "mean_latency_s": np.mean(roi_latencies),
                "median_latency_s": np.median(roi_latencies),
                "std_latency_s": np.std(roi_latencies),
                "min_latency_s": np.min(roi_latencies),
                "max_latency_s": np.max(roi_latencies)
            })

    # Create DataFrames
    stats_df = pd.DataFrame(stats_rows)
    detailed_df = pd.DataFrame(detailed_rows)

    return latencies_dict, stats_df, detailed_df


def calculate_stim_onset_latencies(
    spike_times: Dict[str, np.ndarray],
    stim_windows: List[Tuple[float, float]],
    max_latency_window_s: Optional[float] = None
) -> Tuple[Dict[str, np.ndarray], pd.DataFrame, pd.DataFrame]:
    """
    Calculate spike latencies relative to the START of stimulation windows.

    For each spike, find the most recent stimulation window whose start is
    at or before the spike time, then calculate latency = spike_time - stim_start.
    Spikes occurring inside a stimulation window are included (latency > 0).

    Parameters
    ----------
    spike_times : Dict[str, np.ndarray]
        Dictionary mapping ROI names to arrays of spike times (in seconds).
    stim_windows : List[Tuple[float, float]]
        List of stimulation windows as (start, end) tuples in seconds.
    max_latency_window_s : Optional[float]
        Maximum latency to include. If None, all spikes are considered.

    Returns
    -------
    latencies_dict, stats_df, detailed_df
    """
    if not stim_windows:
        empty_dict = {roi: np.array([], dtype=float) for roi in spike_times.keys()}
        empty_stats = pd.DataFrame(columns=["ROI", "n_latencies", "mean_latency_s",
                                             "median_latency_s", "std_latency_s",
                                             "min_latency_s", "max_latency_s"])
        empty_detailed = pd.DataFrame(columns=["ROI", "spike_time_s", "latency_s",
                                                "stim_window_start_s", "stim_window_end_s"])
        return empty_dict, empty_stats, empty_detailed

    sorted_windows = sorted(stim_windows, key=lambda x: x[0])

    latencies_dict = {}
    detailed_rows = []
    stats_rows = []

    for roi_name, spikes in spike_times.items():
        roi_latencies = []

        for spike_time in spikes:
            # Find all windows whose START is at or before spike_time
            preceding = [w for w in sorted_windows if w[0] <= spike_time]

            if not preceding:
                continue

            # Most recent window by start time
            window_start, window_end = max(preceding, key=lambda x: x[0])

            # Latency from start of stimulation window
            latency = spike_time - window_start

            if max_latency_window_s is not None and latency > max_latency_window_s:
                continue

            roi_latencies.append(latency)
            detailed_rows.append({
                "ROI": roi_name,
                "spike_time_s": spike_time,
                "latency_s": latency,
                "stim_window_start_s": window_start,
                "stim_window_end_s": window_end
            })

        latencies_array = np.array(roi_latencies, dtype=float)
        latencies_dict[roi_name] = latencies_array

        if len(roi_latencies) > 0:
            stats_rows.append({
                "ROI": roi_name,
                "n_latencies": len(roi_latencies),
                "mean_latency_s": np.mean(roi_latencies),
                "median_latency_s": np.median(roi_latencies),
                "std_latency_s": np.std(roi_latencies),
                "min_latency_s": np.min(roi_latencies),
                "max_latency_s": np.max(roi_latencies)
            })

    stats_df = pd.DataFrame(stats_rows)
    detailed_df = pd.DataFrame(detailed_rows)

    return latencies_dict, stats_df, detailed_df


def calculate_first_spike_latencies(
    spike_times: Dict[str, np.ndarray],
    stim_windows: List[Tuple[float, float]],
    max_latency_window_s: Optional[float] = None
) -> Tuple[Dict[str, np.ndarray], pd.DataFrame, pd.DataFrame]:
    """
    First-spike latency: for each stim window, find the first evoked spike
    (first spike after the window ends) and compute latency = spike_time - window_end.

    Returns same format as calculate_spike_latencies for compatibility.
    """
    if not stim_windows:
        empty_dict = {roi: np.array([], dtype=float) for roi in spike_times.keys()}
        empty_stats = pd.DataFrame(columns=["ROI", "n_latencies", "mean_latency_s",
                                             "median_latency_s", "std_latency_s",
                                             "min_latency_s", "max_latency_s"])
        empty_detailed = pd.DataFrame(columns=["ROI", "spike_time_s", "latency_s",
                                                "stim_window_start_s", "stim_window_end_s"])
        return empty_dict, empty_stats, empty_detailed

    sorted_windows = sorted(stim_windows, key=lambda x: x[0])

    latencies_dict = {}
    detailed_rows = []
    stats_rows = []

    for roi_name, spikes in spike_times.items():
        roi_latencies = []
        sorted_spikes = np.sort(spikes)

        for window_start, window_end in sorted_windows:
            # Find first spike during or after this stim window
            # First check for spikes inside the window
            inside = sorted_spikes[(sorted_spikes >= window_start) & (sorted_spikes <= window_end)]
            if len(inside) > 0:
                first_spike = inside[0]
                latency = 0.0
            else:
                # Find first spike after window_end
                after = sorted_spikes[sorted_spikes > window_end]
                if len(after) == 0:
                    continue
                first_spike = after[0]
                latency = first_spike - window_end

            if max_latency_window_s is not None and latency > max_latency_window_s:
                continue

            roi_latencies.append(latency)
            detailed_rows.append({
                "ROI": roi_name,
                "spike_time_s": float(first_spike),
                "latency_s": latency,
                "stim_window_start_s": window_start,
                "stim_window_end_s": window_end,
            })

        latencies_array = np.array(roi_latencies, dtype=float)
        latencies_dict[roi_name] = latencies_array

        if len(roi_latencies) > 0:
            stats_rows.append({
                "ROI": roi_name,
                "n_latencies": len(roi_latencies),
                "mean_latency_s": np.mean(roi_latencies),
                "median_latency_s": np.median(roi_latencies),
                "std_latency_s": np.std(roi_latencies),
                "min_latency_s": np.min(roi_latencies),
                "max_latency_s": np.max(roi_latencies),
            })

    stats_df = pd.DataFrame(stats_rows)
    detailed_df = pd.DataFrame(detailed_rows)
    return latencies_dict, stats_df, detailed_df


def calculate_glm_latencies(
    spike_times: Dict[str, np.ndarray],
    stim_windows: List[Tuple[float, float]],
    time_array: np.ndarray,
    max_latency_window_s: Optional[float] = None,
    bin_size_s: float = 0.1,
) -> Tuple[Dict[str, np.ndarray], pd.DataFrame, pd.DataFrame]:
    """
    Point-process GLM latency estimation.

    Fits a GLM that models spike probability as:
        logit(P(spike)) = beta_0 + stim_kernel * stimulus_history + hist_kernel * spike_history

    Stimulus history: convolution of binary stimulus signal with raised-cosine basis.
    Spike history: convolution of past spikes with exponential refractory/adaptation kernel.

    Latency is estimated per stim window as the time of peak predicted firing rate
    after stimulus onset.
    """
    from scipy.optimize import minimize
    from scipy.special import expit  # logistic sigmoid

    if not stim_windows:
        empty_dict = {roi: np.array([], dtype=float) for roi in spike_times.keys()}
        empty_stats = pd.DataFrame(columns=["ROI", "n_latencies", "mean_latency_s",
                                             "median_latency_s", "std_latency_s",
                                             "min_latency_s", "max_latency_s"])
        empty_detailed = pd.DataFrame(columns=["ROI", "spike_time_s", "latency_s",
                                                "stim_window_start_s", "stim_window_end_s"])
        return empty_dict, empty_stats, empty_detailed

    sorted_windows = sorted(stim_windows, key=lambda x: x[0])

    # Build time bins covering the full recording
    t_min, t_max = float(time_array[0]), float(time_array[-1])
    bin_edges = np.arange(t_min, t_max + bin_size_s, bin_size_s)
    bin_centres = 0.5 * (bin_edges[:-1] + bin_edges[1:])
    n_bins = len(bin_centres)

    # Build binary stimulus signal
    stim_signal = np.zeros(n_bins, dtype=float)
    for ws, we in sorted_windows:
        stim_signal[(bin_centres >= ws) & (bin_centres <= we)] = 1.0

    # Stimulus basis functions (raised-cosine bumps spanning 0-30s after stim)
    n_stim_basis = 8
    max_lag_s = 30.0
    max_lag_bins = int(max_lag_s / bin_size_s)
    peaks = np.linspace(0, max_lag_bins, n_stim_basis + 2)[1:-1]  # exclude 0 and end
    width = max_lag_bins / (n_stim_basis + 1)

    def raised_cos(t_bins, peak, w):
        x = (t_bins - peak) / w
        return np.where(np.abs(x) <= 1, 0.5 * (1 + np.cos(np.pi * x)), 0.0)

    stim_basis = np.zeros((n_bins, n_stim_basis), dtype=float)
    for bi in range(n_stim_basis):
        kernel = raised_cos(np.arange(max_lag_bins), peaks[bi], width)
        conv = np.convolve(stim_signal, kernel, mode='full')[:n_bins]
        stim_basis[:, bi] = conv

    # Spike history basis (refractory + adaptation, 2 exponential kernels)
    n_hist_basis = 2
    hist_taus = [0.5 / bin_size_s, 5.0 / bin_size_s]  # fast refractory, slow adaptation
    hist_len = int(max(hist_taus) * 5)

    latencies_dict = {}
    detailed_rows = []
    stats_rows = []

    for roi_name, spikes in spike_times.items():
        # Build binary spike train
        spike_train = np.zeros(n_bins, dtype=float)
        for st in spikes:
            idx = int((st - t_min) / bin_size_s)
            if 0 <= idx < n_bins:
                spike_train[idx] = 1.0

        # Build spike history features
        hist_basis = np.zeros((n_bins, n_hist_basis), dtype=float)
        for hi, tau in enumerate(hist_taus):
            kernel = np.exp(-np.arange(hist_len) / max(tau, 1.0))
            kernel[0] = 0.0  # exclude current bin
            conv = np.convolve(spike_train, kernel, mode='full')[:n_bins]
            hist_basis[:, hi] = conv

        # Design matrix: intercept + stim_basis + hist_basis
        X = np.column_stack([np.ones(n_bins), stim_basis, hist_basis])
        y = spike_train

        # Fit GLM via maximum likelihood (logistic regression)
        n_params = X.shape[1]

        def neg_log_likelihood(beta):
            eta = X @ beta
            eta = np.clip(eta, -20, 20)
            p = expit(eta)
            eps = 1e-12
            ll = np.sum(y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps))
            # L2 regularization
            return -ll + 0.01 * np.sum(beta[1:] ** 2)

        beta0 = np.zeros(n_params)
        beta0[0] = np.log(max(y.mean(), 1e-4) / max(1 - y.mean(), 1e-4))

        result = minimize(neg_log_likelihood, beta0, method='L-BFGS-B',
                          options={'maxiter': 200, 'disp': False})
        beta_hat = result.x

        # Compute predicted firing rate
        eta_hat = X @ beta_hat
        eta_hat = np.clip(eta_hat, -20, 20)
        lambda_hat = expit(eta_hat)

        # Compute baseline rate (mean rate outside stim windows)
        baseline_mask = stim_signal == 0
        # Exclude 30s after each stim window from baseline
        for ws, we in sorted_windows:
            post_mask = (bin_centres > we) & (bin_centres <= we + max_lag_s)
            baseline_mask &= ~post_mask
        baseline_rate = np.mean(lambda_hat[baseline_mask]) if baseline_mask.any() else 0.0
        rate_threshold = baseline_rate + 2 * np.std(lambda_hat[baseline_mask]) if baseline_mask.any() else 0.0

        # For each stim window, find peak predicted rate and latency
        roi_latencies = []
        for ws, we in sorted_windows:
            # Look for peak in [ws, ws + max_lag_s]
            search_mask = (bin_centres >= ws) & (bin_centres <= ws + max_lag_s)
            if not search_mask.any():
                continue

            search_rates = lambda_hat[search_mask]
            search_times = bin_centres[search_mask]

            # Find first time the rate exceeds threshold after stim start
            above = search_rates > rate_threshold
            if not above.any():
                continue

            first_above_idx = np.argmax(above)
            peak_time = search_times[first_above_idx]

            if peak_time <= we:
                latency = 0.0
            else:
                latency = peak_time - we

            if max_latency_window_s is not None and latency > max_latency_window_s:
                continue

            roi_latencies.append(latency)
            detailed_rows.append({
                "ROI": roi_name,
                "spike_time_s": float(peak_time),
                "latency_s": latency,
                "stim_window_start_s": ws,
                "stim_window_end_s": we,
            })

        latencies_array = np.array(roi_latencies, dtype=float)
        latencies_dict[roi_name] = latencies_array

        if len(roi_latencies) > 0:
            stats_rows.append({
                "ROI": roi_name,
                "n_latencies": len(roi_latencies),
                "mean_latency_s": np.mean(roi_latencies),
                "median_latency_s": np.median(roi_latencies),
                "std_latency_s": np.std(roi_latencies),
                "min_latency_s": np.min(roi_latencies),
                "max_latency_s": np.max(roi_latencies),
            })

    stats_df = pd.DataFrame(stats_rows)
    detailed_df = pd.DataFrame(detailed_rows)
    return latencies_dict, stats_df, detailed_df


def _find_roi_col_by_number(columns: Sequence[str], roi_num: int) -> Optional[str]:
    """
    Find a column name for ROI number robustly.
    Matches patterns like 'ROI.005 []', 'ROI.05 []', 'ROI.5 []', 'ROI05', 'ROI5' etc.
    """
    # Try strict dotted form first: ROI.<zero-padded> possibly with trailing space + []
    patt_strict = re.compile(rf"^ROI\.0*{roi_num}\b.*")
    for c in columns:
        if patt_strict.match(c):
            return c
    # Fallback: plain 'ROI' + digits
    patt_loose = re.compile(rf"^ROI0*{roi_num}\b.*", re.IGNORECASE)
    for c in columns:
        if patt_loose.match(c):
            return c
    # Last resort: contains-but-unique
    candidates = [c for c in columns if re.search(rf"ROI\.?0*{roi_num}\b", c)]
    if len(candidates) == 1:
        return candidates[0]
    return None


def plot_single_roi_across_experiments(
    roi_num: int,
    batch_cfg: BatchConfig,
    base_cfg: Config,
    files_filter: Optional[Sequence[str]] = None,  # e.g. ["20s_1.csv", "2mW2.csv"] (filename or stem substrings)
    y_shift: float = 0.8,
    linewidth: float = 1.4,
    show_spikes: bool = True,
    spike_marker: str = "o",
    spike_size: int = 28,
    figsize: Tuple[float, float] = (12, 7),
    title: Optional[str] = None,
) -> plt.Figure:
    """
    Plot ΔF/F traces for a single ROI across multiple experiments on one y-shifted graph.
    Uses batch_cfg to discover files and base_cfg to compute ΔF/F and detect spikes.

    Args:
        roi_num: ROI number (e.g., 5 for ROI05).
        batch_cfg: your BatchConfig with input_folder and shared settings.
        base_cfg: a Config instance (will be copied and per-file csv_path set).
        files_filter: optional list of substrings to keep certain files (match on name or stem).
        y_shift: vertical offset applied cumulatively between traces.
        linewidth: line width for traces.
        show_spikes: overlay spike markers detected with your current thresholds.
        spike_marker: marker style.
        spike_size: marker size.
        figsize: figure size.
        title: custom title.

    Returns:
        Matplotlib Figure.
    """
    from dataclasses import replace

    files = discover_csv_files(batch_cfg)

    # Apply a simple include-filter by substring on filename or stem
    if files_filter:
        keep = []
        for p in files:
            name = p.name
            stem = p.stem
            if any(s in name or s in stem for s in files_filter):
                keep.append(p)
        files = keep

    if not files:
        raise ValueError("No CSV files found for plotting (after filtering).")

    fig, ax = plt.subplots(figsize=figsize)

    # palette
    cmap = plt.get_cmap("tab10")
    color_cycle = [cmap(i % 10) for i in range(20)]

    # keep track of y shift
    offset = 0.0
    plotted_any = False

    for i, csv_path in enumerate(files):
        # Clone base config and set the path
        cfg = replace(base_cfg)
        cfg.csv_path = str(csv_path)

        # Determine if spikes should be excluded for this file
        exclude_in_stim = should_exclude_spikes_in_stim(cfg.exclude_spikes_in_stim, str(csv_path))

        # Load and compute ΔF/F
        df = load_fluo_csv(cfg.csv_path, encoding=cfg.encoding, skip_first_row=cfg.skip_first_row)
        if cfg.time_col not in df.columns:
            print(f"[WARN] Time column '{cfg.time_col}' not in {csv_path.name}; skipping.")
            continue
        t = df[cfg.time_col].to_numpy(dtype=float)

        roi_cols_all = find_roi_columns(df, cfg.roi_key)
        if not roi_cols_all:
            print(f"[WARN] No ROI columns in {csv_path.name}; skipping.")
            continue

        roi_col = _find_roi_col_by_number(roi_cols_all, roi_num)
        if roi_col is None:
            print(f"[WARN] ROI {roi_num:02d} not found in {csv_path.name}; skipping.")
            continue

        # Background vector (interpolated if needed)
        try:
            bg_vec = select_background(df, cfg)
        except Exception as e:
            print(f"[WARN] Could not select background for {csv_path.name}: {e}; skipping.")
            continue

        # Compute DFF only for this ROI to save time
        F_corr = background_subtraction(df[roi_col].to_numpy(dtype=float), bg_vec)
        dff_vals, _ = dff_percentile_window(
            F_corr, t,
            window_half_s=cfg.baseline_window_half_s,
            percentile=cfg.baseline_percentile,
        )

        # Plot stim windows behind
        for s, e in cfg.stim_windows:
            ax.axvspan(s, e, color=cfg.stim_color, alpha=cfg.stim_alpha, zorder=0)

        # Plot the shifted trace
        color = color_cycle[i % len(color_cycle)]
        label = csv_path.stem  # e.g., "20s_1", "2mW2"
        ax.plot(t, dff_vals + offset, linewidth=linewidth, color=color, label=label)

        # Optionally detect and overlay spikes for THIS ROI
        if show_spikes:
            # Run your detector for this file, then pull just this ROI's peaks
            dff_table = pd.DataFrame({"Time (s)": t, roi_col: dff_vals})
            spike_summary_df, spike_stats_df, spike_times = detect_spikes_across_rois(
                dff_table=dff_table,
                roi_cols=[roi_col],
                time_col="Time (s)",
                baseline_range=(cfg.baseline_index_start, cfg.baseline_index_end),
                spike_z_sigma=cfg.spike_z_sigma,
                min_distance_s=cfg.min_spike_distance_s,
                width_mode=cfg.width_mode,
                width_threshold_s=cfg.width_threshold_s,
                stim_windows=cfg.stim_windows,
                exclude_spikes_in_windows=exclude_in_stim,
                stim_exclusion_pad_s=cfg.stim_exclusion_pad_s,
            )
            ptimes = spike_times.get(roi_col, np.array([], dtype=float))
            if ptimes.size > 0:
                # Grab y at those times for this ROI to position markers at (dff + offset)
                # Align times to nearest indices
                idxs = np.searchsorted(t, ptimes)
                idxs = np.clip(idxs, 0, len(t)-1)
                y_sp = dff_vals[idxs] + offset
                ax.scatter(ptimes, y_sp, s=spike_size, marker=spike_marker,
                           facecolors="none", edgecolors=color, linewidths=1.2, zorder=5)

        # Increment offset for next experiment
        offset += y_shift
        plotted_any = True

    if not plotted_any:
        raise RuntimeError("No traces were plotted (did the filters exclude everything?).")

    ax.set_xlabel("Time (s)")
    ax.set_ylabel(f"ΔF/F (y-shift={y_shift:g})")
    ttl = title or f"ROI{roi_num:02d} across experiments (y-shifted)"
    ax.set_title(ttl, fontweight="bold")

    # optional 0-line only for the first level (visual cue)
    ax.axhline(0.0, linestyle="--", linewidth=0.8, alpha=0.6)

    ax.legend(ncol=2, fontsize=9)
    ax.grid(True, axis="x", alpha=0.3, linestyle="--", linewidth=0.6)
    fig.tight_layout()
    return fig

def plot_single_roi_across_experiments_flat(
    roi_num: int,
    batch_cfg: BatchConfig,
    base_cfg: Config,
    files_filter: Optional[Sequence[str]] = None,  # e.g. ["20s_1", "2mW2"]
    y_step: float = 1.0,
    linewidth: float = 1.2,
    show_spikes: bool = True,
    spike_marker: str = "o",
    spike_size: int = 26,
    figsize: Tuple[float, float] = (12, 7),
    title: Optional[str] = None,
    out_path: Optional[str] = None,

    # NEW: fixed-scale options
    use_fixed_scale: bool = False,
    fixed_min: Optional[float] = None,
    fixed_max: Optional[float] = None,
) -> plt.Figure:
    """
    Plot one ROI across multiple experiments as horizontally stacked traces.
    Each experiment appears at a distinct y-level labeled by its experiment name.

    If use_fixed_scale is False (default), each experiment is normalized to its own
    [min, max] range before being shifted (current behavior).

    If use_fixed_scale is True, all experiments share the same normalization range:
        - If fixed_min/fixed_max are provided, use those.
        - Otherwise infer global min/max across all experiments for this ROI.
    """
    from dataclasses import replace

    files = discover_csv_files(batch_cfg)
    if files_filter:
        files = [p for p in files if any(f in p.name or f in p.stem for f in files_filter)]
    if not files:
        raise ValueError("No matching files found!")

    fig, ax = plt.subplots(figsize=figsize)
    cmap = plt.get_cmap("tab10")
    color_cycle = [cmap(i % 10) for i in range(20)]

    # --- FIRST PASS: load & compute dFF for each file, gather stats if needed ---
    traces = []  # each element: dict with keys: csv_path, cfg, t, dff_vals
    global_min = np.inf
    global_max = -np.inf

    for csv_path in sorted(files):
        cfg = replace(base_cfg)
        cfg.csv_path = str(csv_path)

        # Determine if spikes should be excluded for this file
        exclude_in_stim = should_exclude_spikes_in_stim(cfg.exclude_spikes_in_stim, str(csv_path))

        df = load_fluo_csv(cfg.csv_path, encoding=cfg.encoding, skip_first_row=cfg.skip_first_row)
        if cfg.time_col not in df.columns:
            continue

        t = df[cfg.time_col].to_numpy(dtype=float)
        roi_cols = find_roi_columns(df, cfg.roi_key)
        roi_col = _find_roi_col_by_number(roi_cols, roi_num)
        if roi_col is None:
            continue

        try:
            bg_vec = select_background(df, cfg)
        except Exception as e:
            print(f"[WARN] Could not select background for {csv_path.name}: {e}; skipping.")
            continue

        F_corr = background_subtraction(df[roi_col].to_numpy(dtype=float), bg_vec)
        dff_vals, _ = dff_percentile_window(
            F_corr, t, cfg.baseline_window_half_s, cfg.baseline_percentile
        )

        traces.append(
            {
                "csv_path": csv_path,
                "cfg": cfg,
                "t": t,
                "roi_col": roi_col,
                "dff_vals": dff_vals,
            }
        )

        # For fixed scale, track global min/max unless user provides explicit limits
        if use_fixed_scale or (fixed_min is not None or fixed_max is not None):
            local_min = float(np.nanmin(dff_vals))
            local_max = float(np.nanmax(dff_vals))
            global_min = min(global_min, local_min)
            global_max = max(global_max, local_max)

    if not traces:
        raise ValueError("No valid traces to plot for this ROI (check filters/ROI number).")

    # Determine normalization range for fixed scale (if requested)
    if fixed_min is not None or fixed_max is not None:
        # Use explicit values when provided; fall back to inferred global when missing
        norm_min = fixed_min if fixed_min is not None else global_min
        norm_max = fixed_max if fixed_max is not None else global_max
    else:
        # Auto from global stats
        norm_min = global_min
        norm_max = global_max

    if use_fixed_scale:
        denom_global = norm_max - norm_min
        if denom_global <= 0 or not np.isfinite(denom_global):
            denom_global = 1e-9  # fallback to avoid division by zero

    # --- SECOND PASS: actually plot ---
    for i, trace in enumerate(traces):
        csv_path = trace["csv_path"]
        cfg = trace["cfg"]
        t = trace["t"]
        roi_col = trace["roi_col"]
        dff_vals = trace["dff_vals"]

        # Choose normalization mode
        if use_fixed_scale:
            dff_norm = (dff_vals - norm_min) / (denom_global + 1e-9)
        else:
            local_min = float(np.nanmin(dff_vals))
            local_max = float(np.nanmax(dff_vals))
            denom = local_max - local_min
            if denom <= 0 or not np.isfinite(denom):
                denom = 1e-9
            dff_norm = (dff_vals - local_min) / (denom + 1e-9)

        # Offset by experiment index
        y_offset = i * y_step
        color = color_cycle[i % len(color_cycle)]

        # Shade stim windows (behind traces)
        for s, e in cfg.stim_windows:
            ax.axvspan(s, e, color=cfg.stim_color, alpha=0.2, zorder=0)

        # Plot normalized, shifted trace
        ax.plot(t, dff_norm + y_offset, color=color, lw=linewidth, label=None)

        # Optionally detect & overlay spikes
        if show_spikes:
            dff_table = pd.DataFrame({"Time (s)": t, roi_col: dff_vals})
            _, _, spike_times = detect_spikes_across_rois(
                dff_table=dff_table,
                roi_cols=[roi_col],
                time_col="Time (s)",
                baseline_range=(cfg.baseline_index_start, cfg.baseline_index_end),
                spike_z_sigma=cfg.spike_z_sigma,
                min_distance_s=cfg.min_spike_distance_s,
                width_mode=cfg.width_mode,
                width_threshold_s=cfg.width_threshold_s,
                stim_windows=cfg.stim_windows,
                exclude_spikes_in_windows=exclude_in_stim,
                stim_exclusion_pad_s=cfg.stim_exclusion_pad_s,
            )

            # Save raw dFF table for this ROI/file (unchanged behavior)
            out_csv = Path(batch_cfg.output_root) / f"dff_table_ROI{roi_num:02d}_{csv_path.stem}.csv"
            dff_table.to_csv(out_csv, index=False)
            print(f"💾 Saved {out_csv}")

            ptimes = spike_times.get(roi_col, np.array([], dtype=float))
            if ptimes.size:
                ax.scatter(
                    ptimes,
                    np.full_like(ptimes, y_offset),
                    marker=spike_marker,
                    s=spike_size,
                    facecolors="none",
                    edgecolors=color,
                    lw=1.2,
                    zorder=5,
                )

    # Y-axis labels (one per experiment)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Experiment #")
    ax.set_yticks(np.arange(len(traces)) * y_step)
    ax.set_yticklabels([t["csv_path"].stem for t in traces], fontsize=8)

    effective_title = title or f"ROI{roi_num:02d} traces across experiments"
    if use_fixed_scale:
        effective_title += f" (fixed scale [{norm_min:.2f}, {norm_max:.2f}])"
    ax.set_title(effective_title, fontweight="bold")

    ax.grid(True, axis="x", alpha=0.3, linestyle="--", lw=0.5)
    fig.tight_layout()

    if out_path:
        fig.savefig(out_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        print(f"✅ Saved to {out_path}")

    return fig

def compute_shared_baseline_from_files(
    file_paths: List[str],
    cfg: Config
) -> Dict[str, float]:
    """
    Compute shared baseline (F0) from specified files.

    Extracts frames [shared_baseline_start_frame : shared_baseline_end_frame]
    from each file, averages across all files, then computes F0 for each ROI.

    Parameters
    ----------
    file_paths : List[str]
        List of file paths to use for baseline calculation
    cfg : Config
        Configuration with shared_baseline_start_frame and shared_baseline_end_frame

    Returns
    -------
    baseline_dict : Dict[str, float]
        Dictionary mapping ROI names to baseline values (F0)
    """
    if not file_paths:
        return {}

    print(f"\n{'='*60}")
    print(f"Computing shared baseline from {len(file_paths)} file(s):")
    for fp in file_paths:
        print(f"  - {Path(fp).name}")
    print(f"Using frames {cfg.shared_baseline_start_frame} to {cfg.shared_baseline_end_frame}")
    print(f"{'='*60}\n")

    # Collect baseline frames from all files
    all_baseline_data = []  # List of DataFrames, each with ROI columns and baseline frames

    for file_path in file_paths:
        try:
            # Load CSV with proper path handling
            temp_cfg = copy.copy(cfg)
            temp_cfg.csv_path = str(file_path)

            # Load dataframe
            df = load_fluo_csv(
                file_path,
                encoding=cfg.encoding,
                skip_first_row=cfg.skip_first_row
            )

            # Get background for this file
            bg_vec = select_background(df, temp_cfg)

            # Extract baseline frames
            start_idx = cfg.shared_baseline_start_frame
            end_idx = cfg.shared_baseline_end_frame

            if end_idx > len(df):
                print(f"Warning: {Path(file_path).name} has only {len(df)} frames, "
                      f"requested baseline frames {start_idx}-{end_idx}. Using available frames.")
                end_idx = len(df)

            # Get ROI columns (excluding time column)
            roi_columns = [col for col in df.columns if cfg.roi_key in col and col != cfg.time_col]

            # For each ROI, apply background subtraction to baseline frames
            baseline_data_dict = {}
            for roi_col in roi_columns:
                # Get raw fluorescence for baseline frames
                F_raw = df[roi_col].iloc[start_idx:end_idx].to_numpy(dtype=float)
                # Apply background subtraction
                bg_for_frames = bg_vec[start_idx:end_idx]
                F_corrected = F_raw - bg_for_frames
                baseline_data_dict[roi_col] = F_corrected

            baseline_data = pd.DataFrame(baseline_data_dict)
            all_baseline_data.append(baseline_data)

        except Exception as e:
            print(f"Error loading {file_path}: {e}")
            import traceback
            traceback.print_exc()
            continue

    if not all_baseline_data:
        print("Warning: No baseline data could be loaded. Returning empty baseline.")
        return {}

    # Concatenate all baseline data
    combined_baseline = pd.concat(all_baseline_data, axis=0, ignore_index=True)

    # Compute F0 for each ROI (using percentile like standard baseline)
    baseline_dict = {}
    skipped_rois = []
    for roi_col in combined_baseline.columns:
        roi_data = combined_baseline[roi_col].values
        # Use percentile method (same as standard baseline)
        f0 = np.percentile(roi_data, cfg.baseline_percentile)

        # Skip ROIs with F0 too close to zero (would cause division by zero)
        # This typically happens with background ROI after background subtraction
        if abs(f0) < 1.0:
            print(f"  {roi_col}: F0 = {f0:.3f} (SKIPPED - too close to zero)")
            skipped_rois.append(roi_col)
            continue

        baseline_dict[roi_col] = f0
        print(f"  {roi_col}: F0 = {f0:.3f}")

    print(f"\nShared baseline computed for {len(baseline_dict)} ROIs")
    if skipped_rois:
        print(f"Skipped {len(skipped_rois)} ROIs with F0 near zero: {', '.join(skipped_rois)}")
        print("These ROIs will use standard sliding window baseline instead.")
    print()
    return baseline_dict


def identify_control_files(file_paths: List[str], control_pattern: str) -> List[str]:
    """
    Identify control files from a list of file paths based on a pattern.

    Parameters
    ----------
    file_paths : List[str]
        List of all file paths
    control_pattern : str
        Pattern to match control files (e.g., "Ctrl")

    Returns
    -------
    control_files : List[str]
        List of file paths that match the control pattern
    """
    control_files = [
        fp for fp in file_paths
        if control_pattern.lower() in Path(fp).stem.lower()
    ]
    return control_files


def identify_first_files_per_condition(file_paths: List[str]) -> Dict[str, str]:
    """
    Identify the first file for each condition.

    A file is considered "first" if:
    - It has no number suffix (e.g., "20s.csv")
    - OR it ends with "1" (e.g., "20s1.csv")

    Parameters
    ----------
    file_paths : List[str]
        List of all file paths

    Returns
    -------
    first_files_dict : Dict[str, str]
        Dictionary mapping condition name to first file path
        e.g., {"20s": "path/to/20s1.csv", "10s": "path/to/10s1.csv"}
    """
    import re

    first_files = {}

    for fp in file_paths:
        stem = Path(fp).stem  # e.g., "20s1", "20s2", "Ctrl", "10s"

        # Try to extract condition name and number
        # Pattern: look for letters/numbers followed by optional digit(s)
        match = re.match(r'^([a-zA-Z0-9]+?)(\d*)$', stem)

        if match:
            condition = match.group(1)  # e.g., "20s", "10s", "Ctrl"
            number = match.group(2)      # e.g., "1", "2", "" (empty)

            # Consider as "first" if no number or number is "1"
            if number == "" or number == "1":
                # Only keep the first occurrence for each condition
                if condition not in first_files:
                    first_files[condition] = fp
                    print(f"First file for condition '{condition}': {Path(fp).name}")

    return first_files


def run(cfg: Config):
    df = load_fluo_csv(cfg.csv_path, encoding=cfg.encoding, skip_first_row=cfg.skip_first_row)

    if cfg.time_col not in df.columns:
        raise ValueError(f"Time column '{cfg.time_col}' not found. Columns: {list(df.columns)}")
    time = df[cfg.time_col].to_numpy()

    roi_cols = find_roi_columns(df, cfg.roi_key)
    if not roi_cols:
        raise ValueError(f"No ROI columns found using key '{cfg.roi_key}'.")

    bg_vec = select_background(df, cfg)
    bg_is_roi = (cfg.bg_source == "roi_column")

    dff_table = compute_all_dff(df, roi_cols, bg_vec, time, cfg)

    roi_cols_for_detection = list(roi_cols)
    if (cfg.bg_source == "roi_column") and cfg.exclude_bg_roi_from_detection:
        roi_cols_for_detection = [c for c in roi_cols_for_detection if c != cfg.bg_column_name]

    # Determine if spikes should be excluded based on mode and filename
    exclude_in_stim = should_exclude_spikes_in_stim(cfg.exclude_spikes_in_stim, cfg.csv_path)

    spike_summary_df, spike_stats_df, spike_times = detect_spikes_across_rois(
        dff_table=dff_table,
        roi_cols=roi_cols_for_detection,
        time_col="Time (s)",
        baseline_range=(cfg.baseline_index_start, cfg.baseline_index_end),
        spike_z_sigma=cfg.spike_z_sigma,
        min_distance_s=cfg.min_spike_distance_s,
        width_mode=cfg.width_mode,
        width_threshold_s=cfg.width_threshold_s,
        stim_windows=cfg.stim_windows,
        exclude_spikes_in_windows=exclude_in_stim,
        stim_exclusion_pad_s=cfg.stim_exclusion_pad_s,
    )

    # Calculate spike latencies if requested
    if cfg.calculate_spike_latencies:
        method = getattr(cfg, 'latency_method', 'nearest')
        print(f"Latency method: {method}")

        if method == "first_spike":
            latencies_dict, latency_stats_df, latency_detailed_df = calculate_first_spike_latencies(
                spike_times=spike_times,
                stim_windows=cfg.stim_windows,
                max_latency_window_s=cfg.max_latency_window_s,
            )
        elif method == "stim_onset":
            latencies_dict, latency_stats_df, latency_detailed_df = calculate_stim_onset_latencies(
                spike_times=spike_times,
                stim_windows=cfg.stim_windows,
                max_latency_window_s=cfg.max_latency_window_s,
            )
        elif method == "glm":
            time_arr = dff_table["Time (s)"].values
            latencies_dict, latency_stats_df, latency_detailed_df = calculate_glm_latencies(
                spike_times=spike_times,
                stim_windows=cfg.stim_windows,
                time_array=time_arr,
                max_latency_window_s=cfg.max_latency_window_s,
            )
        else:  # "nearest" (default, original method)
            latencies_dict, latency_stats_df, latency_detailed_df = calculate_spike_latencies(
                spike_times=spike_times,
                stim_windows=cfg.stim_windows,
                max_latency_window_s=cfg.max_latency_window_s,
            )

        # Save latency results
        if cfg.out_spike_latency_stats_csv:
            latency_stats_df.to_csv(cfg.out_spike_latency_stats_csv, index=False)
            print(f"Saved spike latency stats to {cfg.out_spike_latency_stats_csv}")

        if cfg.out_spike_latency_detailed_csv:
            latency_detailed_df.to_csv(cfg.out_spike_latency_detailed_csv, index=False)
            print(f"Saved detailed spike latencies to {cfg.out_spike_latency_detailed_csv}")

    if cfg.out_spike_csv:
        tmp = spike_summary_df.copy()
        tmp["spike_times_s"] = tmp["ROI"].map(lambda r: ";".join(f"{x:.3f}" for x in spike_times.get(r, [])))
        tmp.to_csv(cfg.out_spike_csv, index=False)

    if cfg.out_spike_stats_csv:
        spike_stats_df.to_csv(cfg.out_spike_stats_csv, index=False)

    fig_all = plot_dff(
        dff_table=dff_table,
        roi_cols=roi_cols,
        cfg=cfg,
        bg_was_roi=bg_is_roi,
        spike_times=spike_times,
    )
    if fig_all.axes:
        fig_all.axes[0].set_title("ΔF/F (all ROIs)")

    if cfg.out_fig:
        fig_all.savefig(cfg.out_fig, dpi=300, bbox_inches="tight")

    roi_cols_spiking = spike_summary_df["ROI"].tolist()
    fig_spk = None
    if cfg.show_spiking_only_figure and len(roi_cols_spiking) > 0:
        fig_spk = plot_dff(
            dff_table=dff_table,
            roi_cols=roi_cols_spiking,
            cfg=cfg,
            bg_was_roi=bg_is_roi,
            spike_times=spike_times,
        )
        if fig_spk.axes:
            fig_spk.axes[0].set_title("ΔF/F (ROIs with spikes)")

        if cfg.out_fig_spiking_only:
            fig_spk.savefig(cfg.out_fig_spiking_only, dpi=300, bbox_inches="tight")

    if cfg.out_csv:
        dff_table.to_csv(cfg.out_csv, index=False)

    return dff_table, fig_all, fig_spk


# BATCH PROCESSING FUNCTIONS

def parse_experiment_filename(filename: str) -> Optional[Tuple[str, int]]:
    name = Path(filename).stem
    pattern1 = r"^([a-zA-Z0-9]+?)(\d+)$"
    match = re.match(pattern1, name)
    if match:
        return (match.group(1), int(match.group(2)))
    pattern2 = r"^(\d+)-(\d+)$"
    match = re.match(pattern2, name)
    if match:
        return (match.group(1), int(match.group(2)))
    pattern3 = r"^([a-zA-Z0-9]+)$"
    match = re.match(pattern3, name)
    if match:
        return (match.group(1), 1)
    return None


def extract_roi_number(roi_name: str) -> Optional[int]:
    match = re.search(r"ROI\.0*(\d+)", roi_name)
    if match:
        return int(match.group(1))
    return None


def discover_csv_files(batch_cfg: BatchConfig) -> List[Path]:
    folder = Path(batch_cfg.input_folder)
    if not folder.exists():
        raise FileNotFoundError(f"Input folder not found: {folder}")
    files = sorted(folder.glob(batch_cfg.file_pattern))
    if not files:
        raise ValueError(f"No files found matching pattern '{batch_cfg.file_pattern}' in {folder}")
    return files


def process_single_file(
        csv_path: Path,
        base_config: Config,
        output_dir: Path,
        overrides: Optional[Dict] = None
) -> Tuple[bool, Optional[pd.DataFrame], Optional[str]]:
    from dataclasses import replace
    import matplotlib
    matplotlib.use("Agg")

    try:
        cfg = replace(base_config)
        cfg.csv_path = str(csv_path)

        if overrides:
            for key, value in overrides.items():
                setattr(cfg, key, value)

        if not overrides or ("stim_preset" not in overrides and cfg.stim_preset_infer_from_name):
            apply_inferred_stim_preset(cfg, name_hint=csv_path.name)


        output_dir.mkdir(parents=True, exist_ok=True)
        cfg.out_fig = str(output_dir / "deltaF_F_plot_all.png")
        cfg.out_fig_spiking_only = str(output_dir / "deltaF_F_spiking_only.png")
        cfg.out_spike_csv = str(output_dir / "spike_summary.csv")
        cfg.out_spike_stats_csv = str(output_dir / "spike_baseline_stats.csv")
        cfg.out_spike_latency_stats_csv = str(output_dir / "spike_latency_stats.csv")
        cfg.out_spike_latency_detailed_csv = str(output_dir / "spike_latency_detailed.csv")

        dff_table, fig_all, fig_spk = run(cfg)

        plt.close(fig_all)
        if fig_spk is not None:
            plt.close(fig_spk)

        spike_summary_path = output_dir / "spike_summary.csv"
        if spike_summary_path.exists():
            spike_df = pd.read_csv(spike_summary_path)
        else:
            spike_df = pd.DataFrame(columns=["ROI", "n_spikes"])

        return (True, spike_df, None)

    except Exception as e:
        import traceback
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        return (False, None, error_msg)


def run_batch(batch_cfg: BatchConfig) -> pd.DataFrame:
    csv_files = discover_csv_files(batch_cfg)

    output_root = Path(batch_cfg.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    results = []

    if HAS_TQDM and batch_cfg.verbose:
        iterator = tqdm(csv_files, desc="Processing files")
    else:
        iterator = csv_files

    for csv_path in iterator:
        filename = csv_path.name

        if batch_cfg.verbose and not HAS_TQDM:
            print(f"Processing: {filename}")

        parsed = parse_experiment_filename(filename)
        if parsed:
            group, replicate = parsed
        else:
            group, replicate = filename, None

        output_dir = output_root / csv_path.stem

        overrides = batch_cfg.per_file_overrides.get(filename, {})

        success, spike_df, error = process_single_file(
            csv_path, batch_cfg.shared_config, output_dir, overrides
        )

        if success:
            n_rois = len(spike_df)
            n_spiking = (spike_df["n_spikes"] > 0).sum() if n_rois > 0 else 0
            total_spikes = spike_df["n_spikes"].sum() if n_rois > 0 else 0

            results.append({
                "filename": filename,
                "group": group,
                "replicate": replicate,
                "n_rois": n_rois,
                "n_spiking_rois": n_spiking,
                "total_spikes": total_spikes,
                "status": "success",
                "error": None
            })

        else:
            results.append({
                "filename": filename,
                "group": group,
                "replicate": replicate,
                "n_rois": None,
                "n_spiking_rois": None,
                "total_spikes": None,
                "status": "failed",
                "error": error
            })

            if not batch_cfg.continue_on_error:
                raise RuntimeError(f"Processing failed for {filename}: {error}")

    summary_df = pd.DataFrame(results)
    summary_path = output_root / "batch_processing_summary.csv"
    summary_df.to_csv(summary_path, index=False)

    if batch_cfg.verbose:
        print(f"\n{'=' * 60}")
        print(f"Batch processing complete!")
        print(f"Processed: {len(csv_files)} files")
        print(f"Success: {(summary_df['status'] == 'success').sum()}")
        print(f"Failed: {(summary_df['status'] == 'failed').sum()}")
        print(f"Summary saved to: {summary_path}")
        print(f"{'=' * 60}\n")

    return summary_df


def create_spike_summary_table(
        batch_cfg: BatchConfig,
        batch_summary: Optional[pd.DataFrame] = None
) -> pd.DataFrame:
    output_root = Path(batch_cfg.output_root)

    all_spikes = []

    for subdir in output_root.iterdir():
        if not subdir.is_dir():
            continue

        spike_file = subdir / "spike_summary.csv"
        if not spike_file.exists():
            continue

        spike_df = pd.read_csv(spike_file)

        parsed = parse_experiment_filename(subdir.name)
        if not parsed:
            continue

        group, replicate = parsed

        for _, row in spike_df.iterrows():
            roi_name = row["ROI"]
            roi_num = extract_roi_number(roi_name)
            n_spikes = row["n_spikes"]

            if roi_num is not None:
                all_spikes.append({
                    "Parameter": group,
                    "Replicate": replicate,
                    "ROI": roi_num,
                    "n_spikes": n_spikes
                })

    if not all_spikes:
        print("Warning: No spike data found!")
        return pd.DataFrame()

    df = pd.DataFrame(all_spikes)

    if not batch_cfg.include_zero_spike_rois:
        df = df[df["n_spikes"] > 0]

    pivot = df.pivot_table(
        index=["Parameter", "Replicate"],
        columns="ROI",
        values="n_spikes",
        aggfunc="first"
    )

    pivot = pivot.sort_index(axis=1)
    pivot = pivot.sort_index(axis=0)

    csv_path = output_root / batch_cfg.summary_table_path
    pivot.to_csv(csv_path)

    if batch_cfg.summary_table_excel:
        try:
            excel_path = output_root / batch_cfg.summary_table_excel
            pivot.to_excel(excel_path)
        except ImportError:
            print("Warning: openpyxl not installed. Skipping Excel output.")

    if batch_cfg.verbose:
        print(f"\nSpike summary table created:")
        print(f"  CSV: {csv_path}")
        if batch_cfg.summary_table_excel:
            print(f"  Excel: {excel_path}")
        print(f"\nTable shape: {pivot.shape[0]} experiments x {pivot.shape[1]} ROIs")
        print(f"\nPreview:")
        print(pivot.head(10))

    return pivot


def batch_process_and_summarize(batch_cfg: BatchConfig) -> Tuple[pd.DataFrame, pd.DataFrame]:
    batch_summary = run_batch(batch_cfg)
    spike_table = create_spike_summary_table(batch_cfg, batch_summary)
    return batch_summary, spike_table


def collect_all_spike_timestamps(batch_cfg: BatchConfig) -> pd.DataFrame:
    """
    Collect all spike timestamps from individual spike_summary.csv files.

    Returns:
        DataFrame with columns: [Parameter, Replicate, ROI, spike_time_s]
        Each row represents one spike event.
    """
    output_root = Path(batch_cfg.output_root)

    all_spike_events = []

    for subdir in output_root.iterdir():
        if not subdir.is_dir():
            continue

        spike_file = subdir / "spike_summary.csv"
        if not spike_file.exists():
            continue

        spike_df = pd.read_csv(spike_file)

        parsed = parse_experiment_filename(subdir.name)
        if not parsed:
            continue

        group, replicate = parsed

        # Check if spike_times_s column exists
        if "spike_times_s" not in spike_df.columns:
            continue

        for _, row in spike_df.iterrows():
            roi_name = row["ROI"]
            roi_num = extract_roi_number(roi_name)

            if roi_num is None:
                continue

            # Parse semicolon-separated spike times
            spike_times_str = str(row["spike_times_s"])
            if spike_times_str and spike_times_str != "nan" and spike_times_str != "":
                times = [float(t.strip()) for t in spike_times_str.split(";") if t.strip()]

                for spike_time in times:
                    all_spike_events.append({
                        "Parameter": group,
                        "Replicate": replicate,
                        "ROI": roi_num,
                        "spike_time_s": spike_time,
                    })

    if not all_spike_events:
        print("Warning: No spike timestamps found!")
        return pd.DataFrame(columns=["Parameter", "Replicate", "ROI", "spike_time_s"])

    df = pd.DataFrame(all_spike_events)

    # Sort by Parameter, Replicate, ROI, and time
    df = df.sort_values(["Parameter", "Replicate", "ROI", "spike_time_s"]).reset_index(drop=True)

    # Save to CSV
    output_path = output_root / "all_spike_timestamps.csv"
    df.to_csv(output_path, index=False)

    if batch_cfg.verbose:
        print(f"\nSpike timestamps collected: {len(df)} total spike events")
        print(f"Saved to: {output_path}")

    return df


def collect_all_spike_latencies(batch_cfg: BatchConfig) -> pd.DataFrame:
    """
    Collect all spike latencies from individual spike_latency_detailed.csv files.

    Returns:
        DataFrame with columns: [Parameter, Replicate, ROI, ROI_num, spike_time_s,
        latency_s, stim_window_start_s, stim_window_end_s]
        Each row represents one spike event with its latency.
    """
    output_root = Path(batch_cfg.output_root)

    all_latency_events = []

    for subdir in output_root.iterdir():
        if not subdir.is_dir():
            continue

        latency_file = subdir / "spike_latency_detailed.csv"
        if not latency_file.exists():
            continue

        try:
            latency_df = pd.read_csv(latency_file)
        except pd.errors.EmptyDataError:
            # Skip empty files (files with no latencies)
            continue

        if latency_df.empty:
            continue

        parsed = parse_experiment_filename(subdir.name)
        if not parsed:
            continue

        group, replicate = parsed

        for _, row in latency_df.iterrows():
            roi_name = row["ROI"]
            roi_num = extract_roi_number(roi_name)

            if roi_num is None:
                continue

            all_latency_events.append({
                "Parameter": group,
                "Replicate": replicate,
                "ROI": roi_name,
                "ROI_num": roi_num,
                "spike_time_s": row["spike_time_s"],
                "latency_s": row["latency_s"],
                "stim_window_start_s": row["stim_window_start_s"],
                "stim_window_end_s": row["stim_window_end_s"],
            })

    if not all_latency_events:
        print("Warning: No spike latencies found!")
        return pd.DataFrame(columns=["Parameter", "Replicate", "ROI", "ROI_num",
                                      "spike_time_s", "latency_s",
                                      "stim_window_start_s", "stim_window_end_s"])

    df = pd.DataFrame(all_latency_events)

    # Sort by Parameter, Replicate, ROI, and spike time
    df = df.sort_values(["Parameter", "Replicate", "ROI_num", "spike_time_s"]).reset_index(drop=True)

    # Save to CSV
    output_path = output_root / "all_spike_latencies.csv"
    df.to_csv(output_path, index=False)

    if batch_cfg.verbose:
        print(f"\nSpike latencies collected: {len(df)} total spike events with latencies")
        print(f"Saved to: {output_path}")

    return df


def plot_raster(
    spike_timestamps_df: pd.DataFrame,
    output_path: Optional[str] = None,
    figsize: Tuple[float, float] = (12, 8),
    marker: str = "s",            # square
    marker_size: int = 260,       # bigger
    marker_color: str = "orange",
    title: str = "Raster Plot: Individual Spike Events per ROI & Condition",
    xlabel: str = "Condition",
    ylabel: str = "ROI",
    show_replicate_labels: bool = True,
    roi_sort_order: Optional[List[int]] = None,
    condition_order: Optional[List[str]] = None,
    highlight_control: bool = True,
    control_keywords: List[str] = None,
    highlight_color: str = "lightgreen",
    highlight_alpha: float = 0.25,
    square_edgecolor: str = "k",     # NEW
    square_edgewidth: float = 0.9,   # NEW
    tighten_grid: bool = True,       # NEW
) -> plt.Figure:

    """
    Create a raster plot showing individual spike events.

    Args:
        spike_timestamps_df: DataFrame with columns [Parameter, Replicate, ROI, spike_time_s]
        output_path: Path to save figure (optional)
        figsize: Figure size (width, height)
        marker: Marker style for spikes
        marker_size: Size of spike markers
        marker_color: Color of spike markers
        title: Plot title
        xlabel: X-axis label
        ylabel: Y-axis label
        show_replicate_labels: If True, show replicate numbers below condition names
        roi_sort_order: Custom ROI ordering (list of ROI numbers)
        condition_order: Custom condition ordering (list of condition names)
        highlight_control: If True, highlight ROIs that have spikes in control groups
        control_keywords: List of keywords to identify control groups (e.g., ["Ctrl", "ctrl"])
        highlight_color: Color for highlighting control ROIs
        highlight_alpha: Transparency for highlighting

    Returns:
        matplotlib Figure object
    """
    if spike_timestamps_df.empty:
        print("Warning: No spike data to plot!")
        return None

    df = spike_timestamps_df.copy()

    # Default control keywords
    if control_keywords is None:
        control_keywords = ["Ctrl", "ctrl", "Control", "control"]

    # ----- Build clean condition labels -----
    def _rep_str(x):
        # "" if NA, else integer-like string (1, 2, 3 …)
        return "" if pd.isna(x) else str(int(x))

    if show_replicate_labels:
        df["Condition"] = df["Parameter"].astype(str) + df["Replicate"].apply(_rep_str)
    else:
        df["Condition"] = df["Parameter"].astype(str)

    # ----- Unique, stable condition order -----
    if condition_order is None:
        # Drop duplicate (Parameter, Replicate) pairs in FIRST occurrence order
        cond_df = (
            df.assign(_rep_clean=df["Replicate"].apply(lambda r: None if pd.isna(r) else int(r)))
            .drop_duplicates(["Parameter", "_rep_clean"], keep="first")
        )
        conditions = cond_df["Condition"].tolist()
    else:
        conditions = list(condition_order)

    # Determine ROI order
    if roi_sort_order is None:
        roi_list = sorted(df["ROI"].unique())
    else:
        roi_list = list(roi_sort_order)

    # Identify ROIs with spikes in control conditions
    control_rois = set()
    if highlight_control:
        for keyword in control_keywords:
            control_df = df[df["Parameter"].str.contains(keyword, case=False, na=False)]
            control_rois.update(control_df["ROI"].unique())

    # Create figure
    fig, ax = plt.subplots(figsize=figsize)

    # Map conditions and ROIs to numeric positions
    condition_to_x = {cond: i for i, cond in enumerate(conditions)}
    roi_to_y = {roi: i for i, roi in enumerate(roi_list)}

    # Highlight control ROI rows FIRST (background layer)
    if highlight_control and control_rois:
        for roi in control_rois:
            if roi in roi_to_y:
                y_pos = roi_to_y[roi]
                ax.axhspan(y_pos - 0.4, y_pos + 0.4,
                           color=highlight_color, alpha=highlight_alpha, zorder=0)

    # Plot each spike as a marker
    for _, row in df.iterrows():
        cond = row["Condition"]
        roi = row["ROI"]

        if cond in condition_to_x and roi in roi_to_y:
            x_pos = condition_to_x[cond]
            y_pos = roi_to_y[roi]

            ax.scatter(
                x_pos, y_pos,
                marker=marker,
                s=marker_size,
                facecolors=marker_color,
                edgecolors=square_edgecolor,
                linewidths=square_edgewidth,
                alpha=0.95,
                zorder=2,
            )

    # Set up axes
    ax.set_xticks(range(len(conditions)))
    ax.set_xticklabels(conditions, rotation=45, ha="right")

    ax.set_yticks(range(len(roi_list)))
    y_labels = []
    for roi in roi_list:
        label = f"ROI{roi:02d}"
        if highlight_control and roi in control_rois:
            label += " ★"  # Add star to indicate control ROI
        y_labels.append(label)
    ax.set_yticklabels(y_labels)

    ax.set_xlabel(xlabel, fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(title, fontsize=14, fontweight="bold")

    # Add grid for better readability
    ax.grid(True, axis="both", alpha=0.3, linestyle="--", linewidth=0.5)

    # Set limits with some padding
    ax.set_xlim(-0.5, len(conditions) - 0.5)
    ax.set_ylim(-0.5, len(roi_list) - 0.5)

    # Add legend for highlighting
    if highlight_control and control_rois:
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor=highlight_color, alpha=highlight_alpha,
                  label=f'ROIs with spikes in control (n={len(control_rois)})')
        ]
        ax.legend(handles=legend_elements, loc='upper left', fontsize=9)
    # Optional: make cells read like a grid
    if tighten_grid:
        # make tick lines align with “cells”
        ax.set_xlim(-0.6, len(conditions) - 0.4)
        ax.set_ylim(-0.6, len(roi_list) - 0.4)
        # equal-ish cell feel (doesn't force perfect squares but helps)
        ax.set_aspect("auto")
        # stronger grid lines
        ax.grid(True, which="major", axis="both", alpha=0.35, linestyle="--", linewidth=0.6)
        # a faint frame
        for spine in ax.spines.values():
            spine.set_alpha(0.6)

    fig.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=300, bbox_inches="tight")
        print(f"Raster plot saved to: {output_path}")

    return fig
from pathlib import Path

def list_all_roi_numbers(
    batch_cfg: BatchConfig,
    base_cfg: Config,
    files_filter: Optional[List[str]] = None,
    max_files: Optional[int] = None,
) -> List[int]:
    """
    Scan CSVs and return the sorted union of ROI numbers present.
    """
    files = discover_csv_files(batch_cfg)
    if files_filter:
        files = [p for p in files if any(f in p.name or f in p.stem for f in files_filter)]
    if max_files is not None:
        files = files[:max_files]

    roi_nums: set[int] = set()
    for csv_path in files:
        try:
            df = load_fluo_csv(str(csv_path), encoding=base_cfg.encoding, skip_first_row=base_cfg.skip_first_row)
            roi_cols = find_roi_columns(df, base_cfg.roi_key)
            for c in roi_cols:
                n = extract_roi_number(c)
                if n is not None:
                    roi_nums.add(n)
        except Exception as e:
            print(f"[WARN] Could not inspect {csv_path.name}: {e}")
            continue

    return sorted(roi_nums)


def _load_condition_data(
    analysis_output_folder: str,
    selected_conditions: Optional[List[str]] = None,
    stim_preset_mode: str = "auto",
) -> Dict:
    """Load ΔF/F data and spike info from analysis output subfolders."""
    import pandas as pd

    parent_folder = Path(analysis_output_folder)
    if not parent_folder.exists():
        raise FileNotFoundError(f"Analysis output folder not found: {parent_folder}")

    subfolders = [f for f in parent_folder.iterdir() if f.is_dir()]
    if not subfolders:
        raise ValueError(f"No subfolders found in {parent_folder}")

    if selected_conditions:
        subfolders = [f for f in subfolders if f.name in selected_conditions]
    if not subfolders:
        raise ValueError("No matching conditions found")

    presets = {
        "20s": [(30, 50), (80, 100), (130, 150)],
        "10s": [(30, 40), (70, 80), (110, 120)],
        "5s": [(30, 35), (65, 70), (100, 105)],
        "none": [],
    }
    valid_stim_modes = {"auto", *presets.keys()}
    if stim_preset_mode not in valid_stim_modes:
        raise ValueError(
            f"Invalid stim_preset_mode='{stim_preset_mode}'. "
            f"Expected one of: {sorted(valid_stim_modes)}"
        )

    condition_data = {}
    all_roi_names = set()

    for subfolder in subfolders:
        condition_name = subfolder.name
        dff_file = subfolder / "dff_table.csv"
        spike_file = subfolder / "spike_summary.csv"

        if not dff_file.exists():
            print(f"[SKIP] {condition_name}: dff_table.csv not found")
            continue
        try:
            dff_df = pd.read_csv(dff_file)
            roi_cols = [col for col in dff_df.columns if col != "Time (s)"]
            all_roi_names.update(roi_cols)

            spike_times_dict = {}
            if spike_file.exists():
                spike_df = pd.read_csv(spike_file)
                if "spike_times_s" in spike_df.columns:
                    for _, row in spike_df.iterrows():
                        roi_name = row["ROI"]
                        times_str = str(row["spike_times_s"])
                        if times_str and times_str != "nan":
                            times = [float(t.strip()) for t in times_str.split(";") if t.strip()]
                            spike_times_dict[roi_name] = np.array(times)

            if stim_preset_mode == "auto":
                stim_preset = infer_stim_preset_from_string(condition_name)
            else:
                stim_preset = stim_preset_mode

            condition_data[condition_name] = {
                "dff_df": dff_df,
                "spike_times": spike_times_dict,
                "stim_preset": stim_preset,
                "stim_windows": presets.get(stim_preset, []),
            }
            print(
                f"[OK] {condition_name}: {len(roi_cols)} ROIs, "
                f"{len(spike_times_dict)} with spikes, stim={stim_preset}"
            )

        except Exception as e:
            print(f"[ERROR] {condition_name}: {str(e)}")
            continue

    if not condition_data:
        raise ValueError("No valid condition data loaded")

    return condition_data, all_roi_names


def plot_multi_roi_traces_svg(
    analysis_output_folder: str,
    selected_conditions: Optional[List[str]] = None,
    selected_rois: Optional[List[str]] = None,
    output_path: Optional[str] = None,
    layout_mode: str = "stacked",
    figsize: Tuple[float, float] = (16, 12),
    show_stim_windows: bool = True,
    show_spike_markers: bool = True,
    condition_offset: str = "none",   # "none", "auto", "manual"
    manual_offset_value: float = 0.5,
    label_right_margin: float = 0.10,
    stim_preset_mode: str = "auto",   # "auto", "20s", "10s", "5s", "none"
) -> str:
    """
    Plot ΔF/F traces from multiple conditions/ROIs to SVG with
    optional per-condition vertical offset and end-of-trace labels.

    Parameters
    ----------
    analysis_output_folder : str
        Path to analysis output folder with one subfolder per condition.
    selected_conditions, selected_rois : Optional[List[str]]
        Filter lists.  None = include all.
    output_path : Optional[str]
        Destination SVG.  None = auto-named inside *analysis_output_folder*.
    layout_mode : str
        "stacked" (one subplot per ROI), "grid", or "overlay".
    figsize : Tuple[float,float]
        Figure size in inches.
    show_stim_windows, show_spike_markers : bool
        Toggle helpers.
    condition_offset : str
        "none"   - all conditions share the same y-axis (overlaid).
        "auto"   - automatically compute offset so traces don't overlap.
        "manual" - use *manual_offset_value* between consecutive conditions.
    manual_offset_value : float
        Vertical shift between conditions when condition_offset="manual".
    label_right_margin : float
        Fraction of x-axis reserved on the right for end-of-trace labels
        (0.06 = 6 %).
    stim_preset_mode : str
        "auto" infers per condition from folder/file name (e.g., 5s1, 10s2),
        otherwise force one preset for all conditions ("20s", "10s", "5s", "none").

    Returns
    -------
    str   Path to saved SVG.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    parent_folder = Path(analysis_output_folder)

    print(f"\n{'='*60}")
    print(f"Loading data ...")
    print(f"{'='*60}\n")

    condition_data, all_roi_names = _load_condition_data(
        analysis_output_folder, selected_conditions, stim_preset_mode=stim_preset_mode
    )

    if selected_rois:
        all_roi_names = set(selected_rois) & all_roi_names
    roi_names_sorted = sorted(all_roi_names)
    if not roi_names_sorted:
        raise ValueError("No matching ROIs found")

    cond_names_sorted = sorted(condition_data.keys())
    n_cond = len(cond_names_sorted)
    n_roi = len(roi_names_sorted)

    print(f"Generating {layout_mode} plot: {n_roi} ROI(s) x {n_cond} condition(s), "
          f"offset={condition_offset}")

    # ---- Colour palette (distinct, colourblind-friendly-ish) ----
    _base = plt.get_cmap("tab10")
    condition_colors = {c: _base(i % 10) for i, c in enumerate(cond_names_sorted)}

    # ---- Publication styling ----
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 11,
        "axes.linewidth": 1.2,
        "axes.labelsize": 12,
        "axes.titlesize": 13,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "svg.fonttype": "none",        # keep text as text in SVG
    })

    use_offset = condition_offset in ("auto", "manual")

    # ---- Reserve right margin for labels ----
    right_frac = 1.0 - label_right_margin if use_offset else 0.98

    # ---- Create figure ----
    if layout_mode == "stacked":
        height_per_roi = max(2.5, figsize[1] / max(n_roi, 1))
        actual_h = height_per_roi * n_roi + 1.0
        fig, axes = plt.subplots(
            n_roi, 1,
            figsize=(figsize[0], actual_h),
            sharex=True, squeeze=False,
        )
        axes = axes.flatten()
    elif layout_mode == "grid":
        n_cols = min(3, n_cond)
        n_rows = (n_roi + n_cols - 1) // n_cols
        fig, axes = plt.subplots(
            n_rows, n_cols,
            figsize=figsize,
            sharex=True, squeeze=False,
        )
        axes = axes.flatten()
    else:  # overlay
        fig, ax_single = plt.subplots(figsize=figsize)
        axes = [ax_single]

    fig.patch.set_facecolor("white")

    # ---- Helper: compute auto offset for one ROI across conditions ----
    def _auto_offset_for_roi(roi_name: str) -> float:
        """Return an offset large enough to visually separate conditions."""
        spans = []
        for cn in cond_names_sorted:
            dff_df = condition_data[cn]["dff_df"]
            if roi_name not in dff_df.columns:
                continue
            vals = dff_df[roi_name].values
            finite = vals[np.isfinite(vals)]
            if finite.size > 0:
                spans.append(float(np.max(finite) - np.min(finite)))
        if not spans:
            return 0.5
        return float(np.median(spans)) * 1.2

    # ---- Plot ----
    plot_idx = 0
    for roi_idx, roi_name in enumerate(roi_names_sorted):
        if layout_mode in ("stacked", "grid"):
            ax = axes[plot_idx]
            plot_idx += 1
        else:
            ax = axes[0]

        ax.set_facecolor("white")

        # Decide offset step for this subplot
        if condition_offset == "auto":
            step = _auto_offset_for_roi(roi_name)
        elif condition_offset == "manual":
            step = manual_offset_value
        else:
            step = 0.0

        for ci, condition_name in enumerate(cond_names_sorted):
            data = condition_data[condition_name]
            dff_df = data["dff_df"]
            if roi_name not in dff_df.columns:
                continue

            time_data = dff_df["Time (s)"].values
            dff_raw = dff_df[roi_name].values
            y_off = ci * step
            dff_shifted = dff_raw + y_off

            color = condition_colors[condition_name]

            # --- Per-condition stim windows (bounded to trace y-range) ---
            if show_stim_windows and data["stim_windows"]:
                from matplotlib.patches import Rectangle
                y_lo = float(dff_shifted.min())
                y_hi = float(dff_shifted.max())
                pad = (y_hi - y_lo) * 0.05
                for s, e in data["stim_windows"]:
                    rect = Rectangle(
                        (float(s), y_lo - pad),
                        float(e) - float(s),
                        (y_hi - y_lo) + 2 * pad,
                        facecolor="#ffcccc",
                        alpha=0.45,
                        edgecolor="red",
                        linewidth=0.5,
                        zorder=0,
                    )
                    ax.add_patch(rect)

            # --- Trace ---
            ax.plot(time_data, dff_shifted, color=color,
                    linewidth=1.2, alpha=0.9, zorder=2)

            # --- Spike markers ---
            if show_spike_markers and roi_name in data["spike_times"]:
                sp_t = data["spike_times"][roi_name]
                if sp_t.size > 0:
                    sp_idx = np.clip(np.searchsorted(time_data, sp_t),
                                     0, len(dff_raw) - 1)
                    sp_y = dff_raw[sp_idx] + y_off
                    ax.scatter(sp_t, sp_y, s=40, marker="v",
                               facecolors=color, edgecolors="black",
                               linewidths=0.6, zorder=6, alpha=0.9)

            # --- End-of-trace label ---
            # Average the last few points for a stable y position
            tail = dff_shifted[-min(5, len(dff_shifted)):]
            last_t = float(time_data[-1])
            last_y = float(np.mean(tail))
            ax.annotate(
                f"  {condition_name}",
                xy=(last_t, last_y),
                fontsize=9, fontweight="bold",
                color=color,
                va="center", ha="left",
                clip_on=False,
                zorder=10,
                bbox=dict(boxstyle="round,pad=0.15",
                          facecolor="white", edgecolor="none",
                          alpha=0.75),
            )

        # ---- Axis formatting ----
        ax.axhline(0, color="#999999", linestyle="--", linewidth=0.6,
                    alpha=0.6, zorder=1)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        # Extend x-limit slightly for label room
        if time_data is not None and len(time_data):
            t_max = float(time_data[-1])
            t_min = float(time_data[0])
            extra = (t_max - t_min) * label_right_margin
            ax.set_xlim(t_min, t_max + extra)

        if use_offset:
            ax.set_ylabel(roi_name, fontsize=11, fontweight="bold")
            ax.tick_params(axis="y", length=3)
        else:
            ax.set_ylabel(f"{roi_name}\n$\\Delta$F/F", fontsize=11)

        if layout_mode == "stacked":
            if roi_idx == n_roi - 1:
                ax.set_xlabel("Time (s)", fontsize=12)
            else:
                ax.tick_params(axis="x", labelbottom=False)
        elif layout_mode == "grid":
            ax.set_title(roi_name, fontsize=11, fontweight="bold")
        else:
            ax.set_xlabel("Time (s)", fontsize=12)
            ax.set_ylabel("$\\Delta$F/F", fontsize=12)

    # ---- Hide unused grid subplots ----
    if layout_mode == "grid":
        for idx in range(plot_idx, len(axes)):
            axes[idx].set_visible(False)

    # ---- Suptitle ----
    offset_label = ""
    if condition_offset == "auto":
        offset_label = "  |  offset: auto"
    elif condition_offset == "manual":
        offset_label = f"  |  offset: {manual_offset_value}"
    fig.suptitle(
        f"$\\Delta$F/F Traces:  {n_roi} ROI(s) x {n_cond} Condition(s){offset_label}",
        fontsize=14, fontweight="bold", y=0.998,
    )

    fig.tight_layout(rect=[0, 0, right_frac, 0.99])

    # ---- Save SVG + PNG preview ----
    if output_path is None:
        output_path = str(parent_folder / "traces_visualization.svg")

    fig.savefig(output_path, format="svg", bbox_inches="tight")

    # Also save a high-res PNG for quick preview in the GUI
    png_path = output_path.replace(".svg", "_preview.png")
    fig.savefig(png_path, format="png", dpi=180, bbox_inches="tight",
                facecolor="white")
    plt.close(fig)

    print(f"\n[OK] SVG saved to: {output_path}")
    print(f"[OK] PNG preview saved to: {png_path}")
    print(f"{'='*60}\n")

    return output_path


def generate_flat_figs_for_all_rois(
    batch_cfg: BatchConfig,
    base_cfg: Config,
    roi_list: Optional[List[int]] = None,
    files_filter: Optional[List[str]] = None,
    out_dir: Optional[str] = None,
    y_step: float = 1.2,
    show_spikes: bool = True,
    linewidth: float = 1.2,
    figsize: Tuple[float, float] = (12, 7),
) -> List[Path]:
    """
    For each ROI, generate a flat figure (ROI across all experiments) and save it.

    Args:
        roi_list: if None, auto-discovers all ROI numbers present.
        files_filter: optional substrings to include certain files only.
        out_dir: folder to save images. Defaults to '<output_root>/roi_flat'.
    Returns:
        List of saved file paths.
    """
    save_root = Path(out_dir) if out_dir else Path(batch_cfg.output_root) / "roi_flat"
    save_root.mkdir(parents=True, exist_ok=True)

    if roi_list is None:
        roi_list = list_all_roi_numbers(batch_cfg, base_cfg, files_filter=files_filter)

    saved: List[Path] = []
    for roi_num in roi_list:
        try:
            out_path = save_root / f"ROI{roi_num:02d}_flat.png"
            _ = plot_single_roi_across_experiments_flat(
                roi_num=roi_num,
                batch_cfg=batch_cfg,
                base_cfg=base_cfg,
                files_filter=files_filter,
                y_step=y_step,
                linewidth=linewidth,
                show_spikes=show_spikes,
                figsize=figsize,
                title=f"ROI{roi_num:02d} traces across experiments",
                out_path=str(out_path),
                use_fixed_scale=True,
                fixed_min=0.0,  # optional (else inferred)
                fixed_max=1.0,
            )
            saved.append(out_path)
            print(f"✅ Saved {out_path}")
        except Exception as e:
            print(f"[WARN] Failed for ROI{roi_num:02d}: {e}")
            continue

    if not saved:
        print("No ROI flat figures were generated.")
    else:
        print(f"\nDone. Generated {len(saved)} ROI flat figures → {save_root}")
    return saved

def create_raster_plot_from_batch(
        batch_cfg: BatchConfig,
        output_filename: str = "spike_raster_plot.png",
        **plot_kwargs
) -> Tuple[pd.DataFrame, plt.Figure]:
    """
    Convenience function: collect spike timestamps and create raster plot.

    Args:
        batch_cfg: BatchConfig object
        output_filename: Filename for the raster plot
        **plot_kwargs: Additional arguments passed to plot_raster()

    Returns:
        (spike_timestamps_df, figure)
    """
    # Collect all spike timestamps
    spike_timestamps_df = collect_all_spike_timestamps(batch_cfg)

    # Create raster plot
    output_path = Path(batch_cfg.output_root) / output_filename
    fig = plot_raster(
        spike_timestamps_df,
        output_path=str(output_path),
        **plot_kwargs
    )

    return spike_timestamps_df, fig


def plot_raster_with_time(
        spike_timestamps_df: pd.DataFrame,
        output_path: Optional[str] = None,
        figsize: Tuple[float, float] = (14, 8),
        marker: str = "|",
        marker_size: int = 100,
        marker_color: str = "orange",
        title: str = "Raster Plot: Spike Timing per ROI & Condition",
        xlabel: str = "Time (s)",
        ylabel: str = "ROI & Condition",
        stim_windows: Optional[List[Tuple[float, float]]] = None,
        stim_color: str = "lightblue",
        stim_alpha: float = 0.3,
        separate_by_condition: bool = True,
        roi_sort_order: Optional[List[int]] = None,
        condition_order: Optional[List[str]] = None,
        color_by_condition: bool = True,
        condition_colors: Optional[Dict[str, str]] = None,
) -> plt.Figure:
    """
    Create a raster plot with TIME on X-axis showing when spikes occurred.

    Args:
        spike_timestamps_df: DataFrame with columns [Parameter, Replicate, ROI, spike_time_s]
        output_path: Path to save figure
        figsize: Figure size (width, height)
        marker: Marker style for spikes
        marker_size: Size of spike markers
        marker_color: Default color (used if color_by_condition=False)
        title: Plot title
        xlabel: X-axis label
        ylabel: Y-axis label
        stim_windows: List of (start, end) tuples for stimulation periods
        stim_color: Color for stimulation windows
        stim_alpha: Transparency for stimulation windows
        separate_by_condition: If True, each condition gets separate rows
        roi_sort_order: Custom ROI ordering
        condition_order: Custom condition ordering
        color_by_condition: If True, color spikes by condition
        condition_colors: Dict mapping condition names to colors

    Returns:
        matplotlib Figure object
    """
    if spike_timestamps_df.empty:
        print("Warning: No spike data to plot!")
        return None

    df = spike_timestamps_df.copy()

    # Create condition labels
    df["Condition"] = df["Parameter"].astype(str) + df["Replicate"].astype(str)

    # Determine orders
    if condition_order is None:
        conditions = df.groupby(["Parameter", "Replicate"])["Condition"].first().unique().tolist()
    else:
        conditions = condition_order

    if roi_sort_order is None:
        roi_list = sorted(df["ROI"].unique())
    else:
        roi_list = roi_sort_order

    # Create figure
    fig, ax = plt.subplots(figsize=figsize)

    # Plot stimulation windows first (background)
    if stim_windows:
        y_max = len(conditions) * len(roi_list) if separate_by_condition else len(roi_list)
        for start, end in stim_windows:
            ax.axvspan(start, end, color=stim_color, alpha=stim_alpha, zorder=0)

    # Create color map for conditions
    if color_by_condition:
        if condition_colors is None:
            unique_params = df["Parameter"].unique()
            cmap = plt.get_cmap("tab10")
            condition_colors = {
                param: cmap(i % 10) for i, param in enumerate(unique_params)
            }
        color_map = {cond: condition_colors.get(df[df["Condition"] == cond]["Parameter"].iloc[0], marker_color)
                     for cond in conditions}
    else:
        color_map = {cond: marker_color for cond in conditions}

    # Build Y-axis labels and positions
    if separate_by_condition:
        # Each condition-ROI pair gets its own row
        y_labels = []
        y_positions = {}
        y_pos = 0

        for cond in conditions:
            for roi in roi_list:
                y_labels.append(f"{cond}-ROI{roi:02d}")
                y_positions[(cond, roi)] = y_pos
                y_pos += 1
    else:
        # ROIs only, spikes from all conditions overlap
        y_labels = [f"ROI{roi:02d}" for roi in roi_list]
        y_positions = {roi: i for i, roi in enumerate(roi_list)}

    # Plot spikes
    for _, row in df.iterrows():
        spike_time = row["spike_time_s"]
        roi = row["ROI"]
        cond = row["Condition"]

        if separate_by_condition:
            if (cond, roi) in y_positions:
                y_pos = y_positions[(cond, roi)]
                color = color_map[cond]
                ax.scatter(spike_time, y_pos, marker=marker, s=marker_size,
                           color=color, alpha=0.8, linewidths=1.5, zorder=2)
        else:
            if roi in y_positions:
                y_pos = y_positions[roi]
                color = color_map[cond]
                ax.scatter(spike_time, y_pos, marker=marker, s=marker_size,
                           color=color, alpha=0.8, linewidths=1.5, zorder=2)

    # Set up axes
    ax.set_yticks(range(len(y_labels)))
    ax.set_yticklabels(y_labels, fontsize=8)

    ax.set_xlabel(xlabel, fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(title, fontsize=14, fontweight="bold")

    # Grid
    ax.grid(True, axis="x", alpha=0.3, linestyle="--", linewidth=0.5)

    # Add legend for conditions if colored by condition
    if color_by_condition and condition_colors:
        from matplotlib.patches import Patch
        legend_elements = [Patch(facecolor=condition_colors[param], label=param)
                           for param in sorted(condition_colors.keys())]
        ax.legend(handles=legend_elements, loc="upper right", fontsize=9)

    # Set limits
    ax.set_ylim(-0.5, len(y_labels) - 0.5)
    if not df.empty:
        time_min = df["spike_time_s"].min() - 5
        time_max = df["spike_time_s"].max() + 5
        ax.set_xlim(time_min, time_max)

    fig.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=300, bbox_inches="tight")
        print(f"Time-based raster plot saved to: {output_path}")

    return fig


def create_both_raster_plots(
        batch_cfg: BatchConfig,
        stim_windows: Optional[List[Tuple[float, float]]] = None,
) -> Tuple[pd.DataFrame, plt.Figure, plt.Figure]:
    """
    Create both types of raster plots:
    1. Grouped by condition (original)
    2. Time-based showing when spikes occurred

    Returns:
        (spike_timestamps_df, grouped_raster_fig, time_raster_fig)
    """
    # Collect timestamps
    spike_timestamps_df = collect_all_spike_timestamps(batch_cfg)

    if spike_timestamps_df.empty:
        return spike_timestamps_df, None, None

    output_root = Path(batch_cfg.output_root)

    # Raster plot 1: Grouped by condition
    fig1 = plot_raster(
        spike_timestamps_df,
        output_path=str(output_root / "spike_raster_grouped.png"),
        figsize=(14, 8),
        marker="|",
        marker_size=120,
        marker_color="orange",
        title="Raster Plot: Individual Spike Events per ROI & Condition",
    )

    # Raster plot 2: Time-based
    fig2 = plot_raster_with_time(
        spike_timestamps_df,
        output_path=str(output_root / "spike_raster_timeline.png"),
        figsize=(16, 10),
        marker="|",
        marker_size=80,
        stim_windows=stim_windows,
        separate_by_condition=True,
        color_by_condition=True,
    )

    return spike_timestamps_df, fig1, fig2


if __name__ == "__main__":

    single_file_mode = False

    if single_file_mode:
        cfg = Config(
            csv_path="./0806_F_N/Ctrl1.csv",
            encoding="utf-16",
            skip_first_row=True,
            time_col="Axis [s]",
            roi_key="ROI",
            bg_source="roi_column",
            bg_column_name="ROI.000 []",
            exclude_bg_roi_from_plot=True,
            exclude_bg_roi_from_detection=True,
            baseline_window_half_s=30.0,
            baseline_percentile=8.0,
            stim_preset="20s",
            baseline_index_start=5,
            baseline_index_end=25,
            spike_z_sigma=3.0,
            min_spike_distance_s=10,
            width_mode="rough",
            width_threshold_s=2.0,
            use_auto_ylim=True,
            show_spike_markers=True,
            show_spiking_only_figure=True,
            out_fig="deltaF_F_plot_bgselect.png",
            out_spike_csv="spike_summary.csv",
            out_spike_stats_csv="spike_baseline_stats.csv",
        )
        dff, fig_all, fig_spk = run(cfg)
        plt.show()

    else:
        shared_config = Config(
            csv_path="",
            encoding="utf-16",
            skip_first_row=True,
            time_col="Axis [s]",
            roi_key="ROI",
            bg_source="roi_column",
            bg_column_name="ROI.000 []",
            exclude_bg_roi_from_plot=True,
            exclude_bg_roi_from_detection=True,
            baseline_window_half_s=30.0,
            baseline_percentile=8.0,
            stim_preset="20s",
            baseline_index_start=10,
            baseline_index_end=30,
            spike_z_sigma=3.0,
            min_spike_distance_s=15,
            width_mode="rough",
            width_threshold_s=4.0,
            use_auto_ylim=False,
            show_spike_markers=True,
            show_spiking_only_figure=True,
            out_fig=None,
            out_spike_csv=None,
            out_spike_stats_csv=None,

        )

        batch_cfg = BatchConfig(
            input_folder="./1125",
            file_pattern="*.csv",
            output_root="./batch_results",
            shared_config=shared_config,
            per_file_overrides={},
            summary_table_path="spike_summary_table.csv",
            summary_table_excel="spike_summary_table.xlsx",
            include_zero_spike_rois=False,
            verbose=True,
            continue_on_error=True,
        )

        print("Starting batch processing...")
        batch_summary, spike_table = batch_process_and_summarize(batch_cfg)

        print("\n" + "=" * 60)
        print("Creating raster plots...")
        print("=" * 60)

        # Create BOTH raster plots
        spike_timestamps_df, fig_grouped, fig_timeline = create_both_raster_plots(
            batch_cfg,
            stim_windows=shared_config.stim_windows,  # Use stim windows from config
        )

        print("\n" + "=" * 60)
        print("ALL DONE!")
        print("=" * 60)
        print(f"\nCheck results in: {batch_cfg.output_root}/")
        print(f"Summary table: {batch_cfg.output_root}/{batch_cfg.summary_table_path}")
        print(f"Raster plot (grouped): {batch_cfg.output_root}/spike_raster_grouped.png")
        print(f"Raster plot (timeline): {batch_cfg.output_root}/spike_raster_timeline.png")
        print(f"All spike timestamps: {batch_cfg.output_root}/all_spike_timestamps.csv")



        # fig = plot_single_roi_across_experiments_flat(
        #     roi_num=3,
        #     batch_cfg=batch_cfg,
        #     base_cfg=shared_config,
        #     files_filter=["Ctrl1", "Ctrl2","20-2"],
        #     y_step=1.2,
        #     show_spikes=True,
        #     out_path="batch_results/ROI03_flat.png",
        # )
        #
        # fig2 = plot_single_roi_across_experiments_flat(
        #     roi_num=5,
        #     batch_cfg=batch_cfg,
        #     base_cfg=shared_config,
        #     files_filter=["Ctrl1", "Ctrl2", "20-1","20-2"],
        #     y_step=1.2,
        #     show_spikes=True,
        #     out_path="batch_results/ROI05_flat.png",
        # )
        #
        # fig3 = plot_single_roi_across_experiments_flat(
        #     roi_num=8,
        #     batch_cfg=batch_cfg,
        #     base_cfg=shared_config,
        #     files_filter=["Ctrl1", "Ctrl2", "20-3","2hz1","2hz3","5hz1","5hz3"],
        #     y_step=1.2,
        #     show_spikes=True,
        #     out_path="batch_results/ROI08_flat.png",
        # )
        #
        # fig4 = plot_single_roi_across_experiments_flat(
        #     roi_num=9,
        #     batch_cfg=batch_cfg,
        #     base_cfg=shared_config,
        #     files_filter=["Ctrl1", "Ctrl2", "20-3","2hz1","2hz3","5hz2","20-2"],
        #     y_step=1.2,
        #     show_spikes=True,
        #     out_path="batch_results/ROI09_flat.png",
        # )
        #
        # fig5 = plot_single_roi_across_experiments_flat(
        #     roi_num=10,
        #     batch_cfg=batch_cfg,
        #     base_cfg=shared_config,
        #     files_filter=["Ctrl1", "Ctrl2", "20-1", "5hz1", "5hz2", "5hz3", "20-2"],
        #     y_step=1.2,
        #     show_spikes=True,
        #     out_path="batch_results/ROI10_flat.png",
        # )
        #
        # fig6 = plot_single_roi_across_experiments_flat(
        #     roi_num=12,
        #     batch_cfg=batch_cfg,
        #     base_cfg=shared_config,
        #     files_filter=["Ctrl1", "Ctrl2", "20-2", "2hz1", "2hz2", "5hz1", "20-1"],
        #     y_step=1.2,
        #     show_spikes=True,
        #     out_path="batch_results/ROI12_flat.png",
        # )
        #
        # fig7 = plot_single_roi_across_experiments_flat(
        #     roi_num=13,
        #     batch_cfg=batch_cfg,
        #     base_cfg=shared_config,
        #     files_filter=["Ctrl1", "Ctrl2", "20-2", "2hz1", "2hz2", "20-1"],
        #     y_step=1.2,
        #     show_spikes=True,
        #     out_path="batch_results/ROI13_flat.png",
        # )


        _ = generate_flat_figs_for_all_rois(
            batch_cfg=batch_cfg,
            base_cfg=shared_config,
            roi_list=None,  # auto-discover all ROI numbers
            files_filter=None,  # or e.g. ["Ctrl", "10-1"] to subset
            out_dir="batch_results/roi_flat",
            y_step=1.2,
            show_spikes=True,
            linewidth=1.2,
            figsize=(12, 7),
        )


# ==========================================
# Interactive HTML report
# ==========================================
def generate_interactive_html(
    analysis_output_folder: str,
    selected_conditions: Optional[List[str]] = None,
    selected_rois: Optional[List[str]] = None,
    output_path: Optional[str] = None,
    show_stim_windows: bool = True,
    show_spike_markers: bool = True,
    stim_preset_mode: str = "auto",
    condition_offset: str = "auto",
    manual_offset_value: float = 0.5,
) -> str:
    """
    Generate a standalone interactive HTML file with Plotly traces.

    Parameters
    ----------
    condition_offset : str
        "none" - traces overlap on same y-axis.
        "auto" - auto-compute offset so traces don't overlap.
        "manual" - use manual_offset_value between conditions.
    manual_offset_value : float
        Vertical shift between conditions when condition_offset="manual".

    Returns the path to the saved HTML file.
    """
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    condition_data, all_roi_names = _load_condition_data(
        analysis_output_folder,
        selected_conditions=selected_conditions,
        stim_preset_mode=stim_preset_mode,
    )

    if selected_rois:
        roi_names = [r for r in sorted(all_roi_names) if r in selected_rois]
    else:
        roi_names = sorted(all_roi_names)

    if not roi_names:
        raise ValueError("No matching ROIs found")

    cond_names = sorted(condition_data.keys())
    n_rois = len(roi_names)

    # Assign consistent colors per condition
    palette = [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
        "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
        "#aec7e8", "#ffbb78", "#98df8a", "#ff9896", "#c5b0d5",
    ]
    condition_colors = {c: palette[i % len(palette)] for i, c in enumerate(cond_names)}

    fig = make_subplots(
        rows=n_rois, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        subplot_titles=[f"{roi}" for roi in roi_names],
    )

    # Track which conditions have been added to legend
    legend_shown = set()

    for ri, roi_name in enumerate(roi_names):
        row = ri + 1

        # Compute offset step for this ROI
        if condition_offset == "auto":
            ptp_vals = []
            for cn in cond_names:
                d = condition_data[cn]["dff_df"]
                if roi_name in d.columns:
                    ptp_vals.append(np.ptp(d[roi_name].values))
            step = 1.2 * float(np.median(ptp_vals)) if ptp_vals else 0.0
        elif condition_offset == "manual":
            step = manual_offset_value
        else:
            step = 0.0

        for ci, cond_name in enumerate(cond_names):
            data = condition_data[cond_name]
            dff_df = data["dff_df"]
            if roi_name not in dff_df.columns:
                continue

            time_arr = dff_df["Time (s)"].values
            dff_raw = dff_df[roi_name].values
            y_off = ci * step
            dff_arr = dff_raw + y_off
            color = condition_colors[cond_name]
            show_legend = cond_name not in legend_shown

            # Trace
            fig.add_trace(
                go.Scatter(
                    x=time_arr, y=dff_arr,
                    mode="lines",
                    name=cond_name,
                    legendgroup=cond_name,
                    showlegend=show_legend,
                    line=dict(color=color, width=1.2),
                    hovertemplate=(
                        f"<b>{cond_name}</b> - {roi_name}<br>"
                        "Time: %{x:.2f} s<br>"
                        "ΔF/F: %{y:.4f}<extra></extra>"
                    ),
                ),
                row=row, col=1,
            )
            legend_shown.add(cond_name)

            # Spike markers
            if show_spike_markers and roi_name in data["spike_times"]:
                sp_t = data["spike_times"][roi_name]
                if sp_t.size > 0:
                    sp_idx = np.clip(np.searchsorted(time_arr, sp_t),
                                     0, len(dff_raw) - 1)
                    sp_y = dff_raw[sp_idx] + y_off
                    fig.add_trace(
                        go.Scatter(
                            x=sp_t, y=sp_y,
                            mode="markers",
                            marker=dict(symbol="triangle-down", size=8,
                                        color=color, line=dict(color="black", width=0.5)),
                            name=f"{cond_name} spikes",
                            legendgroup=cond_name,
                            showlegend=False,
                            hovertemplate=(
                                f"<b>Spike</b> ({cond_name})<br>"
                                "Time: %{x:.3f} s<br>"
                                "ΔF/F: %{y:.4f}<extra></extra>"
                            ),
                        ),
                        row=row, col=1,
                    )

        # Stim windows as shaded rectangles
        if show_stim_windows:
            drawn_windows = set()
            for cond_name in cond_names:
                for s, e in condition_data[cond_name]["stim_windows"]:
                    key = (float(s), float(e))
                    if key not in drawn_windows:
                        drawn_windows.add(key)
                        fig.add_vrect(
                            x0=s, x1=e,
                            fillcolor="red", opacity=0.08,
                            line_width=0.5, line_color="red",
                            row=row, col=1,
                        )

        fig.update_yaxes(title_text="ΔF/F", row=row, col=1)

    fig.update_xaxes(title_text="Time (s)", row=n_rois, col=1)

    # Layout
    height = max(2000, n_rois * 1250)
    folder_name = Path(analysis_output_folder).name
    fig.update_layout(
        title=dict(
            text=f"ΔF/F Trace Visualization — {folder_name}",
            font=dict(size=18),
        ),
        height=height,
        template="plotly_white",
        font=dict(family="Arial", size=12),
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.01,
            xanchor="center",
            x=0.5,
        ),
    )

    # Save
    if output_path is None:
        output_path = str(Path(analysis_output_folder) / "trace_report.html")

    fig.write_html(
        output_path,
        include_plotlyjs=True,
        full_html=True,
        config={
            "displayModeBar": True,
            "modeBarButtonsToAdd": ["drawrect", "eraseshape"],
            "toImageButtonOptions": {
                "format": "svg",
                "filename": "trace_visualization",
            },
        },
    )
    print(f"HTML report saved to: {output_path}")
    return output_path
