"""
Bar plot of mean spike latency per ROI, sorted ascending,
with SEM error bars, individual data points, and mean labels.
"""

import pathlib
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np

# ── paths ────────────────────────────────────────────────────────────────
DATA_DIR = pathlib.Path(
    r"0806sub2\analysis_output_20260303_123720"
)
ROI_CSV = DATA_DIR / "latency_per_roi_stats.csv"
DETAILED_CSV = DATA_DIR / "spike_latency_detailed_filtered.csv"
print("start")

# ── academic style ───────────────────────────────────────────────────────
mpl.rcParams.update({
    "font.family":       "Arial",
    "font.size":         9,
    "axes.titlesize":    12,
    "axes.labelsize":    11,
    "xtick.labelsize":   8.5,
    "ytick.labelsize":   9,
    "axes.linewidth":    0.8,
    "xtick.major.width": 0.8,
    "ytick.major.width": 0.8,
    "xtick.major.size":  3.5,
    "ytick.major.size":  3.5,
    "svg.fonttype":      "none",
    "pdf.fonttype":      42,
    "figure.dpi":        300,
    "savefig.dpi":       300,
    "savefig.bbox":      "tight",
})

# ── load data ────────────────────────────────────────────────────────────
df_roi = pd.read_csv(ROI_CSV)
# normalise column name (some pipelines output Mean_Latency_s, others Avg_Latency_s)
if "Mean_Latency_s" in df_roi.columns and "Avg_Latency_s" not in df_roi.columns:
    df_roi.rename(columns={"Mean_Latency_s": "Avg_Latency_s"}, inplace=True)
df_detail = pd.read_csv(DETAILED_CSV)

# clean ROI labels
df_roi["ROI_label"] = (
    df_roi["ROI"]
    .str.replace(r"\s*\[.*?\]", "", regex=True)
    .str.replace(".", " ", regex=False)
)
df_detail["ROI_label"] = (
    df_detail["ROI"]
    .str.replace(r"\s*\[.*?\]", "", regex=True)
    .str.replace(".", " ", regex=False)
)

# sort by mean latency ascending
df_roi = df_roi.sort_values("Avg_Latency_s").reset_index(drop=True)

# ── colour gradient: low latency → blue, high → red ─────────────────────
cmap = mpl.colormaps["RdYlBu_r"]
norm = mpl.colors.Normalize(
    vmin=df_roi["Avg_Latency_s"].min(),
    vmax=df_roi["Avg_Latency_s"].max(),
)
bar_colors = [cmap(norm(v)) for v in df_roi["Avg_Latency_s"]]

# ── figure ───────────────────────────────────────────────────────────────
fig, (ax, ax2) = plt.subplots(
    2, 1, figsize=(12, 9.5),
    gridspec_kw={"height_ratios": [1, 0.7], "hspace": 0.40},
)

x = np.arange(len(df_roi))
sem = df_roi["SEM_Latency_s"].fillna(0)

bars = ax.bar(
    x, df_roi["Avg_Latency_s"],
    yerr=sem, capsize=3,
    color=bar_colors, edgecolor="black", linewidth=0.5,
    width=0.65, zorder=3,
    error_kw={"elinewidth": 0.8, "capthick": 0.8, "color": "#333333"},
)

# overlay individual data points
rng = np.random.default_rng(42)
for i, row in df_roi.iterrows():
    roi_label = row["ROI_label"]
    vals = df_detail.loc[df_detail["ROI_label"] == roi_label, "latency_s"].values
    if len(vals) == 0:
        continue
    jitter = rng.uniform(-0.18, 0.18, size=len(vals))
    ax.scatter(
        x[i] + jitter, vals,
        s=16, color="white", edgecolor="black",
        linewidth=0.4, zorder=5, alpha=0.85,
    )

