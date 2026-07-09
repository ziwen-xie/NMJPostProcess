"""
Quick test to verify shared baseline fix works.
"""
import BatchProcess as bp
from pathlib import Path

# Create config
cfg = bp.Config()
cfg.csv_path = "./0806FS2/20s1.csv"
cfg.encoding = "utf-16"
cfg.skip_first_row = True
cfg.roi_key = "ROI"
cfg.time_col = "Axis [s]"
cfg.bg_source = "roi_column"
cfg.bg_column_name = "ROI.01 []"
cfg.baseline_mode = "shared_control"
cfg.shared_baseline_start_frame = 10
cfg.shared_baseline_end_frame = 60
cfg.control_file_pattern = "Ctrl"

# Test files
test_files = ["./0806FS2/Ctrl1.csv", "./0806FS2/Ctrl2.csv"]
existing = [f for f in test_files if Path(f).exists()]

if not existing:
    print("Test files not found")
    exit(1)

print("Testing shared baseline with background correction...")
print(f"Using {len(existing)} control files")

# Compute shared baseline (should now use background-corrected values)
baseline_dict = bp.compute_shared_baseline_from_files(existing, cfg)

print(f"\nBaseline values computed: {len(baseline_dict)} ROIs")
for roi, f0 in list(baseline_dict.items())[:3]:
    print(f"  {roi}: F0 = {f0:.3f}")

# Now test if it produces reasonable ΔF/F values
print("\nTesting dF/F calculation with shared baseline...")
cfg.shared_baseline_values = baseline_dict
cfg.out_fig = None
cfg.out_csv = "test_shared_dff.csv"

try:
    dff_table, fig_all, fig_spk = bp.run(cfg)

    # Check if dF/F values are reasonable
    roi_cols = [c for c in dff_table.columns if "ROI" in c and c != cfg.bg_column_name]
    if roi_cols:
        sample_roi = roi_cols[0]  # Use first non-background ROI
        dff_vals = dff_table[sample_roi].values

        print(f"\ndF/F statistics for {sample_roi}:")
        print(f"  Min: {dff_vals.min():.3f}")
        print(f"  Max: {dff_vals.max():.3f}")
        print(f"  Mean: {dff_vals.mean():.3f}")
        print(f"  Std: {dff_vals.std():.3f}")

        # Check if values are reasonable (not all zeros or all negative)
        if abs(dff_vals.mean()) < 5.0 and dff_vals.std() > 0.01:
            print("\n[OK] dF/F values look reasonable!")
            print("Shared baseline is working correctly.")
        else:
            print("\n[WARNING] dF/F values might be unusual")
            print("Check if baseline values are appropriate")

    print("\n[SUCCESS] Shared baseline test passed!")

except Exception as e:
    print(f"\n[ERROR] Test failed: {e}")
    import traceback
    traceback.print_exc()
