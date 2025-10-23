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

plt.figure(figsize=(12, 7))
ax = sns.heatmap(
    mat, mask=mask,
    cmap="coolwarm", vmin=1, vmax=5,
    linewidths=1.0, linecolor="white",
    cbar_kws={"label": "Value"},
    square=False, annot=False
)
ax.set_title("Pattern Heatmap of All Conditions", fontsize=16, fontweight="bold", pad=12)
ax.set_xlabel("Condition / Replicate", fontsize=12)
ax.set_ylabel("Parameter (Sample ID)", fontsize=12)
ax.set_yticklabels([f"{i:02d}" for i in mat.index], rotation=0)
ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha="right")
plt.tight_layout()
plt.show()
