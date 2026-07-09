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



# =========================
# CONFIG
# =========================
CSV_PATH = "./0718/20-5.csv"          # CSV path
CSV_BG_PATH = "./0718/bg.csv"          # CSV path
ENCODING = "utf-16"                  # files from UV-3600/Fiji often are UTF-16
SKIP_FIRST_ROW = True                # first line is "Channel.001" in your files
TIME_COL_NAME = "Axis [s]"           # time column name in your CSV
ROI_KEY = "ROI"                      # columns containing this substring are ROIs

STIM_COLOR = "red"
STIM_ALPHA = 0.30
ylim_max = 0.80

# ΔF/F baseline frames
BASELINE_FRAMES = 59                 # first 59 frames as baseline

# Stimulation windows (seconds)
STIM_WINDOWS_20 = [(30, 50), (80, 100), (130, 150)]
STIM_WINDOWS_10 = [(30, 40), (70, 80), (110, 120)]
STIM_WINDOWS_5 = [(30, 35), (65, 70), (100, 105)]
STIM_WINDOWS = STIM_WINDOWS_20
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
df_bg = load_fluo_csv(CSV_BG_PATH, encoding=ENCODING, skip_first_row=SKIP_FIRST_ROW)
df_bg = df['ROI.01 []']

# Identify ROI columns & time column
roi_cols = [c for c in df.columns if ROI_KEY in c]
if TIME_COL_NAME not in df.columns:
    raise ValueError(f"Time column '{TIME_COL_NAME}' not found. Columns: {list(df.columns)}")

time = df[TIME_COL_NAME].values

def background_subtraction(F: np.ndarray, t: np.ndarray, bg):
    dff = F - bg
    return dff

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
    dff = background_subtraction(df[col].to_numpy(), time, df_bg.to_numpy())
    dff_vals, _ = compute_dff_8percent_15s(dff, time, window_half=15.0, perc=8.0)
    dff_dict[col] = dff_vals

dff_8pct_15s = pd.DataFrame(dff_dict)
dff_8pct_15s.insert(0, "Time (s)", time)



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
    ax.plot(dff_8pct_15s["Time (s)"], dff_8pct_15s[col], label=col, linewidth=1.2, color=color_map[col])

# Red stimulation windows
for (s, e) in STIM_WINDOWS:
    ax.axvspan(s, e, color=STIM_COLOR, alpha=STIM_ALPHA)


# Styling
ax.axhline(0, linestyle="--", linewidth=1)
ax.set_ylim(0,ylim_max)
ax.set_xlabel("Time (s)")
ax.set_ylabel("ΔF/F")
ax.set_title(f"ΔF/F")

# Normal legend (inside plot, default location)
ax.legend()

plt.tight_layout()
plt.show()

