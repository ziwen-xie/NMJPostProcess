"""
Test the timestamped output folder feature.
Processes a single file and verifies output is organized in timestamped folder.
"""
import BatchProcess as bp
from pathlib import Path
from datetime import datetime

def test_timestamped_output():
    print("=" * 60)
    print("Testing Timestamped Output Folder Feature")
    print("=" * 60)

    # Create config
    cfg = bp.Config()
    cfg.csv_path = "./0806N/20-1.csv"
    cfg.encoding = "utf-16"
    cfg.skip_first_row = True
    cfg.time_col = "Axis [s]"
    cfg.roi_key = "ROI"
    cfg.bg_source = "roi_column"
    cfg.bg_column_name = "ROI.01 []"
    cfg.spike_z_sigma = 5.0
    cfg.stim_preset = "20s"
    cfg.calculate_spike_latencies = True

    # Create timestamped output folder (simulating GUI behavior)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = Path("./0806N")
    output_dir = base_dir / f"analysis_output_{timestamp}"
    file_output_dir = output_dir / "20-1"
    file_output_dir.mkdir(parents=True, exist_ok=True)

    # Set output paths
    cfg.out_fig = str(file_output_dir / "deltaF_F_plot_all.png")
    cfg.out_csv = str(file_output_dir / "dff_table.csv")
    cfg.out_spike_csv = str(file_output_dir / "spike_summary.csv")
    cfg.out_spike_stats_csv = str(file_output_dir / "spike_baseline_stats.csv")
    cfg.out_spike_latency_stats_csv = str(file_output_dir / "spike_latency_stats.csv")
    cfg.out_spike_latency_detailed_csv = str(file_output_dir / "spike_latency_detailed.csv")
    cfg.out_fig_spiking_only = str(file_output_dir / "deltaF_F_spiking_only.png")

    print(f"\nOutput directory: {output_dir}")
    print(f"File output: {file_output_dir}")

    try:
        # Run analysis
        dff_table, fig_all, fig_spk = bp.run(cfg)

        print("\n" + "=" * 60)
        print("Analysis completed!")
        print("=" * 60)

        # Check created files
        expected_files = [
            "deltaF_F_plot_all.png",
            "dff_table.csv",
            "spike_summary.csv",
            "spike_baseline_stats.csv",
            "spike_latency_stats.csv",
            "spike_latency_detailed.csv"
        ]

        print(f"\nChecking files in: {file_output_dir}")
        all_found = True
        for fname in expected_files:
            fpath = file_output_dir / fname
            if fpath.exists():
                size = fpath.stat().st_size
                print(f"  [OK] {fname} ({size} bytes)")
            else:
                print(f"  [MISSING] {fname}")
                all_found = False

        if all_found:
            print(f"\n[SUCCESS] All files created in organized folder structure!")
            print(f"Output location: {file_output_dir}")
            return True
        else:
            print(f"\n[FAIL] Some files missing")
            return False

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_timestamped_output()
    exit(0 if success else 1)
