"""
Test script for batch spike latency calculation and aggregation.
Tests with multiple files from 0806N folder.
"""
import BatchProcess as bp
import pandas as pd
from pathlib import Path

def test_batch_latency():
    print("=" * 60)
    print("Testing Batch Spike Latency Calculation")
    print("=" * 60)

    # Create base config
    base_cfg = bp.Config()
    base_cfg.encoding = "utf-16"
    base_cfg.skip_first_row = True
    base_cfg.time_col = "Axis [s]"
    base_cfg.roi_key = "ROI"
    base_cfg.bg_source = "roi_column"
    base_cfg.bg_column_name = "ROI.01 []"
    base_cfg.baseline_index_start = 10
    base_cfg.baseline_index_end = 20
    base_cfg.spike_z_sigma = 5.0
    base_cfg.width_threshold_s = 0.50
    base_cfg.stim_preset = "20s"
    base_cfg.stim_preset_infer_from_name = True

    # Enable spike latency calculation
    base_cfg.calculate_spike_latencies = True
    base_cfg.max_latency_window_s = None

    # Create batch config
    batch_cfg = bp.BatchConfig(
        input_folder="./0806N",
        output_root="./test_batch_latency_output",
        file_pattern="20-*.csv",  # Only process files starting with "20-"
        shared_config=base_cfg,
        verbose=True
    )

    print(f"\nInput folder: {batch_cfg.input_folder}")
    print(f"Output folder: {batch_cfg.output_root}")
    print(f"Pattern: {batch_cfg.file_pattern}")

    try:
        # Run batch processing
        print("\n" + "=" * 60)
        print("Running batch processing...")
        print("=" * 60)

        results_df = bp.run_batch(batch_cfg)

        print("\n" + "=" * 60)
        print("Batch processing completed!")
        print("=" * 60)
        print(f"\n{results_df.to_string()}")

        # Now test aggregation
        print("\n" + "=" * 60)
        print("Testing spike latency aggregation...")
        print("=" * 60)

        all_latencies_df = bp.collect_all_spike_latencies(batch_cfg)

        if not all_latencies_df.empty:
            print(f"\n[OK] Aggregated latencies from {len(all_latencies_df)} spike events")
            print(f"\nFirst 20 rows:")
            print(all_latencies_df.head(20).to_string())

            print(f"\nSummary by Parameter:")
            summary = all_latencies_df.groupby('Parameter')['latency_s'].agg(['count', 'mean', 'std'])
            print(summary.to_string())

            # Check if output file was created
            output_file = Path(batch_cfg.output_root) / "all_spike_latencies.csv"
            if output_file.exists():
                print(f"\n[OK] Aggregated file created: {output_file}")
            else:
                print(f"\n[FAIL] Aggregated file NOT created")
        else:
            print("\n[WARNING] No latencies were aggregated")

        print("\n" + "=" * 60)
        print("Batch test completed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n[ERROR] Error during batch processing: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True

if __name__ == "__main__":
    success = test_batch_latency()
    exit(0 if success else 1)
