# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Tuple, List, Optional, Dict

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt



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
    bg_source: str = "roi_column"         # "roi_column" or "csv_file"
    bg_column_name: str = "ROI.01 []"     # used if bg_source == "roi_column"
    bg_csv_path: str = "./0718/bg.csv"    # used if bg_source == "csv_file"
    bg_csv_col_name: Optional[str] = None # if None, auto-pick ROI-like or first numeric

    # Plot behavior
    exclude_bg_roi_from_plot: bool = True
    ylim_max: float = 0.80
    fig_size: Tuple[float, float] = (10, 6)
    cmap_name: str = "tab10"
    stim_color: str = "red"
    stim_alpha: float = 0.30
    use_auto_ylim: bool = True  # autoset y-lims per figure
    auto_ylim_include_zero: bool = True  # keep y=0 in view
    auto_ylim_pad_frac: float = 0.05  # 5% headroom
    ylim_min: Optional[float] = 0.0  # used only if use_auto_ylim=False

    # ΔF/F baseline (rolling percentile)
    baseline_window_half_s: float = 15.0
    baseline_percentile: float = 8.0

    # ---- Stimulation windows (with presets) ----
    stim_preset: str = "20s"                        # "20s", "10s", "5s", "none", "custom"
    stim_windows_custom: Optional[List[Tuple[float, float]]] = None
    # resolved windows (filled in __post_init__)
    stim_windows: List[Tuple[float, float]] = None

    # Outputs
    out_fig: Optional[str] = "deltaF_F_plot_bgselect.png"
    out_csv: Optional[str] = None  # e.g., "dff_table.csv"

    # Spike detection
    baseline_frames_for_spike: int = 29
    spike_z_sigma: float = 5.0
    min_spike_distance_s: Optional[float] = None  # e.g., 2.0 to avoid double-counting within 2 s
    exclude_bg_roi_from_detection: bool = True  # usually True if bg ROI is ROI.01
    out_spike_csv: Optional[str] = "spike_summary.csv"
    out_spike_stats_csv: Optional[str] = "spike_baseline_stats.csv"

    # Plot: spike overlay
    show_spike_markers: bool = True
    spike_marker: str = "o"  # e.g., "o", "^", "v", "x", "*"
    spike_marker_size: int = 36
    spike_marker_face: str = "none"  # "none" or "fill"
    spike_marker_edgecolor: str = "k"  # edge outline (black)
    annotate_spike_counts: bool = True  # text box listing ROI spike counts
    annotate_spike_counts_max: int = 6  # show top-N ROIs by count
    annotate_spike_counts_loc: str = "upper right"  # "upper right"/"upper left"/"lower right"/"lower left"

    label_spike_numbers: bool = False  # set True to show 1,2,3... at peaks
    label_fontsize: int = 8
    label_offset_y: float = 0.02  # vertical offset in data units

    # Second figure with only spiking ROIs
    show_spiking_only_figure: bool = True
    out_fig_spiking_only: Optional[str] = "deltaF_F_spiking_only.png"


    # Spike width filter
    width_mode: str = "rough"  # "rough" or "fwhm"
    width_threshold_s: float = 0.50  # minimum width (seconds) to count a spike

    def __post_init__(self):
        presets: Dict[str, List[Tuple[float, float]]] = {
            "20s": [(30, 50), (80, 100), (130, 150)],
            "10s": [(30, 40), (70, 80), (110, 120)],
            "5s":  [(30, 35), (65, 70), (100, 105)],
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


# =========================
# I/O helpers
# =========================
def load_fluo_csv(path: str, encoding: str, skip_first_row: bool) -> pd.DataFrame:
    p = Path(path)
    if skip_first_row:
        return pd.read_csv(p, encoding=encoding, skiprows=1)
    try:
        return pd.read_csv(p)  # try UTF-8
    except UnicodeDecodeError:
        return pd.read_csv(p, encoding=encoding)


def find_roi_columns(df: pd.DataFrame, roi_key: str) -> List[str]:
    return [c for c in df.columns if roi_key in c]


# =========================
# Background selection
# =========================
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

    # bg_source == "csv_file"
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


# =========================
# ΔF/F computation
# =========================
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
    dff = np.abs((F - F0) / (F0))
    return dff, F0


def compute_all_dff(
    df_main: pd.DataFrame,
    roi_cols: Iterable[str],
    bg_vec: np.ndarray,
    t: np.ndarray,
    cfg: Config
) -> pd.DataFrame:
    dff_dict: Dict[str, np.ndarray] = {}
    for col in roi_cols:
        F_corr = background_subtraction(df_main[col].to_numpy(dtype=float), bg_vec)
        dff_vals, _ = dff_percentile_window(
            F_corr, t,
            window_half_s=cfg.baseline_window_half_s,
            percentile=cfg.baseline_percentile,
        )
        dff_dict[col] = dff_vals
    out = pd.DataFrame(dff_dict)
    out.insert(0, "Time (s)", t)
    return out


# =========================
# Plotting
# =========================
def plot_dff(
    dff_table: pd.DataFrame,
    roi_cols: List[str],
    cfg: Config,
    bg_was_roi: bool,
    spike_times: Optional[Dict[str, np.ndarray]] = None,
) -> plt.Figure:

    roi_cols_for_plot = list(roi_cols)
    if bg_was_roi and cfg.exclude_bg_roi_from_plot:
        roi_cols_for_plot = [c for c in roi_cols_for_plot if c != cfg.bg_column_name]

    fig, ax = plt.subplots(figsize=cfg.fig_size)

    colors = plt.get_cmap(cfg.cmap_name).colors
    color_map = {roi_cols_for_plot[i]: colors[i % len(colors)] for i in range(len(roi_cols_for_plot))}

    # Lines
    for col in roi_cols_for_plot:
        ax.plot(dff_table["Time (s)"], dff_table[col], label=col, linewidth=1.2, color=color_map[col])

    # Stim windows
    for s, e in cfg.stim_windows:
        ax.axvspan(s, e, color=cfg.stim_color, alpha=cfg.stim_alpha)

    # Spike overlay (markers + optional summary box)
    if spike_times is not None:
        overlay_spikes_on_axes(ax, dff_table, roi_cols_for_plot, spike_times, color_map, cfg)

    # Style
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


#===================
# Spike Detection
#=====================

def _segments_above_threshold(y: np.ndarray, thr: float) -> list[np.ndarray]:
    """Return list of contiguous index runs where y > thr."""
    above = y > thr
    idx = np.flatnonzero(above)
    if idx.size == 0:
        return []
    splits = np.where(np.diff(idx) > 1)[0] + 1
    return np.split(idx, splits)

def _interp_time_at_y(t1, y1, t2, y2, y_target) -> float:
    """Linear interpolate time where (t,y) crosses y_target between sample 1 and 2."""
    if y2 == y1:
        return float(t1)
    alpha = (y_target - y1) / (y2 - y1)
    return float(t1 + alpha * (t2 - t1))

def _measure_run_widths(
    y: np.ndarray, t: np.ndarray, run: np.ndarray, k_peak: int, baseline_mean: float
) -> tuple[float, float]:
    """
    Measure (rough_width_s, fwhm_width_s) for one contiguous >thr run.
    - rough width: t[end] - t[start]
    - FWHM: width at half level = (peak + baseline_mean)/2, using linear interpolation to find crossings.
    """
    # Rough width
    rough_w = float(t[run[-1]] - t[run[0]])

    # FWHM relative to baseline mean
    peak_val = float(y[k_peak])
    half_lvl = 0.5 * (peak_val + float(baseline_mean))

    # Left crossing from peak downwards
    t_left = float(t[run[0]])
    for j in range(k_peak, run[0], -1):
        if (y[j - 1] < half_lvl) and (y[j] >= half_lvl):
            t_left = _interp_time_at_y(t[j - 1], y[j - 1], t[j], y[j], half_lvl)
            break

    # Right crossing from peak upwards
    t_right = float(t[run[-1]])
    for j in range(k_peak + 1, run[-1] + 1):
        if (y[j] < half_lvl) and (y[j - 1] >= half_lvl):
            t_right = _interp_time_at_y(t[j - 1], y[j - 1], t[j], y[j], half_lvl)
            break

    fwhm_w = max(0.0, float(t_right - t_left))
    return rough_w, fwhm_w


def _baseline_stats_first_n(y: np.ndarray, spike_z_sigma, n: int) -> Tuple[float, float, float]:
    """
    Return (mean0, sd0, thr) using the first n samples of y.
    thr = mean0 + 3 * sd0  (3σ)
    """
    n_eff = min(n, y.size)
    base = y[:n_eff]
    mean0 = float(np.mean(base))
    sd0 = float(np.std(base, ddof=1)) if n_eff > 1 else 0.0
    # guard against sd=0 to avoid permanent "above threshold"
    thr = mean0 + spike_z_sigma * (sd0 if sd0 > 0 else 1e-12)
    return mean0, sd0, thr


def _rising_crossings(y: np.ndarray, thr: float) -> np.ndarray:
    """
    Indices where the trace rises above threshold: y[k-1] <= thr and y[k] > thr.
    Returns 1D array of indices (k).
    """
    if y.size < 2:
        return np.array([], dtype=int)
    return np.where((y[1:] > thr) & (y[:-1] <= thr))[0] + 1


def _enforce_min_distance(idxs: np.ndarray, t: np.ndarray, min_distance_s: Optional[float]) -> np.ndarray:
    """
    Keep rising crossings at least min_distance_s apart in time.
    Greedy thinning. If min_distance_s is None, return idxs unchanged.
    """
    if min_distance_s is None or idxs.size == 0:
        return idxs
    keep = [idxs[0]]
    last_t = t[idxs[0]]
    for k in idxs[1:]:
        if (t[k] - last_t) >= min_distance_s:
            keep.append(k)
            last_t = t[k]
    return np.array(keep, dtype=int)


def detect_spikes_across_rois(
    dff_table: pd.DataFrame,
    roi_cols: List[str],
    time_col: str = "Time (s)",
    baseline_frames: int = 59,
    spike_z_sigma: float = 3.0,
    min_distance_s: Optional[float] = None,
    width_mode: str = "rough",  # "rough" or "fwhm"
    width_threshold_s: float = 0.50,  # seconds
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, np.ndarray]]:
    t = dff_table[time_col].to_numpy(dtype=float)

    stats_rows = []
    summary_rows = []
    spike_times: Dict[str, np.ndarray] = {}

    for col in roi_cols:
        y = dff_table[col].to_numpy(dtype=float)

        # baseline on first N frames
        mean0, sd0, thr = _baseline_stats_first_n(y, spike_z_sigma,baseline_frames)

        # Segments where y > thr
        runs = _segments_above_threshold(y, thr)

        accepted_peak_idxs: list[int] = []
        peak_times_tmp: list[float] = []

        for run in runs:
            # peak index inside this run
            k_peak = run[np.argmax(y[run])]

            # measure widths
            rough_w, fwhm_w = _measure_run_widths(y, t, run, k_peak, baseline_mean=mean0)
            measured = rough_w if width_mode.lower() == "rough" else fwhm_w

            # width criterion
            if np.isfinite(measured) and (measured >= width_threshold_s):
                accepted_peak_idxs.append(int(k_peak))
                peak_times_tmp.append(float(t[k_peak]))

        # min-distance thinning (optional)
        if accepted_peak_idxs:
            accepted_peak_idxs = np.array(sorted(accepted_peak_idxs), dtype=int)
            accepted_peak_idxs = _enforce_min_distance(accepted_peak_idxs, t, min_distance_s)
            peak_times = t[accepted_peak_idxs]
        else:
            peak_times = np.array([], dtype=float)

        # record
        stats_rows.append({"ROI": col, "mean0": mean0, "sd0": sd0, "thr": thr})
        spike_times[col] = peak_times
        if peak_times.size > 0:
            summary_rows.append({"ROI": col, "n_spikes": int(peak_times.size)})

    stats_df = pd.DataFrame(stats_rows)
    summary_df = pd.DataFrame(summary_rows).sort_values("n_spikes", ascending=False).reset_index(drop=True)
    return summary_df, stats_df, spike_times


