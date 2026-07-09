"""
Violin + box plots of spike latency data — by condition and by ROI,
with pairwise significance brackets and KDE distribution panel.
Sorted low-high, Cohen's d, % reduction vs Ctrl, N labels.
"""

import pathlib
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np
from scipy.stats import gaussian_kde

# ── paths ────────────────────────────────────────────────────────────────
DATA_DIR = pathlib.Path(
    r"0806sub2\analysis_output_20260303_123720"
)
ROI_CSV = DATA_DIR / "latency_per_roi_stats.csv"
COND_CSV = DATA_DIR / "spike_latency_by_condition.csv"
SIG_CSV = DATA_DIR / "latency_significance.csv"

# ── global academic style ────────────────────────────────────────────────
mpl.rcParams.update({
    "font.family":       "Arial",
    "font.size":         9,
    "axes.titlesize":    11,
    "axes.labelsize":    10,
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
# prefer filtered detailed CSV; fall back to loading from subfolders
FILTERED_CSV = DATA_DIR / "spike_latency_detailed_filtered.csv"
if FILTERED_CSV.exists():
    df = pd.read_csv(FILTERED_CSV)
else:
    _frames = []
    for _csv in DATA_DIR.glob("*/spike_latency_detailed.csv"):
        try:
            _tmp = pd.read_csv(_csv)
            _tmp["condition"] = _csv.parent.name
            _frames.append(_tmp)
        except pd.errors.EmptyDataError:
            pass
    df = pd.concat(_frames, ignore_index=True) if _frames else pd.DataFrame()

df_sig = pd.read_csv(SIG_CSV) if SIG_CSV.exists() else pd.DataFrame()

# extract base condition: "10s2" → "10s", Ctrl/Ctrl1 → "Ctrl", Ctrl2+ → "Far Light Control"
import re as _re

def _extract_cond(name):
    ctrl_m = _re.match(r'^Ctrl(\d*)$', name, _re.IGNORECASE)
    if ctrl_m:
        num = ctrl_m.group(1)
        if num == '' or num == '1':
            return 'Ctrl'
        return 'Far Light Control'
    m = _re.match(r'^([a-zA-Z0-9]+?)\d+$', name)
    if m:
        return m.group(1)
    m = _re.match(r'^(\d+)-\d+$', name)
    if m:
        return m.group(1)
    return name

df["cond_base"] = df["condition"].apply(_extract_cond)

# clean ROI names for display: "ROI.10 []" → "ROI 10"
df["ROI_label"] = (
    df["ROI"]
    .str.replace(r"\s*\[.*?\]", "", regex=True)
    .str.replace(".", " ", regex=False)
)

# ── colour palette (auto-extend for unknown conditions) ──────────────────
_known_colors = {
    "5s": "#4C72B0", "10s": "#55A868", "20s": "#C44E52",
    "2hz": "#8172B2", "5hz": "#CCB974", "1mw": "#64B5CD",
    "2mw": "#E5AE38", "Ctrl": "#AAAAAA",
    "Far Light Control": "#D4A0A0",
    "red": "#C44E52", "blue": "#4C72B0",
}
_tab10 = plt.cm.tab10.colors
_all_conds = sorted(df["cond_base"].unique())
cond_colors = {}
_extra_i = 0
for c in _all_conds:
    if c in _known_colors:
        cond_colors[c] = _known_colors[c]
    else:
        cond_colors[c] = mpl.colors.to_hex(_tab10[_extra_i % len(_tab10)])
        _extra_i += 1

# ── compute stats per condition ──────────────────────────────────────────
cond_stats = (
    df.groupby("cond_base")["latency_s"]
    .agg(["mean", "std", "count"])
    .rename(columns={"mean": "avg", "std": "sd", "count": "n"})
)

# Ctrl reference (optional — may not exist in every dataset)
HAS_CTRL = "Ctrl" in cond_stats.index
if HAS_CTRL:
    ctrl_mean = cond_stats.loc["Ctrl", "avg"]
    ctrl_sd = cond_stats.loc["Ctrl", "sd"]
    ctrl_n = cond_stats.loc["Ctrl", "n"]

    def cohens_d(row):
        pooled = np.sqrt(
            ((row["n"] - 1) * row["sd"] ** 2 + (ctrl_n - 1) * ctrl_sd ** 2)
            / (row["n"] + ctrl_n - 2)
        )
        if pooled == 0:
            return 0.0
        return (ctrl_mean - row["avg"]) / pooled

    cond_stats["cohens_d"] = cond_stats.apply(cohens_d, axis=1)
    cond_stats["pct_reduction"] = (ctrl_mean - cond_stats["avg"]) / ctrl_mean * 100

# sort by mean latency (ascending)
cond_stats = cond_stats.sort_values("avg")
cond_order = cond_stats.index.tolist()
cond_pos = {c: i for i, c in enumerate(cond_order)}

# ── compute stats per ROI ────────────────────────────────────────────────
roi_stats = (
    df.groupby("ROI_label")["latency_s"]
    .agg(["mean", "std", "count"])
    .rename(columns={"mean": "avg", "std": "sd", "count": "n"})
    .sort_values("avg")
)
roi_order = roi_stats.index.tolist()

# ── significance brackets helper ─────────────────────────────────────────
def draw_bracket(ax, x1, x2, y, label, lw=0.7, color="#333333"):
    """Draw a significance bracket between x1 and x2 at height y."""
    tip = (y - ax.get_ylim()[0]) * 0.02
    ax.plot([x1, x1, x2, x2], [y - tip, y, y, y - tip],
            lw=lw, color=color, clip_on=False, zorder=10)
    ax.text((x1 + x2) / 2, y + tip * 0.3, label,
            ha="center", va="bottom", fontsize=7, color=color,
            fontweight="bold", zorder=10)


# ── figure: 3 panels ────────────────────────────────────────────────────
fig, (ax1, ax2, ax3) = plt.subplots(
    3, 1,
    figsize=(9, 14),
    gridspec_kw={"height_ratios": [1.4, 1.2, 0.8], "hspace": 0.45},
)

# ═══════════════════════════════════════════════════════════════════════════
# Panel A: by condition (violin + box + significance)
# ═══════════════════════════════════════════════════════════════════════════
data_by_cond = [df.loc[df["cond_base"] == c, "latency_s"].values for c in cond_order]
positions = np.arange(len(cond_order))

vp = ax1.violinplot(
    data_by_cond, positions=positions,
    showextrema=False, showmedians=False, widths=0.7,
)
for i, body in enumerate(vp["bodies"]):
    body.set_facecolor(cond_colors.get(cond_order[i], "#999999"))
    body.set_edgecolor("black")
    body.set_linewidth(0.5)
    body.set_alpha(0.35)

bp = ax1.boxplot(
    data_by_cond, positions=positions,
    widths=0.25, patch_artist=True, showfliers=False, zorder=4,
    medianprops=dict(color="black", linewidth=1.2),
    whiskerprops=dict(linewidth=0.8),
    capprops=dict(linewidth=0.8),
    boxprops=dict(linewidth=0.6),
)
for i, patch in enumerate(bp["boxes"]):
    patch.set_facecolor(cond_colors.get(cond_order[i], "#999999"))
    patch.set_alpha(0.85)

# individual data points (jittered)
rng = np.random.default_rng(42)
for i, (cond, vals) in enumerate(zip(cond_order, data_by_cond)):
    jitter = rng.uniform(-0.12, 0.12, size=len(vals))
    ax1.scatter(
        positions[i] + jitter, vals,
        s=14, color=cond_colors.get(cond, "#999999"),
        edgecolor="black", linewidth=0.3, zorder=5, alpha=0.7,
    )

# N, Cohen's d, % reduction annotations
y_max = max(v.max() for v in data_by_cond if len(v) > 0)
for i, cond in enumerate(cond_order):
    row = cond_stats.loc[cond]
    ax1.text(
        positions[i], row["avg"] * 0.15 + 1.0,
        f"N={int(row['n'])}", ha="center", va="bottom",
        fontsize=7.5, fontweight="bold", color="black",
        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.8),
        zorder=6,
    )
    if not HAS_CTRL or cond == "Ctrl":
        continue
    top = np.max(df.loc[df["cond_base"] == cond, "latency_s"])
    ax1.text(
        positions[i], top + y_max * 0.03,
        f"d={row['cohens_d']:.2f}", ha="center", va="bottom",
        fontsize=6.5, color="#333333",
    )
    sign = "-" if row["pct_reduction"] > 0 else "+"
    ax1.text(
        positions[i], top + y_max * 0.09,
        f"{sign}{abs(row['pct_reduction']):.0f}%",
        ha="center", va="bottom", fontsize=6.5, fontweight="bold",
        color="#B22222" if row["pct_reduction"] > 0 else "#228B22",
    )

# ── pairwise significance brackets (only p < 0.05) ──────────────────────
sig_pairs = df_sig[df_sig["Significance"] != "ns"].copy()
# map to sorted x-positions
sig_pairs["x1"] = sig_pairs["Group_A"].map(cond_pos)
sig_pairs["x2"] = sig_pairs["Group_B"].map(cond_pos)
sig_pairs = sig_pairs.dropna(subset=["x1", "x2"])
# ensure x1 < x2
for idx, r in sig_pairs.iterrows():
    if r["x1"] > r["x2"]:
        sig_pairs.loc[idx, ["x1", "x2"]] = r["x2"], r["x1"]
# sort by span width (narrow brackets first, drawn lower)
sig_pairs["span"] = sig_pairs["x2"] - sig_pairs["x1"]
sig_pairs = sig_pairs.sort_values("span").reset_index(drop=True)

# stagger bracket heights
bracket_base = y_max * 1.18
bracket_step = y_max * 0.07
for k, (_, r) in enumerate(sig_pairs.iterrows()):
    label = r["Significance"]  # "*" or "**"
    y_bracket = bracket_base + k * bracket_step
    draw_bracket(ax1, r["x1"], r["x2"], y_bracket, label)

top_bracket = bracket_base + len(sig_pairs) * bracket_step
ax1.set_ylim(0, top_bracket + y_max * 0.06)

ax1.set_xticks(positions)
ax1.set_xticklabels(cond_order, fontweight="bold")
ax1.set_ylabel("Latency (s)")
ax1.set_title("A.  Spike Latency by Stimulation Condition", loc="left", fontweight="bold")
ax1.spines[["top", "right"]].set_visible(False)
ax1.set_xlim(-0.6, len(cond_order) - 0.4)

# ═══════════════════════════════════════════════════════════════════════════
# Panel B: by ROI (violin + box)
# ═══════════════════════════════════════════════════════════════════════════
data_by_roi = [df.loc[df["ROI_label"] == r, "latency_s"].values for r in roi_order]
positions_r = np.arange(len(roi_order))

vp2 = ax2.violinplot(
    data_by_roi, positions=positions_r,
    showextrema=False, showmedians=False, widths=0.7,
)
for body in vp2["bodies"]:
    body.set_facecolor("#4C72B0")
    body.set_edgecolor("black")
    body.set_linewidth(0.4)
    body.set_alpha(0.30)

bp2 = ax2.boxplot(
    data_by_roi, positions=positions_r,
    widths=0.22, patch_artist=True, showfliers=False, zorder=4,
    medianprops=dict(color="black", linewidth=1),
    whiskerprops=dict(linewidth=0.7),
    capprops=dict(linewidth=0.7),
    boxprops=dict(linewidth=0.5),
)
for patch in bp2["boxes"]:
    patch.set_facecolor("#4C72B0")
    patch.set_alpha(0.75)

for i, (roi, vals) in enumerate(zip(roi_order, data_by_roi)):
    jitter = rng.uniform(-0.10, 0.10, size=len(vals))
    ax2.scatter(
        positions_r[i] + jitter, vals,
        s=10, color="#4C72B0", edgecolor="black",
        linewidth=0.25, zorder=5, alpha=0.65,
    )

for i, roi in enumerate(roi_order):
    row = roi_stats.loc[roi]
    ax2.text(
        positions_r[i], 1.0,
        f"N={int(row['n'])}", ha="center", va="bottom",
        fontsize=5.5, fontweight="bold", color="black",
        bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.8),
        zorder=6,
    )

