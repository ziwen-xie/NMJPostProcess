import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

csv_path = "batch_results/spike_summary_table.csv"
df = pd.read_csv(csv_path)

df["Condition"] = df["Parameter"].astype(str)
df["Replicate"] = df["Replicate"].astype(int).astype(str)
df["CondRep"] = df["Condition"] + "_" + df["Replicate"]

roi_cols = [c for c in df.columns if c.strip().isdigit()]

mat = df.set_index("CondRep")[roi_cols].T
mat.index = pd.Index(map(int, mat.index))
mat = mat.sort_index()
cond_order = df["CondRep"].tolist()
mat = mat[cond_order]

# Safety: the cell in question should be NaN
if "1mW_3" in mat.columns:
    print("Value @ ROI01, 1mW_3:", mat.loc[1, "1mW_3"])

mask = mat.isna()  # ensure blanks stay blank

plt.figure(figsize=(100,40))
ax = sns.heatmap(
    mat, mask=mask,
    cmap="coolwarm", vmin=1, vmax=5,
    linewidths=1.0, linecolor="white",
    square=True, annot=False
)
cbar = ax.collections[0].colorbar
cbar.ax.tick_params(labelsize=70)      # tick font
cbar.set_label("Spike Count", fontsize=70)  # label font

ax.set_title("Pattern Heatmap of All Conditions", fontsize=70, fontweight="bold", pad=70)
ax.set_xlabel("Condition / Replicate", fontsize=70)
ax.set_ylabel("Parameter (Sample ID)", fontsize=70)
ax.set_yticklabels([f"{i:02d}" for i in mat.index], fontsize=70, rotation=0)
ax.set_xticklabels(ax.get_xticklabels(), rotation=45, fontsize=70, ha="right")
plt.tight_layout()
plt.show()