def overlay_spikes_on_axes(
    ax: plt.Axes,
    dff_table: pd.DataFrame,
    roi_cols_for_plot: List[str],
    spike_times: Dict[str, np.ndarray],
    color_map: Dict[str, tuple],
    cfg: Config,
) -> None:
    """
    Draw spike markers on each ROI trace and (optionally) annotate a small summary box.
    """
    if not cfg.show_spike_markers and not cfg.annotate_spike_counts:
        return

    t_vals = dff_table["Time (s)"].to_numpy()
    annotated_rows = []

    for col in roi_cols_for_plot:
        times = spike_times.get(col, np.array([], dtype=float))
        if times.size == 0:
            continue

        # match times back to indices (same array origin, so exact match is OK)
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

    # Add a compact text box with counts
    if cfg.annotate_spike_counts and annotated_rows:
        annotated_rows.sort(key=lambda kv: kv[1], reverse=True)
        annotated_rows = annotated_rows[: cfg.annotate_spike_counts_max]
        summary_text = "\n".join(f"{roi}: {cnt}" for roi, cnt in annotated_rows)

        # position
        loc_map = {
            "upper right":  (1.0, 1.0, "right", "top"),
            "upper left":   (0.0, 1.0, "left", "top"),
            "lower right":  (1.0, 0.0, "right", "bottom"),
            "lower left":   (0.0, 0.0, "left", "bottom"),
        }
        xA, yA, ha, va = loc_map.get(cfg.annotate_spike_counts_loc, (1.0, 1.0, "right", "top"))

        ax.text(
            xA, yA, f"Spikes (top {cfg.annotate_spike_counts_max}):\n" + summary_text,
            transform=ax.transAxes,
            ha=ha, va=va,
            fontsize=9,
            bbox=dict(boxstyle="round,pad=0.35", facecolor="white", alpha=0.8, linewidth=0.8),
        )