ax2.set_xticks(positions_r)
ax2.set_xticklabels(roi_order, rotation=55, ha="right", fontsize=6.5)
ax2.set_ylabel("Latency (s)")
ax2.set_title("B.  Spike Latency by ROI", loc="left", fontweight="bold")
ax2.spines[["top", "right"]].set_visible(False)
ax2.set_xlim(-0.6, len(roi_order) - 0.4)
y_max_r = max(v.max() for v in data_by_roi if len(v) > 0)
ax2.set_ylim(0, y_max_r * 1.10)

# ═══════════════════════════════════════════════════════════════════════════
# Panel C: KDE distribution by condition
# ═══════════════════════════════════════════════════════════════════════════
t_grid = np.linspace(0, df["latency_s"].max() + 5, 500)

for cond in cond_order:
    vals = df.loc[df["cond_base"] == cond, "latency_s"].values
    if len(vals) < 2:
        continue
    kde = gaussian_kde(vals, bw_method="silverman")
    density = kde(t_grid)
    ax3.plot(
        t_grid, density,
        color=cond_colors.get(cond, "#999999"),
        linewidth=1.5, label=cond,
    )
    ax3.fill_between(
        t_grid, density,
        color=cond_colors.get(cond, "#999999"),
        alpha=0.15,
    )

