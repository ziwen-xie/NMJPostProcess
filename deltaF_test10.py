
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

# =========================
# USER SETTINGS
# =========================
CSV_PATH = "./0819/20-1.csv"          # <-- put your CSV name here
ENCODING = "utf-16"                  # files from UV-3600/Fiji often are UTF-16
SKIP_FIRST_ROW = True                # first line is "Channel.001" in your files
TIME_COL_NAME = "Axis [s]"           # time column name in your CSV
ROI_KEY = "ROI"                      # columns containing this substring are ROIs

# ΔF/F baseline frames
BASELINE_FRAMES = 59                 # first 59 frames as baseline

# Spike detection parameters
WINDOW_SEC = 10                      # sliding window length in seconds
THRESHOLD = 0.01                 # peak-to-peak threshold for "spike"

# Stimulation windows (seconds)
STIM_WINDOWS = [(30, 40), (70, 80), (110, 120)]

# Output files
OUT_FIG = "deltaF_F_plot_10s_spikes_thr0015_red_labels_above_default_legend.png"
OUT_CSV = "spikes_10s_thr0015.csv"   # set to None if you don’t want a CSV


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
# SPIKE DETECTION (peak-to-peak in a time window)
# =========================

def detect_spikes(dff_df: pd.DataFrame,
                  time_col: str,
                  roi_columns: list[str],
                  window_sec: float,
                  threshold: float):
    """
    Returns dict {roi: [(start_time, end_time, p2p_change), ...]}
    Sliding window starts at each time sample.
    """
    results = {}
    t = dff_df[time_col].values
    for roi in roi_columns:
        events = []
        for i in range(len(dff_df)):
            start = t[i]
            end = start + window_sec
            mask = (t >= start) & (t <= end)
            vals = dff_df.loc[mask, roi].values
            if vals.size > 0:
                change = float(vals.max() - vals.min())
                if change > threshold:
                    events.append((start, end, change))
        results[roi] = events
    return results
# ---- Helpers to merge windows and summarize counts ----
def merge_windows(events, gap=0.0):
    """
    Merge overlapping/adjacent (within 'gap' seconds) windows.
    events: list of (start, end, change)
    Returns: list of merged (start, end, max_change)
    """
    if not events:
        return []
    ev = sorted(events, key=lambda x: x[0])
    merged = [list(ev[0])]
    for s, e, ch in ev[1:]:
        last = merged[-1]
        if s <= last[1] + gap:          # overlap or touching within 'gap'
            last[1] = max(last[1], e)    # extend end
            last[2] = max(last[2], ch)   # keep max peak-to-peak
        else:
            merged.append([s, e, ch])
    return [tuple(m) for m in merged]

def summarize_spike_counts(spikes_dict, stim_windows=None, gap=0.0,
                           exclude_before=30.0,
                           save_csv_path="spike_counts_summary.csv"):
    """
    spikes_dict: {roi: [(start, end, change), ...]} from detect_spikes()
    stim_windows: list[(s,e)] in seconds or None
    gap: seconds to merge adjacent spikes
    exclude_before: ignore spikes starting before this time (s)
    """
    rows = []
    for roi, events in spikes_dict.items():
        # Filter out early events
        events = [(s, e, ch) for (s, e, ch) in events if s >= exclude_before]

        merged = merge_windows(events, gap=gap)

        if stim_windows:
            in_stim = 0
            for s, e, _ in merged:
                if any((s <= se and e >= ss) for (ss, se) in stim_windows):
                    in_stim += 1
            out_stim = len(merged) - in_stim
        else:
            in_stim = None
            out_stim = None

        rows.append({
            "ROI": roi,
            "n_spikes_all": len(merged),
            "n_spikes_in_stim": in_stim,
            "n_spikes_outside": out_stim
        })

    summary = pd.DataFrame(rows).sort_values("ROI")
    summary.to_csv(save_csv_path, index=False)
    return summary


spikes = detect_spikes(dff, "Time (s)", roi_cols, WINDOW_SEC, THRESHOLD)
spike_summary = summarize_spike_counts(
    spikes_dict=spikes,
    stim_windows=STIM_WINDOWS,
    gap=0.0,                 # merge overlapping windows if needed
    exclude_before=30.0,     # ignore spikes in first 30 s
    save_csv_path="spike_counts_summary.csv"
)

print(spike_summary)

# Optional: write detections to CSV
if OUT_CSV:
    rows = []
    for roi, evs in spikes.items():
        for (s, e, ch) in evs:
            rows.append({"ROI": roi, "start_s": s, "end_s": e, "duration_s": e - s, "peak_to_peak": ch})
    pd.DataFrame(rows).to_csv(OUT_CSV, index=False)

# =========================
# PLOTTING
# =========================
fig = plt.figure(figsize=(10, 6))
gs = fig.add_gridspec(nrows=2, ncols=1, height_ratios=[3, 1])
ax = fig.add_subplot(gs[0])

# Color map for consistency (optional)
colors = plt.cm.tab10.colors
color_map = {roi_cols[i]: colors[i % len(colors)] for i in range(len(roi_cols))}

# Plot ΔF/F traces
for col in roi_cols:
    ax.plot(dff["Time (s)"], dff[col], label=col, linewidth=1.2, color=color_map[col])

# Red stimulation windows
for (s, e) in STIM_WINDOWS:
    ax.axvspan(s, e, color="red", alpha=0.30)

# Blue markers at TOP + labels ABOVE the plot
# We use axis-transform so markers/labels sit at the top margin
for roi, evs in spikes.items():
    for (start, end, change) in evs:
        # Marker at top edge of axes (y=1.0 in axes coords)
        ax.plot([start], [1.0], marker="v", markersize=4, color="blue",
                transform=ax.get_xaxis_transform(), clip_on=False)
        # Label just above the axes
        ax.text(start, 1.04, f"{roi}  Δ={change:.3f}",
                transform=ax.get_xaxis_transform(),
                rotation=90, fontsize=6, ha="center", va="bottom", clip_on=False)

# Styling
ax.axhline(0, linestyle="--", linewidth=1)
ax.set_xlabel("Time (s)")
ax.set_ylabel("ΔF/F")
ax.set_title(f"ΔF/F of 10s constant light)")

# Normal legend (inside plot, default location)
ax.legend()

spike_summary = summarize_spike_counts(
    spikes_dict=spikes,
    stim_windows=STIM_WINDOWS,
    gap=0.0,
    exclude_before=30.0,
    save_csv_path="spike_counts_summary.csv"
)

# Plot table underneath the main plot
from pandas.plotting import table

filtered_summary = spike_summary.loc[spike_summary["n_spikes_all"] > 0].copy()
ax_tbl = fig.add_subplot(gs[1])
if filtered_summary.empty:
    # Nothing to show: write a simple note instead of a table
    ax_tbl.text(0.5, 0.5, "No ROIs with spikes to summarize.",
                ha="center", va="center", fontsize=10)
else:

    ax_tbl.axis("off")
    tbl = table(ax_tbl, filtered_summary, loc='center', cellLoc='center', rowLoc='center',
                colWidths=[1.0/len(spike_summary.columns)]*len(spike_summary.columns))
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    tbl.scale(1.0, 1.2)

# Adjust layout so table fits
plt.subplots_adjust(left=0.12, right=0.98, top=0.92, bottom=0.08, hspace=0.06)

plt.tight_layout()
plt.savefig(OUT_FIG, dpi=300)
plt.show()

print(f"Saved figure to: {OUT_FIG}")
if OUT_CSV:
    print(f"Saved detections to: {OUT_CSV}")