def _peak_indices_above_threshold(y: np.ndarray, thr: float) -> np.ndarray:
    """
    For each contiguous segment where y > thr, return the index of the local maximum (peak).
    """
    above = y > thr
    if not np.any(above):
        return np.array([], dtype=int)

    idx = np.flatnonzero(above)
    # split contiguous runs where consecutive indices differ by >1
    splits = np.where(np.diff(idx) > 1)[0] + 1
    runs = np.split(idx, splits)

    peak_idxs = []
    for run in runs:
        if run.size == 0:
            continue
        k_peak_in_run = np.argmax(y[run])
        peak_idxs.append(run[k_peak_in_run])
    return np.array(peak_idxs, dtype=int)

def compute_auto_ylim(
    dff_table: pd.DataFrame,
    columns: List[str],
    include_zero: bool = True,
    pad_frac: float = 0.05,
) -> tuple[float, float]:
    """
    Compute y-limits from the data in `columns`, with optional inclusion of y=0
    and a fractional padding. Robust to NaNs/empties/flat traces.
    """
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

    return (y_min - pad, y_max + pad)


# =========================
# run
# =========================
def run(cfg: Config):
    df = load_fluo_csv(cfg.csv_path, encoding=cfg.encoding, skip_first_row=cfg.skip_first_row)

    print("Total frames:", df.shape[0])
    if cfg.time_col not in df.columns:
        raise ValueError(f"Time column '{cfg.time_col}' not found. Columns: {list(df.columns)}")
    time = df[cfg.time_col].to_numpy()

    roi_cols = find_roi_columns(df, cfg.roi_key)
    if not roi_cols:
        raise ValueError(f"No ROI columns found using key '{cfg.roi_key}'.")

    bg_vec = select_background(df, cfg)
    bg_is_roi = (cfg.bg_source == "roi_column")

    dff_table = compute_all_dff(df, roi_cols, bg_vec, time, cfg)

    # Decide which ROIs to run detection on (usually exclude the background ROI if used as bg)
    roi_cols_for_detection = list(roi_cols)
    if (cfg.bg_source == "roi_column") and cfg.exclude_bg_roi_from_detection:
        roi_cols_for_detection = [c for c in roi_cols_for_detection if c != cfg.bg_column_name]

    # Spike detection
    spike_summary_df, spike_stats_df, spike_times = detect_spikes_across_rois(
        dff_table=dff_table,
        roi_cols=roi_cols_for_detection,
        time_col="Time (s)",
        baseline_frames=cfg.baseline_frames_for_spike,
        spike_z_sigma =cfg.spike_z_sigma,
        min_distance_s=cfg.min_spike_distance_s,
        width_mode=cfg.width_mode,
        width_threshold_s=cfg.width_threshold_s,
    )

    print(spike_summary_df)
    # Save spike summaries if requested
    if cfg.out_spike_csv:
        # also include spike times as a semicolon-separated string
        tmp = spike_summary_df.copy()
        tmp["spike_times_s"] = tmp["ROI"].map(lambda r: ";".join(f"{x:.3f}" for x in spike_times.get(r, [])))
        tmp.to_csv(cfg.out_spike_csv, index=False)

    if cfg.out_spike_stats_csv:
        spike_stats_df.to_csv(cfg.out_spike_stats_csv, index=False)


    fig = plot_dff(dff_table, roi_cols, cfg, bg_was_roi=bg_is_roi, spike_times=spike_times)

    # Plot original figure (all ROIs, honoring bg exclusion in plot_dff)
    fig_all = plot_dff(
        dff_table=dff_table,
        roi_cols=roi_cols,
        cfg=cfg,
        bg_was_roi=bg_is_roi,
        spike_times=spike_times,  # markers show up where applicable
    )
    fig_all.show()
    # Give a clearer title
    if fig_all.axes:
        fig_all.axes[0].set_title("ΔF/F (all ROIs)")

    if cfg.out_fig:
        fig_all.savefig(cfg.out_fig, dpi=300, bbox_inches="tight")

    # Plot spiking-only figure
    roi_cols_spiking = spike_summary_df["ROI"].tolist()
    if cfg.show_spiking_only_figure and len(roi_cols_spiking) > 0:
        fig_spk = plot_dff(
            dff_table=dff_table,
            roi_cols=roi_cols_spiking,
            cfg=cfg,
            bg_was_roi=bg_is_roi,
            spike_times=spike_times,  # only those ROIs will get markers
        )
        if fig_spk.axes:
            fig_spk.axes[0].set_title("ΔF/F (ROIs with spikes)")

        if cfg.out_fig_spiking_only:
            fig_spk.savefig(cfg.out_fig_spiking_only, dpi=300, bbox_inches="tight")
    else:
        print("No ROIs with spikes; skipping 'spiking only' figure.")

    if cfg.out_fig:
        fig.savefig(cfg.out_fig, dpi=300, bbox_inches="tight")
    if cfg.out_csv:
        dff_table.to_csv(cfg.out_csv, index=False)

    return dff_table, fig_all, (fig_spk if (cfg.show_spiking_only_figure and len(roi_cols_spiking) > 0) else None)


