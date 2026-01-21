# Recreate the raster plot in exactly the same style as the user's reference image
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# Load CSV again
csv_path = "0806_batch_results/spike_summary_table.csv"
df = pd.read_csv(csv_path)

# Sum replicates for each condition
roi_cols = [c for c in df.columns if c.strip().isdigit()]
df_sum = df.groupby("Parameter")[roi_cols].sum().fillna(0)

# Create heatmap-style matrix (ROI × Condition)
mat = df_sum.T
mat.index = pd.Index(map(int, mat.index))
mat = mat.sort_index()  # ROI in ascending numeric order

# Reorder conditions like the example figure
order = ["Ctrl", "20s", "10s", "5s", "2Hz", "5Hz"]
order = [c for c in order if c in mat.columns]
mat = mat[order]

# Plot with exact same style as reference
plt.figure(figsize=(10, 6))
ax = sns.heatmap(
    mat,
    cmap="coolwarm",
    linewidths=1.0,
    linecolor="white",
    cbar_kws={"label": "Value"},
    vmin=1,
    vmax=5,
    square=False
)

# Titles and labels
ax.set_title("Raster Plot of Spike Counts per ROI & Condition", fontsize=16, fontweight="bold", pad=12)
ax.set_xlabel("Condition", fontsize=12)
ax.set_ylabel("ROI", fontsize=12)

# Formatting tick labels
ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha="right", fontsize=10)
ax.set_yticklabels([f"{i:02d}" for i in mat.index], rotation=0, fontsize=10)

plt.tight_layout()
plt.show()
