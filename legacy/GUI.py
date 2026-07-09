# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Tuple, List, Optional, Dict
import re

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
    ylim_max: float = 1
    fig_size: Tuple[float, float] = (10, 6)
    cmap_name: str = "tab10"
    stim_color: str = "red"
    stim_alpha: float = 0.30
    use_auto_ylim: bool = False
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
    min_spike_distance_s: Optional[float] = None
    exclude_bg_roi_from_detection: bool = True
    out_spike_csv: Optional[str] = "spike_summary.csv"
    out_spike_stats_csv: Optional[str] = "spike_baseline_stats.csv"

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
    width_threshold_s: float = 0.50

    # ROIs to exclude from plotting
    exclude_roi_map: Dict[str, bool] = field(default_factory=dict)

    # Stimulation windows
    stim_preset: str = "20s"
    stim_windows_custom: Optional[List[Tuple[float, float]]] = None
    stim_windows: List[Tuple[float, float]] = None

    ### NEW — spike exclusion w.r.t. stim windows
    exclude_spikes_in_stim: bool = False  # don't count spikes that fall inside a stim window
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
    dff = (F - F0) / (F0)
    return dff, F0


def compute_all_dff(
        df_main: pd.DataFrame,
        roi_cols: Iterable[str],
        bg_vec: np.ndarray,
        t: np.ndarray,
        cfg: Config
) -> pd.DataFrame:
    dff_dict = {}
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
      - If it contains '20s' or a '20-' pattern -> '20s'
      - If it contains '10s' or a '10-' pattern -> '10s'
      - If it contains '5s'  or a '5-'  pattern -> '5s'
      - Otherwise default to '20s'
    Matching is case-insensitive.
    """
    s_low = s.lower()
    # explicit 'xs' first (e.g., 20s-3, 10s_2, 5s)
    if "20s" in s_low or re.search(r"\b20[-_]", s_low):
        return "20s"
    if "10s" in s_low or re.search(r"\b10[-_]", s_low):
        return "10s"
    if "5s"  in s_low or re.search(r"\b5[-_]",  s_low):
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
        y: np.ndarray, spike_z_sigma: float, start_idx: int, end_idx: int
) -> Tuple[float, float, float]:
    n = y.size
    if n == 0:
        return 0.0, 0.0, 0.0
    s = max(0, min(start_idx, end_idx))
    e = min(n - 1, max(start_idx, end_idx))
    base = y[s:e + 1]
    if base.size == 0:
        base = y[:1]

    mean0 = float(np.mean(base))
    sd0 = float(np.std(base, ddof=1)) if base.size > 1 else 0.0
    thr = mean0 + spike_z_sigma * (sd0 if sd0 > 0 else 1e-12)
    return mean0, sd0, thr


def _baseline_stats_first_n(y: np.ndarray, spike_z_sigma: float, n: int) -> Tuple[float, float, float]:
    n_eff = min(n, y.size)
    base = y[:n_eff]
    mean0 = float(np.mean(base))
    sd0 = float(np.std(base, ddof=1)) if n_eff > 1 else 0.0
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
        accepted_peak_idxs = []

        for run in runs:
            k_peak = run[np.argmax(y[run])]
            rough_w, fwhm_w = _measure_run_widths(y, t, run, k_peak, baseline_mean=mean0)
            measured = rough_w if width_mode.lower() == "rough" else fwhm_w
            if np.isfinite(measured) and (measured >= width_threshold_s):
                accepted_peak_idxs.append(int(k_peak))

        if accepted_peak_idxs:
            accepted_peak_idxs = np.array(sorted(accepted_peak_idxs), dtype=int)
            accepted_peak_idxs = _enforce_min_distance(accepted_peak_idxs, t, min_distance_s)
            peak_times = t[accepted_peak_idxs]

            # Exclude spikes before 10 seconds
            peak_times = peak_times[peak_times >= 10.0]

            if exclude_spikes_in_windows and stim_windows:
                peak_times = filter_times_outside_windows(
                    peak_times, stim_windows, pad=stim_exclusion_pad_s
                )
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
            # Run your detector for this file, then pull just this ROI’s peaks
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
                exclude_spikes_in_windows=cfg.exclude_spikes_in_stim,
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
                exclude_spikes_in_windows=cfg.exclude_spikes_in_stim,
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
        exclude_spikes_in_windows=cfg.exclude_spikes_in_stim,
        stim_exclusion_pad_s=cfg.stim_exclusion_pad_s,
    )

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
            bg_column_name="ROI.01 []",
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
            input_folder="./1222",
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
# GUI AND EXECUTION LOGIC
# ==========================================

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk  # Requires: pip install pillow
import os



# --- 1. The "Glue" Logic ---
# This function connects your library functions together to process one file
def run_single_file_pipeline(file_path: Path, config: Config) -> str:
    """
    Runs the loading, dFF, spike detection, and plotting for one file.
    Returns the path to the saved plot image.
    """
    # 1. Update Config path
    config.csv_path = str(file_path)

    # 2. Auto-infer stim preset if enabled
    if config.stim_preset_infer_from_name:
        apply_inferred_stim_preset(config, name_hint=file_path.name)

    # 3. Load Data
    df = load_fluo_csv(config.csv_path, config.encoding, config.skip_first_row)

    # 4. Identify Columns
    roi_cols = find_roi_columns(df, config.roi_key)
    if not roi_cols:
        raise ValueError(f"No ROI columns found in {file_path.name}")

    # 5. Background Subtraction
    bg_vec = select_background(df, config)
    t = df[config.time_col].to_numpy(dtype=float)

    # 6. Compute DFF
    dff_df = compute_all_dff(df, roi_cols, bg_vec, t, config)

    # 7. Spike Detection
    # Note: Using your detect_spikes_across_rois function
    _, _, spike_times = detect_spikes_across_rois(
        dff_table=dff_df,
        roi_cols=roi_cols,
        time_col="Time (s)",
        spike_z_sigma=config.spike_z_sigma,
        width_mode=config.width_mode,
        width_threshold_s=config.width_threshold_s,
        stim_windows=config.stim_windows,
        exclude_spikes_in_windows=config.exclude_spikes_in_stim
    )

    # 8. Plotting
    # We check if background was an ROI to handle exclusion logic
    bg_was_roi = (config.bg_source == "roi_column")

    fig = plot_dff(dff_df, roi_cols, config, bg_was_roi, spike_times)

    # 9. Save Image
    output_filename = f"Delta_F_plot_{file_path.stem}.png"
    output_path = file_path.parent / output_filename
    fig.savefig(output_path, dpi=100)
    plt.close(fig)  # Close to free memory

    return str(output_path)


# --- 2. The GUI Class ---

class AnalysisGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Calcium Imaging Analysis Tool")
        self.root.geometry("1100x850")

        self.file_paths = []
        self.generated_images = []

        # --- Layout Containers ---
        # Top: Settings & Files (Horizontal Split)
        # Bottom: Grid Preview

        main_pane = tk.PanedWindow(root, orient=tk.VERTICAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        top_frame = tk.Frame(main_pane)
        main_pane.add(top_frame, height=350)

        # Left: File Manager
        left_frame = tk.LabelFrame(top_frame, text="1. Load Files", padx=10, pady=10)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.btn_add = tk.Button(left_frame, text="Add CSV Files", command=self.add_files, bg="#e1e1e1")
        self.btn_add.pack(fill=tk.X, pady=5)

        self.btn_clear = tk.Button(left_frame, text="Clear List", command=self.clear_files)
        self.btn_clear.pack(fill=tk.X, pady=2)

        self.listbox = tk.Listbox(left_frame, selectmode=tk.EXTENDED)
        self.listbox.pack(fill=tk.BOTH, expand=True, pady=5)

        # Right: Settings
        right_frame = tk.LabelFrame(top_frame, text="2. Settings", padx=10, pady=10)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False, ipadx=10)

        # -- Settings Fields --
        self.entries = {}
        self.create_setting_entry(right_frame, "Stim Preset (20s/10s/5s/custom)", "20s")
        self.create_setting_entry(right_frame, "Infer Preset from Name (True/False)", "True")
        self.create_setting_entry(right_frame, "Sigma (Spike Threshold)", "5.0")
        self.create_setting_entry(right_frame, "Baseline Window (s)", "15.0")
        self.create_setting_entry(right_frame, "ROI Key (e.g., ROI)", "ROI")
        self.create_setting_entry(right_frame, "BG Column (e.g., ROI.01 [])", "ROI.01 []")

        # Run Button
        self.btn_run = tk.Button(right_frame, text="RUN ANALYSIS", command=self.run_analysis,
                                 bg="green", fg="white", font=("Arial", 12, "bold"))
        self.btn_run.pack(side=tk.BOTTOM, fill=tk.X, pady=20)

        # --- Bottom: Image Grid ---
        bottom_frame = tk.LabelFrame(main_pane, text="3. Preview (Last 25 Traces)", padx=10, pady=10)
        main_pane.add(bottom_frame)

        # Canvas for the grid (to center it)
        self.grid_frame = tk.Frame(bottom_frame)
        self.grid_frame.pack(fill=tk.BOTH, expand=True)

        # Create 5x5 Matrix of Labels
        self.image_slots = []
        for r in range(5):
            for c in range(5):
                lbl = tk.Label(self.grid_frame, text=".", relief=tk.RIDGE, bg="#f0f0f0", width=20, height=10)
                lbl.grid(row=r, column=c, padx=2, pady=2, sticky="nsew")
                self.image_slots.append(lbl)

        # Configure grid weights
        for i in range(5):
            self.grid_frame.columnconfigure(i, weight=1)
            self.grid_frame.rowconfigure(i, weight=1)

    def create_setting_entry(self, parent, label_text, default_val):
        frame = tk.Frame(parent)
        frame.pack(fill=tk.X, pady=2)
        lbl = tk.Label(frame, text=label_text, width=30, anchor="w")
        lbl.pack(side=tk.LEFT)
        entry = tk.Entry(frame)
        entry.insert(0, str(default_val))
        entry.pack(side=tk.RIGHT, expand=True, fill=tk.X)
        self.entries[label_text] = entry

    def add_files(self):
        files = filedialog.askopenfilenames(filetypes=[("CSV Files", "*.csv")])
        for f in files:
            if f not in self.file_paths:
                self.file_paths.append(f)
                self.listbox.insert(tk.END, os.path.basename(f))

    def clear_files(self):
        self.file_paths = []
        self.listbox.delete(0, tk.END)

    def get_config_from_ui(self):
        # Create a default config
        cfg = Config()

        # Override with UI values
        try:
            cfg.stim_preset = self.entries["Stim Preset (20s/10s/5s/custom)"].get()

            infer_val = self.entries["Infer Preset from Name (True/False)"].get().lower()
            cfg.stim_preset_infer_from_name = (infer_val == 'true')

            cfg.spike_z_sigma = float(self.entries["Sigma (Spike Threshold)"].get())
            cfg.baseline_window_half_s = float(self.entries["Baseline Window (s)"].get())
            cfg.roi_key = self.entries["ROI Key (e.g., ROI)"].get()
            cfg.bg_column_name = self.entries["BG Column (e.g., ROI.01 [])"].get()

            # Re-init logic to handle presets logic (calling __post_init__ manually if needed,
            # but since we are modifying dataclass after init, we might need to manually set windows)
            # The cleanest way is to re-run the logic from __post_init__ here:
            presets = {
                "20s": [(30, 50), (80, 100), (130, 150)],
                "10s": [(30, 40), (70, 80), (110, 120)],
                "5s": [(30, 35), (65, 70), (100, 105)],
                "none": [],
            }
            if cfg.stim_preset in presets:
                cfg.stim_windows = presets[cfg.stim_preset]

        except ValueError as e:
            messagebox.showerror("Config Error", f"Invalid input in settings: {e}")
            return None
        return cfg

    def run_analysis(self):
        if not self.file_paths:
            messagebox.showwarning("No Files", "Please add CSV files first.")
            return

        cfg = self.get_config_from_ui()
        if not cfg:
            return

        self.generated_images = []

        # Reset grid visual
        for lbl in self.image_slots:
            lbl.config(image='', text="Processing...", bg="#e1e1e1")

        self.root.update()

        # Run Loop
        try:
            for i, f_path in enumerate(self.file_paths):
                # Update UI status
                if i < 25:
                    self.image_slots[i].config(text=f"Running...\n{os.path.basename(f_path)}")
                    self.root.update()

                path_obj = Path(f_path)
                out_img = run_single_file_pipeline(path_obj, cfg)
                self.generated_images.append(out_img)

            self.update_grid()
            messagebox.showinfo("Done", f"Processed {len(self.file_paths)} files successfully.")

        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", f"An error occurred:\n{str(e)}")

    def update_grid(self):
        # We only show the first 25 images to fit the 5x5 grid
        to_show = self.generated_images[:25]

        for i, img_path in enumerate(to_show):
            try:
                # Load and Resize Image
                pil_img = Image.open(img_path)

                # Resize keeping aspect ratio roughly
                pil_img.thumbnail((200, 150))

                tk_img = ImageTk.PhotoImage(pil_img)

                lbl = self.image_slots[i]
                lbl.config(image=tk_img, text="", bg="white")
                lbl.image = tk_img  # Keep reference!

            except Exception as e:
                print(f"Failed to load image {img_path}: {e}")

        # Clear unused slots
        for i in range(len(to_show), 25):
            self.image_slots[i].config(image='', text="Empty", bg="#f0f0f0")


# --- 3. Main Entry Point ---

if __name__ == "__main__":
    # Check for Pillow
    try:
        import PIL
    except ImportError:
        print("Please install Pillow: pip install pillow")
        exit()

    root = tk.Tk()
    app = AnalysisGUI(root)
    root.mainloop()