ax3.set_xlabel("Latency (s)")
ax3.set_ylabel("Density")
ax3.set_title("C.  Latency Distribution (KDE) by Condition", loc="left", fontweight="bold")
ax3.spines[["top", "right"]].set_visible(False)
ax3.legend(
    frameon=True, framealpha=0.9, edgecolor="#cccccc",
    fontsize=7.5, ncol=4, loc="upper right",
)
ax3.set_xlim(0, t_grid[-1])
ax3.set_ylim(bottom=0)

# ── Ctrl reference line on panels A & B (only if Ctrl exists) ────────────
if HAS_CTRL:
    for ax in (ax1, ax2):
        ax.axhline(ctrl_mean, ls="--", lw=0.7, color="#888888", zorder=2)
        ax.text(
            ax.get_xlim()[1], ctrl_mean + 0.5,
            f"Ctrl mean = {ctrl_mean:.1f} s",
            ha="right", va="bottom", fontsize=7, color="#888888",
        )
    ax3.axvline(ctrl_mean, ls="--", lw=0.7, color="#888888", zorder=2)
    ax3.text(
        ctrl_mean + 0.5, ax3.get_ylim()[1] * 0.92,
        f"Ctrl mean\n{ctrl_mean:.1f} s",
        ha="left", va="top", fontsize=7, color="#888888",
    )

# ── save ─────────────────────────────────────────────────────────────────
out_png = DATA_DIR / "latency_barplot.png"
out_svg = DATA_DIR / "latency_barplot.svg"
fig.savefig(out_png)
fig.savefig(out_svg)
plt.close(fig)
print(f"Saved  {out_png}")
print(f"Saved  {out_svg}")
