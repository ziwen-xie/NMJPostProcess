"""
Test spike latency calculation mimicking GUI behavior.
This test simulates exactly what the GUI does when processing files.
"""
import BatchProcess as bp
from pathlib import Path
from datetime import datetime
import copy

def test_gui_spike_latency():
    print("="*60)
    print("Testing Spike Latency - Mimicking GUI Behavior")
    print("="*60)

    # Create config exactly like GUI does (line 484-522 in GUI_3.py)
    cfg = bp.Config()

    # Settings from Quick Config (Batch Process page)
    cfg.stim_preset = "20s"
    cfg.stim_preset_infer_from_name = True
    cfg.spike_z_sigma = 5.0
    cfg.bg_column_name = "ROI.01 []"
    cfg.use_auto_ylim = False
    cfg.ylim_max = 0.3
    cfg.ylim_min = 0.0

    # Settings from Settings page
    cfg.roi_key = "ROI"
    cfg.time_col = "Axis [s]"
    cfg.skip_first_row = True
    cfg.encoding = "utf-16"
    cfg.bg_source = "roi_column"

    cfg.baseline_index_start = 0
    cfg.baseline_index_end = 50
    cfg.baseline_window_half_s = 5.0
    cfg.baseline_percentile = 10.0

    cfg.min_spike_distance_s = None
    cfg.width_threshold_s = 0.5
    cfg.exclude_spikes_in_stim = False

    # THE CRITICAL SETTING - Enable spike latency calculation
    cfg.calculate_spike_latencies = True
    cfg.max_latency_window_s = None

    # Stim windows
    presets = {
        "20s": [(30, 50), (80, 100), (130, 150)],
        "10s": [(30, 40), (70, 80), (110, 120)],
        "5s": [(30, 35), (65, 70), (100, 105)]
    }
    if cfg.stim_preset in presets:
        cfg.stim_windows = presets[cfg.stim_preset]

    # Test file
    test_file = Path("./0806FS2/20s1.csv")
    if not test_file.exists():
        print(f"ERROR: Test file not found: {test_file}")
        return False

    print(f"\nTest file: {test_file}")
    print(f"Spike latency enabled: {cfg.calculate_spike_latencies}")
    print(f"Stim windows: {cfg.stim_windows}")

    # Create output directory (mimicking GUI lines 534-541)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = test_file.parent
    output_dir = base_dir / f"analysis_output_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Output directory: {output_dir}")

    # Process file (mimicking AnalysisWorker.run() lines 155-193)
    try:
        # Copy config (like line 157)
        local_cfg = copy.copy(cfg)
        local_cfg.csv_path = str(test_file)

        # Apply inferred stim preset (like lines 160-161)
        if local_cfg.stim_preset_infer_from_name:
            bp.apply_inferred_stim_preset(local_cfg, name_hint=test_file.name)

        # Create file-specific output folder (like lines 163-165)
        file_output_dir = output_dir / test_file.stem
        file_output_dir.mkdir(parents=True, exist_ok=True)

        # Set all output paths (like lines 167-174)
        local_cfg.out_fig = str(file_output_dir / "deltaF_F_plot_all.png")
        local_cfg.out_csv = str(file_output_dir / "dff_table.csv")
        local_cfg.out_spike_csv = str(file_output_dir / "spike_summary.csv")
        local_cfg.out_spike_stats_csv = str(file_output_dir / "spike_baseline_stats.csv")
        local_cfg.out_spike_latency_stats_csv = str(file_output_dir / "spike_latency_stats.csv")
        local_cfg.out_spike_latency_detailed_csv = str(file_output_dir / "spike_latency_detailed.csv")
        local_cfg.out_fig_spiking_only = str(file_output_dir / "deltaF_F_spiking_only.png")

        # Print debug info (like lines 177-181)
        print(f"\n{'='*60}")
        print(f"Processing: {test_file.name}")
        print(f"Spike latency calculation: {'ENABLED' if local_cfg.calculate_spike_latencies else 'DISABLED'}")
        if not local_cfg.calculate_spike_latencies:
            print("WARNING: Spike latency is DISABLED - no latency files will be created!")
            print("To enable: Go to Settings -> Check 'Calculate spike latencies'")
        print(f"Output folder: {file_output_dir}")
        print(f"Stimulation windows: {local_cfg.stim_windows}")
        print(f"{'='*60}\n")

        # Run analysis (like line 183)
        print("Calling bp.run()...")
        dff_table, fig_all, fig_spk = bp.run(local_cfg)
        print("bp.run() completed successfully")

        # Verify latency files were created (like lines 185-192)
        if local_cfg.calculate_spike_latencies:
            latency_file = file_output_dir / "spike_latency_detailed.csv"
            latency_stats_file = file_output_dir / "spike_latency_stats.csv"

            if latency_file.exists():
                print(f"[OK] Spike latency file created: {latency_file}")
                import pandas as pd
                df = pd.read_csv(latency_file)
                print(f"     Contains {len(df)} spike events")
                print(f"\nFirst few rows:")
                print(df.head())
            else:
                print(f"[WARNING] Spike latency file NOT created (no valid spikes found)")

            if latency_stats_file.exists():
                print(f"\n[OK] Spike latency stats file created: {latency_stats_file}")
                df_stats = pd.read_csv(latency_stats_file)
                print(f"     Stats for {len(df_stats)} ROIs")
                print(f"\nStats:")
                print(df_stats)

            return latency_file.exists() and latency_stats_file.exists()
        else:
            print("[ERROR] Spike latency calculation was disabled!")
            return False

    except Exception as e:
        print(f"\n[ERROR] Exception occurred: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_gui_spike_latency()
    if success:
        print("\n" + "="*60)
        print("TEST PASSED: Spike latency files created successfully!")
        print("="*60)
        exit(0)
    else:
        print("\n" + "="*60)
        print("TEST FAILED: Spike latency files NOT created!")
        print("="*60)
        exit(1)
