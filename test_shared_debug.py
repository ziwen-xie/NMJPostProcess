"""
Debug test for shared baseline with both control and non-control files.
"""
import BatchProcess as bp
from pathlib import Path

print("="*60)
print("DEBUG: Shared Baseline with Control and Non-Control Files")
print("="*60)

# Files to test
ctrl_file = "./0806FS2/Ctrl1.csv"
test_file = "./0806FS2/20s1.csv"

if not Path(ctrl_file).exists() or not Path(test_file).exists():
    print("Test files not found!")
    exit(1)

# Create config
cfg = bp.Config()
cfg.encoding = "utf-16"
cfg.skip_first_row = True
cfg.roi_key = "ROI"
cfg.time_col = "Axis [s]"
cfg.bg_source = "roi_column"
cfg.bg_column_name = "ROI.01 []"
cfg.baseline_mode = "shared_control"
cfg.shared_baseline_start_frame = 10
cfg.shared_baseline_end_frame = 30
cfg.control_file_pattern = "Ctrl1"
cfg.stim_preset = "20s"
cfg.stim_windows = [(30, 50), (80, 100), (130, 150)]

print("\n1. Computing shared baseline from control file...")
baseline_dict = bp.compute_shared_baseline_from_files([ctrl_file], cfg)

print(f"\nShared baseline computed for {len(baseline_dict)} ROIs")
for roi, f0 in list(baseline_dict.items())[:5]:
    print(f"  {roi}: F0 = {f0:.3f}")

# Now test with control file itself
print("\n" + "="*60)
print("2. Processing CONTROL file (Ctrl1.csv) with shared baseline")
print("="*60)

cfg.csv_path = ctrl_file
cfg.shared_baseline_values = baseline_dict
cfg.out_fig = None
cfg.out_csv = None

try:
    print(f"\nProcessing {Path(ctrl_file).name}...")
    dff_ctrl, _, _ = bp.run(cfg)

    # Check control file results
    roi_cols = [c for c in dff_ctrl.columns if "ROI" in c and c != cfg.bg_column_name]
    if roi_cols:
        sample_roi = roi_cols[0]
        vals = dff_ctrl[sample_roi].values
        print(f"\nControl file - {sample_roi}:")
        print(f"  dF/F min: {vals.min():.3f}, max: {vals.max():.3f}, mean: {vals.mean():.3f}")

        if abs(vals.mean()) < 5.0:
            print("  [OK] Control file values look good")
        else:
            print("  [WARNING] Control file values unusual!")

except Exception as e:
    print(f"ERROR processing control file: {e}")
    import traceback
    traceback.print_exc()

# Now test with non-control file
print("\n" + "="*60)
print("3. Processing NON-CONTROL file (20s1.csv) with same shared baseline")
print("="*60)

cfg.csv_path = test_file
# Keep same shared_baseline_values

try:
    print(f"\nProcessing {Path(test_file).name}...")
    dff_test, _, _ = bp.run(cfg)

    # Check non-control file results
    roi_cols = [c for c in dff_test.columns if "ROI" in c and c != cfg.bg_column_name]
    if roi_cols:
        sample_roi = roi_cols[0]
        vals = dff_test[sample_roi].values
        print(f"\nNon-control file - {sample_roi}:")
        print(f"  dF/F min: {vals.min():.3f}, max: {vals.max():.3f}, mean: {vals.mean():.3f}")

        if abs(vals.mean()) < 5.0:
            print("  [OK] Non-control file values look good!")
            print("\n[SUCCESS] Shared baseline works for both control and non-control!")
        else:
            print("  [PROBLEM] Non-control file values unusual!")
            print("  This explains why output appears white.")

except Exception as e:
    print(f"ERROR processing non-control file: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("Test complete")
print("="*60)
