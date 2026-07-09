# Spike Latency Calculation Feature

## Overview
A comprehensive spike latency calculation system has been added to the NMJ Post-Process tool. This feature measures the time delay from the end of a stimulation window to the occurrence of a spike.

## What is Spike Latency?
**Spike Latency** = Time from END of stimulation window to spike event

For example:
- Stimulation window: [30, 50] seconds
- Spike occurs at: 83.787 seconds
- **Latency = 83.787 - 50 = 33.787 seconds**

The algorithm finds the most recent stimulation window that ends BEFORE each spike.

## Features Implemented

### 1. Core Calculation Engine
- **Function**: `calculate_spike_latencies()` in [BatchProcess.py](BatchProcess.py:605)
- Processes all detected spikes and calculates latencies
- Optional maximum latency window filter
- Handles edge cases (spikes before first window)

### 2. Output Files

#### Per-Experiment Files:
1. **spike_latency_stats.csv** - Summary statistics per ROI
   ```
   ROI, n_latencies, mean_latency_s, median_latency_s, std_latency_s, min_latency_s, max_latency_s
   ```

2. **spike_latency_detailed.csv** - Individual spike records
   ```
   ROI, spike_time_s, latency_s, stim_window_start_s, stim_window_end_s
   ```

#### Batch Processing:
3. **all_spike_latencies.csv** - Aggregated data across all experiments
   ```
   Parameter, Replicate, ROI, ROI_num, spike_time_s, latency_s, stim_window_start_s, stim_window_end_s
   ```

### 3. GUI Integration

#### Settings Page
New controls in "Advanced Spike Detection" section:
- ☑ **Calculate spike latencies** - Enable/disable the feature
- **Max Latency Window (s)** - Optional filter (0 = no limit)

#### New Spike Review Page
Access via sidebar: **"Spike Review"** button

Features:
- Load any spike_latency_detailed.csv file
- View each spike with:
  - ROI name, spike time, latency value
  - Timeline visualization showing stim window and spike
  - Checkbox to include/exclude from analysis
- Select All / Deselect All buttons
- Save filtered results to new CSV

## Usage

### Basic Usage (GUI)
1. Open GUI: `python GUI_3.py`
2. Go to **Settings** page
3. Check ☑ **"Calculate spike latencies"**
4. Return to **Batch Process** page
5. Select your CSV files
6. Click **START BATCH**
7. Results saved in output folders

### Batch Processing Example
```python
import BatchProcess as bp

# Configure
cfg = bp.Config()
cfg.csv_path = "./0806N/20-1.csv"
cfg.stim_preset = "20s"
cfg.calculate_spike_latencies = True
cfg.max_latency_window_s = None  # No limit

# Run
dff_table, fig_all, fig_spk = bp.run(cfg)
```

### Batch Aggregation
```python
import BatchProcess as bp

# Setup batch config
batch_cfg = bp.BatchConfig(
    input_folder="./0806N",
    output_root="./batch_output",
    file_pattern="*.csv"
)
batch_cfg.shared_config.calculate_spike_latencies = True

# Process all files
bp.run_batch(batch_cfg)

# Aggregate latencies
all_latencies = bp.collect_all_spike_latencies(batch_cfg)
# Saves to: batch_output/all_spike_latencies.csv
```

### Review and Filter Spikes
1. Open GUI: `python GUI_3.py`
2. Go to **Spike Review** page
3. Click **"Load Latency Data"**
4. Select a `spike_latency_detailed.csv` file
5. Review each spike with its visualization
6. Uncheck spikes you want to exclude
7. Click **"Save Filtered Data"**

## Test Scripts

### Single File Test
```bash
python test_spike_latency.py
```
Tests latency calculation with one file from 0806N folder.

### Batch Processing Test
```bash
python test_batch_latency.py
```
Processes all 20-*.csv files and tests aggregation.

## Testing Results

Tested with 0806N/20-*.csv files:
- ✓ 8 files processed successfully
- ✓ 8 spike events with latencies detected
- ✓ Mean latency: 24.65 ± 17.06 seconds
- ✓ Output files created correctly
- ✓ Batch aggregation working

Example results:
```
ROI.14 [] had spike at 83.787s after stim window [30, 50]s
→ Latency: 33.787s
```

## Configuration Options

### In Config class:
```python
calculate_spike_latencies: bool = False  # Enable calculation
max_latency_window_s: Optional[float] = None  # Max time after stim (None = unlimited)
out_spike_latency_stats_csv: str = "spike_latency_stats.csv"
out_spike_latency_detailed_csv: str = "spike_latency_detailed.csv"
```

### In GUI:
- Checkbox: "Calculate spike latencies"
- Spin box: "Max Latency Window (s)" with special value "None" when 0

## Implementation Details

### Files Modified
1. **BatchProcess.py**
   - Added `calculate_spike_latencies()` function (~line 605)
   - Added Config fields (~lines 75-79)
   - Integrated into `run()` (~line 1123)
   - Updated `process_single_file()` (~line 1247)
   - Added `collect_all_spike_latencies()` (~line 1511)

2. **GUI_3.py**
   - Added controls in SettingsPage (~line 290)
   - Updated `get_config()` (~line 507)
   - Added SpikeLatencyReviewPage class (~line 579)
   - Added navigation button and page switching
   - Updated version to v2.7

### Algorithm
For each spike:
1. Find all stim windows where `window_end < spike_time`
2. Select window with maximum end time (most recent)
3. Calculate `latency = spike_time - window_end`
4. Apply optional max_latency_window filter
5. Aggregate statistics per ROI

### Edge Cases Handled
- Empty CSV files (no spikes) - skipped gracefully
- Spikes before first stimulation window - excluded
- Missing or invalid data - try-except blocks
- Windows console encoding issues - removed emoji characters

## Future Enhancements

Possible additions:
- Load original ΔF/F data in Spike Review page for full trace visualization
- Export filtered results back to batch processing
- Statistical analysis plots (histograms, box plots of latencies)
- Compare latencies across experimental conditions

## Recent Enhancements (2025-02-05)

### 1. Organized Timestamped Output Folders
When using the GUI, all analysis outputs are now saved to organized timestamped folders:
```
analysis_output_YYYYMMDD_HHMMSS/
  ├── file1/
  │   ├── deltaF_F_plot_all.png
  │   ├── dff_table.csv
  │   ├── spike_latency_stats.csv
  │   └── spike_latency_detailed.csv
  └── file2/
      └── ...
```

**Benefits:**
- No more scattered output files
- Easy to track different analysis sessions
- All results organized in one location
- Each file gets its own subfolder

### 2. Real Spike Waveform Visualization
The Spike Review page now shows:
- **Actual ΔF/F trace** around each spike (not just a timeline)
- **Spike point** marked on the real waveform
- Full context with stimulation window and latency measurement

**New Workflow:**
1. Go to Spike Review page
2. Click "Load Latency Data"
3. **Select the analysis output folder** (contains both latency + ΔF/F files)
4. View spikes with real waveforms
5. Make informed decisions based on spike shape and amplitude

See [RECENT_UPDATES.md](RECENT_UPDATES.md) for detailed information.

## Version History
- **v2.7** (2025-02-05) - Enhanced with timestamped output and real spike waveform visualization
- **v2.7** (2025-02) - Added spike latency calculation feature
- **v2.6** - Previous version