# =========================
# Main
# =========================
if __name__ == "__main__":
    cfg = Config(
        csv_path="./0718/20-7.csv",
        encoding="utf-16",
        skip_first_row=True,
        time_col="Axis [s]",
        roi_key="ROI",

        # Background selection:
        bg_source="roi_column",            # "roi_column" or "csv_file"
        bg_column_name="ROI.01 []",        # used if bg_source == "roi_column"
        bg_csv_path="./0718/bg.csv",       # used if bg_source == "csv_file"
        bg_csv_col_name=None,              # set to a column name if needed

        # Plot behavior:
        exclude_bg_roi_from_plot=True,
        ylim_max=0.80,
        fig_size=(10, 6),
        cmap_name="tab10",
        stim_color="red",
        stim_alpha=0.30,

        # ΔF/F baseline:
        baseline_window_half_s=30.0,
        baseline_percentile=8.0,

        # ---- Choose stim preset here ----
        # Options: "20s", "10s", "5s", "none", "custom"
        stim_preset="20s",
        # If using "custom", provide your own windows:
        # stim_windows_custom=[(15, 20), (45, 55)],

        # Outputs
        out_fig="deltaF_F_plot_bgselect.png",
        out_csv=None,  # e.g., "dff_table.csv"

        # Spike detection
        baseline_frames_for_spike= 59,
        spike_z_sigma = 3.0,
        min_spike_distance_s= 20,  # e.g., 2.0 to avoid double-counting within 2 s
        exclude_bg_roi_from_detection = True,  # usually True if bg ROI is ROI.01
        out_spike_csv= "spike_summary.csv",
        out_spike_stats_csv = "spike_baseline_stats.csv",

        # Plot: spike overlay
        show_spike_markers = True,
        spike_marker = "o",  # e.g., "o", "^", "v", "x", "*"
        spike_marker_size = 36,
        spike_marker_face = "none",  # "none" or "fill"
        spike_marker_edgecolor = "k",  # edge outline (black)
        annotate_spike_counts = True,  # text box listing ROI spike counts
        annotate_spike_counts_max = 6,  # show top-N ROIs by count
        annotate_spike_counts_loc = "upper right",  # "upper right"/"upper left"/"lower right"/"lower left"
        label_spike_numbers = False,  # set True to show 1,2,3... at peaks
        label_fontsize = 8,
        label_offset_y = 0.02,  # vertical offset in data units

        # Second figure with only spiking ROIs
        show_spiking_only_figure = True,
        out_fig_spiking_only = "deltaF_F_spiking_only.png",

        # Y-limits
        use_auto_ylim = True,  # autoset y-lims per figure
        auto_ylim_include_zero = True,  # keep y=0 in view
        auto_ylim_pad_frac = 0.05,  # 5% headroom
        ylim_min = 0.0,  # used only if use_auto_ylim=False

        # Spike width filter
        width_mode = "rough",  # "rough" or "fwhm"
        width_threshold_s = 0.50  # minimum width (seconds) to count a spike

    )

    _dff, fig_all, fig_spk = run(cfg)
    a = fig_spk.show()


