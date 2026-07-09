"""
Test shared baseline functionality.
"""
import BatchProcess as bp
from pathlib import Path

def test_shared_from_control():
    """Test shared baseline from control files mode"""
    print("="*60)
    print("Test 1: Shared Baseline from Control Files")
    print("="*60)

    # Simulate file paths
    file_paths = [
        "./0806FS2/Ctrl1.csv",
        "./0806FS2/Ctrl2.csv",
        "./0806FS2/20s1.csv",
        "./0806FS2/20s2.csv"
    ]

    # Check which files exist
    existing_files = [fp for fp in file_paths if Path(fp).exists()]
    if not existing_files:
        print("No test files found. Skipping test.")
        return

    print(f"\nFound {len(existing_files)} files")

    # Create config
    cfg = bp.Config()
    cfg.encoding = "utf-16"
    cfg.skip_first_row = True
    cfg.roi_key = "ROI"
    cfg.time_col = "Axis [s]"
    cfg.baseline_mode = "shared_control"
    cfg.shared_baseline_start_frame = 10
    cfg.shared_baseline_end_frame = 60
    cfg.control_file_pattern = "Ctrl"

    # Identify control files
    print("\n1. Identifying control files...")
    control_files = bp.identify_control_files(existing_files, cfg.control_file_pattern)
    print(f"Control files found: {len(control_files)}")
    for cf in control_files:
        print(f"  - {Path(cf).name}")

    if not control_files:
        print("No control files found!")
        return False

    # Compute shared baseline
    print("\n2. Computing shared baseline...")
    baseline_dict = bp.compute_shared_baseline_from_files(control_files, cfg)

    if baseline_dict:
        print(f"\n[OK] Shared baseline computed for {len(baseline_dict)} ROIs")
        return True
    else:
        print("\n[FAIL] No baseline computed")
        return False


def test_shared_per_condition():
    """Test shared baseline per condition mode"""
    print("\n" + "="*60)
    print("Test 2: Shared Baseline per Condition")
    print("="*60)

    # Simulate file paths
    file_paths = [
        "./0806FS2/20s1.csv",
        "./0806FS2/20s2.csv",
        "./0806FS2/20s3.csv",
        "./0806FS2/10s1.csv",
        "./0806FS2/10s2.csv",
        "./0806FS2/5s1.csv",
        "./0806FS2/5s2.csv"
    ]

    # Check which files exist
    existing_files = [fp for fp in file_paths if Path(fp).exists()]
    if not existing_files:
        print("No test files found. Skipping test.")
        return

    print(f"\nFound {len(existing_files)} files")

    # Create config
    cfg = bp.Config()
    cfg.encoding = "utf-16"
    cfg.skip_first_row = True
    cfg.roi_key = "ROI"
    cfg.time_col = "Axis [s]"
    cfg.baseline_mode = "shared_per_condition"
    cfg.shared_baseline_start_frame = 10
    cfg.shared_baseline_end_frame = 60

    # Identify first files per condition
    print("\n1. Identifying first files per condition...")
    first_files_dict = bp.identify_first_files_per_condition(existing_files)

    print(f"\nFirst files found for {len(first_files_dict)} conditions:")
    for condition, filepath in first_files_dict.items():
        print(f"  {condition}: {Path(filepath).name}")

    if not first_files_dict:
        print("No first files found!")
        return False

    # Compute shared baseline
    print("\n2. Computing shared baseline...")
    first_files = list(first_files_dict.values())
    baseline_dict = bp.compute_shared_baseline_from_files(first_files, cfg)

    if baseline_dict:
        print(f"\n[OK] Shared baseline computed for {len(baseline_dict)} ROIs")
        return True
    else:
        print("\n[FAIL] No baseline computed")
        return False


def test_latency_zero_in_window():
    """Test that spikes inside stim window have latency = 0"""
    print("\n" + "="*60)
    print("Test 3: Spikes Inside Stim Window Have Latency 0")
    print("="*60)

    import numpy as np

    # Create test data
    spike_times = {
        "ROI.01": np.array([35.0, 60.5, 85.0, 110.5])  # 35.0 and 85.0 are inside windows
    }

    stim_windows = [(30, 50), (80, 100)]

    # Calculate latencies
    latencies_dict, stats_df, detailed_df = bp.calculate_spike_latencies(
        spike_times, stim_windows
    )

    print("\nDetailed latencies:")
    print(detailed_df)

    # Check if spikes inside windows have latency = 0
    inside_window_spikes = detailed_df[
        (detailed_df['spike_time_s'] >= detailed_df['stim_window_start_s']) &
        (detailed_df['spike_time_s'] <= detailed_df['stim_window_end_s'])
    ]

    all_zero = (inside_window_spikes['latency_s'] == 0.0).all()

    if all_zero and len(inside_window_spikes) > 0:
        print(f"\n[OK] {len(inside_window_spikes)} spikes inside windows have latency = 0")
        return True
    else:
        print(f"\n[FAIL] Spikes inside windows don't have latency = 0")
        return False


if __name__ == "__main__":
    results = []

    # Run tests
    try:
        results.append(("Shared from Control", test_shared_from_control()))
    except Exception as e:
        print(f"Error in test 1: {e}")
        results.append(("Shared from Control", False))

    try:
        results.append(("Shared per Condition", test_shared_per_condition()))
    except Exception as e:
        print(f"Error in test 2: {e}")
        results.append(("Shared per Condition", False))

    try:
        results.append(("Latency Zero in Window", test_latency_zero_in_window()))
    except Exception as e:
        print(f"Error in test 3: {e}")
        results.append(("Latency Zero in Window", False))

    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    for name, passed in results:
        status = "[PASSED]" if passed else "[FAILED]"
        print(f"{name:.<40} {status}")

    all_passed = all(result[1] for result in results)
    print("="*60)
    if all_passed:
        print("ALL TESTS PASSED!")
        exit(0)
    else:
        print("SOME TESTS FAILED")
        exit(1)
