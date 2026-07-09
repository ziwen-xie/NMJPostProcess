import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import EngFormatter, AutoMinorLocator
from pathlib import Path

# ====== USER SETTINGS ======
DATA_DIR = "./"          # folder containing B1.csv ... B18.csv
FILE_PREFIX = "B"            # prefix for filenames
N_FILES = 18
CURRENT_COL = "CH2 Current"
VOLTAGE_COL = "CH2 Voltage"
OUT_PREFIX = "iv_mean_std_B"  # output file prefix
GRID_POINTS = 600            # resolution for interpolation
GRAY_COLOR = "#B0B0B0"       # soft gray for individual lines
BLUE_COLOR = "#0072B2"       # scientific blue for mean (same as R journal palette)
INDIV_ALPHA = 0.55           # transparency for gray lines
BAND_ALPHA = 0.18            # transparency for ±1 SD band
MEAN_LW = 2.2
INDIV_LW = 0.9

# ====== LOAD ALL ======
xs, ys = [], []
for i in range(1, N_FILES + 1):
    path = Path(DATA_DIR) / f"{FILE_PREFIX}{i}.csv"
    if not path.exists():
        print(f"⚠️ Missing: {path.name}")
        continue
    df = pd.read_csv(path)
    x = pd.to_numeric(df[CURRENT_COL], errors="coerce").to_numpy()
    y = pd.to_numeric(df[VOLTAGE_COL], errors="coerce").to_numpy()
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    if x.size < 2:
        continue
    idx = np.argsort(x)
    x, y = x[idx], y[idx]
    ux, ui = np.unique(x, return_index=True)
    xs.append(ux)
    ys.append(y[ui])

print(f"Loaded {len(xs)} I–V curves")

# ====== COMMON GRID ======
xmin = max(np.min(x) for x in xs)
xmax = min(np.max(x) for x in xs)
grid = np.linspace(xmin, xmax, GRID_POINTS)

Y = np.vstack([np.interp(grid, x, y) for x, y in zip(xs, ys)])
mean_v = Y.mean(axis=0)
std_v  = Y.std(axis=0, ddof=1)

# ====== PLOT ======
plt.rcParams.update({
    "font.size": 9,
    "axes.linewidth": 1.0,
    "xtick.direction": "in",
    "ytick.direction": "in",
    "xtick.major.size": 4,
    "ytick.major.size": 4,
    "xtick.minor.size": 2.5,
    "ytick.minor.size": 2.5,
    "savefig.bbox": "tight",
})

fig, ax = plt.subplots(figsize=(3.5, 2.7))

# Scale to mA if small currents
current_scale = 1.0
xlabel = "Current (A)"
if np.nanmax(np.abs(grid)) < 0.02:
    current_scale = 1e3
    xlabel = "Current (μA)"

# Light gray individual curves
for x, y in zip(xs, ys):
    ax.plot(x * current_scale, y, color=GRAY_COLOR, lw=INDIV_LW, alpha=INDIV_ALPHA)

# Mean curve (blue) and ±1 SD band
ax.fill_between(grid * current_scale, mean_v - std_v, mean_v + std_v,
                color=BLUE_COLOR, alpha=BAND_ALPHA, label="±1 SD")
ax.plot(grid * current_scale, mean_v, color=BLUE_COLOR, lw=MEAN_LW, label="Mean")

# Axis setup
ax.set_xlabel(xlabel)
ax.set_ylabel("Voltage (V)")
ax.xaxis.set_minor_locator(AutoMinorLocator())
ax.yaxis.set_minor_locator(AutoMinorLocator())
ax.xaxis.set_major_formatter(EngFormatter(unit=""))
ax.yaxis.set_major_formatter(EngFormatter(unit="V"))
ax.legend(frameon=False, fontsize=8.5)

plt.tight_layout()
fig.savefig(f"{OUT_PREFIX}.png", dpi=300)
fig.savefig(f"{OUT_PREFIX}.pdf")
plt.show()

print(f"Saved {OUT_PREFIX}.png and {OUT_PREFIX}.pdf")