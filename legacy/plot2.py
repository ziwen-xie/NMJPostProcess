import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap

# =========================
# Options
# =========================
csv_path = "batch_results/spike_summary_table.csv"
out_svg  = "pattern_heatmap_swapped_3000pt.svg"

COMBINE_SAME_LEVEL = True     # combine all non-Ctrl replicates
AGGREGATION = "sum"           # "sum" or "mean"
AUTO_COLOR_RANGE = True
SWAP_AXES = True              # ROIs on X, Conditions on Y

# Create white → red linear colormap
pink_red = LinearSegmentedColormap.from_list(
    "pink_red",
    ["#f6bea4", "#ff6699", "#ff0000"]
)
# =========================
# Load CSV
# =========================
df = pd.read_csv(csv_path)

df["Condition"] = df["Parameter"].astype(str)
df["Replicate"] = df["Replicate"].astype(int).astype(str)
df["CondRep"]   = df["Condition"] + "_" + df["Replicate"]

roi_cols = [c for c in df.columns if c.strip().isdigit()]

# =========================
# Build matrix with special rules:
# - Keep Ctrl1 and Ctrl3 (exclude Ctrl2)
# - Combine all NON-CTRL replicates
# =========================
if COMBINE_SAME_LEVEL:
    is_ctrl = df["Condition"].str.lower().eq("ctrl")

    # ---- (A) Combine NON-CTRL ----
    df_nonctrl = df[~is_ctrl].copy()

    if AGGREGATION.lower() == "mean":
        mat_nonctrl = df_nonctrl.groupby("Condition", sort=False)[roi_cols].mean().T
    else:
        mat_nonctrl = df_nonctrl.groupby("Condition", sort=False)[roi_cols].sum(min_count=1).T

    nonctrl_order = list(dict.fromkeys(df_nonctrl["Condition"].tolist()))
    if len(nonctrl_order) > 0:
        mat_nonctrl = mat_nonctrl[nonctrl_order]

    # ---- (B) CTRL: Keep Ctrl1 & Ctrl3 ONLY ----
    df_ctrl = df[is_ctrl].copy()
    df_ctrl = df_ctrl[df_ctrl["Replicate"].isin(["1", "3"])]  # exclude Ctrl2

    if df_ctrl.empty:
        mat_ctrl = pd.DataFrame(index=roi_cols)
    else:
        mat_ctrl = df_ctrl.set_index("CondRep")[roi_cols].T

        ctrl_order = [x for x in ["Ctrl_1", "Ctrl_3"] if x in mat_ctrl.columns]
        ctrl_order += [c for c in mat_ctrl.columns if c not in ctrl_order]
        mat_ctrl = mat_ctrl[ctrl_order]

    # ---- (C) Merge ----
    if mat_ctrl.empty:
        mat = mat_nonctrl
    elif mat_nonctrl.empty:
        mat = mat_ctrl
    else:
        mat = pd.concat([mat_ctrl, mat_nonctrl], axis=1)

else:
    # No combining; but still remove Ctrl2
    mask_ctrl2 = df["CondRep"].str.lower().eq("ctrl_2")
    df_wo_ctrl2 = df[~mask_ctrl2].copy()
    mat = df_wo_ctrl2.set_index("CondRep")[roi_cols].T
    mat = mat[df_wo_ctrl2["CondRep"].tolist()]

# =========================
# Swap axes
# =========================
if SWAP_AXES:
    mat_plot = mat.T.copy()
    try:
        sorted_cols = sorted(mat_plot.columns, key=lambda x: int(x))
    except:
        sorted_cols = list(mat_plot.columns)
    mat_plot = mat_plot[sorted_cols]
else:
    mat_plot = mat.copy()

# =========================
# Color range
# =========================
mask = mat_plot.isna()

if AUTO_COLOR_RANGE:
    finite_vals = mat_plot.values[np.isfinite(mat_plot.values)]
    if finite_vals.size == 0:
        vmin, vmax = 0, 1
    else:
        vmin, vmax = float(np.nanmin(finite_vals)), float(np.nanmax(finite_vals))
        if vmin == vmax:
            vmax = vmin + 1
else:
    vmin, vmax = 1, 5

# =========================
# Figure size (3000 pt width)
# =========================
PT_PER_INCH = 72
width_pt = 3000
width_in = width_pt / PT_PER_INCH

n_rows, n_cols = mat_plot.shape
margin_factor = 1.10
height_in = width_in * (n_rows / max(n_cols, 1)) * margin_factor

# =========================
# Global style
# =========================
plt.rcParams.update({
    "font.size": 70,
    "font.family": "Arial",
    "svg.fonttype": "none",   # keep text editable in Illustrator
    "axes.linewidth": 2.0,
})

# =========================
# Plot
# =========================
fig = plt.figure(figsize=(width_in, height_in), constrained_layout=True)
ax = fig.add_subplot(111)



hm = sns.heatmap(
    mat_plot, mask=mask,
    cmap="Reds", vmin=0, vmax=vmax,
    linewidths=1, linecolor="white",
    square=True, annot=True,
    cbar_kws={"pad": 0.02}
)

# ---- COLORBAR ----
cbar = hm.collections[0].colorbar
cbar.ax.tick_params(labelsize=70, width=2, length=10)
cbar.set_label("Spike Count (sum)" if AGGREGATION=="sum" else "Mean Spike Count",
               fontsize=70, labelpad=20)

# ---- LABELS ----
ax.set_title("Pattern Heatmap (Ctrl1 & Ctrl3 separate, Others combined)",
             fontsize=70, fontweight="bold", pad=30)

ax.set_xlabel("ROI", fontsize=70, labelpad=20)
ax.set_ylabel("Condition", fontsize=70, labelpad=20)

# ---- SAFE TICK FORMAT ----
def safe_format(labels, zero_pad=False):
    out = []
    for v in labels:
        s = str(v)
        if zero_pad:
            try:
                out.append(f"{int(float(s)):02d}")
            except:
                out.append(s)
        else:
            out.append(s)
    return out

ax.set_xticklabels(safe_format(mat_plot.columns, zero_pad=True),
                   fontsize=70, rotation=45, ha="right")
ax.set_yticklabels(safe_format(mat_plot.index, zero_pad=False),
                   fontsize=70, rotation=0, va="center")

ax.tick_params(axis="both", which="both", width=2, length=10)

# =========================
# Save (exact width)
# =========================
fig.savefig(out_svg, format="svg")
plt.close(fig)

print(f"Saved {out_svg} ({width_pt} pt x {height_in*PT_PER_INCH:.0f} pt)")
