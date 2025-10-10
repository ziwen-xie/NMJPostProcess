import pandas as pd
import matplotlib.pyplot as plt

# Load the uploaded CSV
file_path = "./0819/20-1.csv"
df = pd.read_csv(file_path, encoding='utf-16', skiprows=1)

# Preview the first few rows to understand structure
df.head()

roi_cols = [col for col in df.columns if "ROI" in col]

baseline = df.loc[:29, roi_cols].mean()

# Calculate ΔF/F
deltaF_F = (df[roi_cols] - baseline) / baseline
deltaF_F.insert(0, "Time (s)", df["Axis [s]"])

# Prepare the plot
plt.figure(figsize=(10, 6))
for col in roi_cols:
    plt.plot(deltaF_F["Time (s)"], deltaF_F[col], label=col)

# Add red transparent blocks for stim periods
stim_windows = [(30, 35), (65, 70), (100, 105)]
for start, end in stim_windows:
    plt.axvspan(start, end, color='red', alpha=0.2)


plt.axhline(0, linestyle='--', linewidth=1)
plt.xlabel("Time (s)")
plt.ylabel("ΔF/F")
plt.title("ΔF/F Over Time for 5s Constant light")
plt.legend()
plt.tight_layout()

plt.show()
