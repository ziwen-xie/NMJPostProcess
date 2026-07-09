"""
Test script for spike latency calculation functionality.
Tests with 0806N/20-1.csv as sample data.
"""
import BatchProcess as bp
import pandas as pd
from pathlib import Path

def test_spike_latency():
    print("=" * 60)
    print("Testing Spike Latency Calculation")
    print("=" * 60)

    # Create config for test
    cfg = bp.Config()
    cfg.csv_path = "./0806N/20-1.csv"
    cfg.encoding = "utf-16"
    cfg.skip_first_row = True
    cfg.time_col = "Axis [s]"
    cfg.roi_key = "ROI"

    # Background settings
    cfg.bg_source = "roi_column"
    cfg.bg_column_name = "ROI.01 []"

    # Spike detection settings
    cfg.baseline_index_start = 10
    cfg.baseline_index_end = 20
    cfg.spike_z_sigma = 5.0
    cfg.width_threshold_s = 0.50

    # Stimulation preset for 20s files
    cfg.stim_preset = "20s"
    cfg.stim_windows = [(30, 50), (80, 100), (130, 150)]

    # Enable spike latency calculation
    cfg.calculate_spike_latencies = True
    cfg.max_latency_window_s = None  # No maximum window

    # Output paths
    test_dir = Path("./test_latency_output")
    test_dir.mkdir(exist_ok=True)

    cfg.out_fig = str(test_dir / "deltaF_F_plot.png")
    cfg.out_csv = str(test_dir / "dff_table.csv")
    cfg.out_spike_csv = str(test_dir / "spike_summary.csv")
    cfg.out_spike_stats_csv = str(test_dir / "spike_baseline_stats.csv")
    cfg.out_spike_latency_stats_csv = str(test_dir / "spike_latency_stats.csv")
    cfg.out_spike_latency_detailed_csv = str(test_dir / "spike_latency_detailed.csv")

    print(f"\nProcessing: {cfg.csv_path}")
    print(f"Stim windows: {cfg.stim_windows}")
    print(f"Output directory: {test_dir}")

    try:
        # Run analysis
        dff_table, fig_all, fig_spk = bp.run(cfg)

        print("\n" + "=" * 60)
        print("Analysis completed successfully!")
        print("=" * 60)

        # Check if latency files were created
        latency_stats_path = Path(cfg.out_spike_latency_stats_csv)
        latency_detailed_path = Path(cfg.out_spike_latency_detailed_csv)

        if latency_stats_path.exists():
            print(f"\n[OK] Latency stats file created: {latency_stats_path}")
            stats_df = pd.read_csv(latency_stats_path)
            print(f"\n{stats_df.to_string()}")
            print(f"\nNumber of ROIs with latencies: {len(stats_df)}")
        else:
            print(f"\n[FAIL] Latency stats file NOT created")

        if latency_detailed_path.exists():
            print(f"\n[OK] Detailed latency file created: {latency_detailed_path}")
            detailed_df = pd.read_csv(latency_detailed_path)
            print(f"\nFirst 10 rows:")
            print(f"{detailed_df.head(10).to_string()}")
            print(f"\nTotal spike events with latencies: {len(detailed_df)}")
        else:
            print(f"\n[FAIL] Detailed latency file NOT created")

        print("\n" + "=" * 60)
        print("Test completed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n[ERROR] Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True

if __name__ == "__main__":
    success = test_spike_latency()
    exit(0 if success else 1)