# mean value + N label on each bar
for i, row in df_roi.iterrows():
    mean_val = row["Avg_Latency_s"]
    n = int(row["Spike_Count"])
    bar_top = mean_val + (row["SEM_Latency_s"] if pd.notna(row["SEM_Latency_s"]) else 0)
    # mean value above error bar
    ax.text(
        x[i], bar_top + 1.0,
        f"{mean_val:.1f}",
        ha="center", va="bottom", fontsize=7, fontweight="bold",
        color="#222222",
    )
    # N inside bar near base
    ax.text(
        x[i], 1.2,
        f"N={n}", ha="center", va="bottom",
        fontsize=6.5, fontweight="bold", color="#444444",
        bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.85),
        zorder=6,
    )

# grand mean reference line
grand_mean = np.average(df_roi["Avg_Latency_s"], weights=df_roi["Spike_Count"])
ax.axhline(grand_mean, ls="--", lw=0.8, color="#888888", zorder=2)
ax.text(
    x[-1] + 0.4, grand_mean + 0.4,
    f"weighted mean = {grand_mean:.1f} s",
    ha="right", va="bottom", fontsize=7.5, color="#888888",
)

# axes
ax.set_xticks(x)
ax.set_xticklabels(df_roi["ROI_label"], rotation=45, ha="right", fontweight="bold")
ax.set_ylabel("Mean Latency (s)")
ax.set_title("A.  Spike Latency per ROI", loc="left", fontweight="bold")
ax.spines[["top", "right"]].set_visible(False)
ax.set_xlim(-0.6, len(df_roi) - 0.4)
ax.set_ylim(0, ax.get_ylim()[1] * 1.12)

# colour bar legend (spans both panels)
sm = mpl.cm.ScalarMappable(cmap=cmap, norm=norm)
sm.set_array([])
cbar = fig.colorbar(sm, ax=[ax, ax2], pad=0.02, aspect=40, shrink=0.6)
cbar.set_label("Mean Latency (s)", fontsize=9)
cbar.outline.set_linewidth(0.5)

# ═══════════════════════════════════════════════════════════════════════════
# Panel B: line diagram — mean latency per ROI with SEM shading
# ═══════════════════════════════════════════════════════════════════════════
means = df_roi["Avg_Latency_s"].values
sems = df_roi["SEM_Latency_s"].fillna(0).values
line_colors = [cmap(norm(v)) for v in means]

# line connecting means
ax2.plot(x, means, color="#333333", linewidth=1.2, zorder=3, marker="")

# SEM shaded band
ax2.fill_between(
    x, means - sems, means + sems,
    color="#4C72B0", alpha=0.15, zorder=2, label="SEM",
)

# coloured markers at each ROI
for i in range(len(x)):
    ax2.plot(
        x[i], means[i],
        marker="o", markersize=7,
        color=line_colors[i], markeredgecolor="black",
        markeredgewidth=0.6, zorder=5,
    )
    # mean value label
    ax2.annotate(
        f"{means[i]:.1f}",
        (x[i], means[i]),
        textcoords="offset points", xytext=(0, 9),
        ha="center", va="bottom", fontsize=6.5, color="#222222",
        fontweight="bold",
    )

# grand mean reference
ax2.axhline(grand_mean, ls="--", lw=0.8, color="#888888", zorder=1)
ax2.text(
    x[-1] + 0.4, grand_mean + 0.4,
    f"weighted mean = {grand_mean:.1f} s",
    ha="right", va="bottom", fontsize=7.5, color="#888888",
)

ax2.set_xticks(x)
ax2.set_xticklabels(df_roi["ROI_label"], rotation=45, ha="right", fontweight="bold")
ax2.set_ylabel("Mean Latency (s)")
ax2.set_title("B.  Mean Latency Trend across ROIs", loc="left", fontweight="bold")
ax2.spines[["top", "right"]].set_visible(False)
ax2.set_xlim(-0.6, len(df_roi) - 0.4)
ax2.set_ylim(0, max(means + sems) * 1.18)
ax2.legend(loc="upper left", fontsize=8, framealpha=0.9, edgecolor="#cccccc")

# ── save ─────────────────────────────────────────────────────────────────
out_png = DATA_DIR / "latency_per_roi.png"
out_svg = DATA_DIR / "latency_per_roi.svg"
fig.savefig(out_png)
fig.savefig(out_svg)
plt.close(fig)
print(f"Saved  {out_png}")
print(f"Saved  {out_svg}")
