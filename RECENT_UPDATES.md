# Recent Updates - Spike Latency Feature Enhancements

## Date: 2025-02-05

### Issue 1: Organized Output with Timestamp ✅

**Problem:** When analyzing files in GUI, output data was scattered in the same folder as input files, making it hard to organize and track different analysis runs.

**Solution:** Implemented timestamped output folders
- Format: `analysis_output_YYYYMMDD_HHMMSS/`
- Each file gets its own subfolder: `analysis_output_YYYYMMDD_HHMMSS/filename/`
- All outputs organized in one place: plots, CSVs, latency data

**Example Structure:**
```
0806N/
├── 20-1.csv (original data)
├── 20-2.csv (original data)
└── analysis_output_20250205_203337/
    ├── 20-1/
    │   ├── deltaF_F_plot_all.png
    │   ├── deltaF_F_spiking_only.png
    │   ├── dff_table.csv
    │   ├── spike_summary.csv
    │   ├── spike_baseline_stats.csv
    │   ├── spike_latency_stats.csv
    │   └── spike_latency_detailed.csv
    └── 20-2/
        ├── deltaF_F_plot_all.png
        └── ... (all outputs)
```

**Benefits:**
- Easy to find all results from a single analysis session
- No more scattered output files mixed with input data
- Timestamp allows tracking different analysis runs
- Each file's outputs are organized in its own subfolder

---

### Issue 2: Real Spike Waveform Visualization ✅

**Problem:** Spike Review page showed only a simple timeline with vertical line for spike position, not the actual spike waveform.

**Solution:** Enhanced visualization with actual ΔF/F trace
- Loads both `spike_latency_detailed.csv` AND `dff_table.csv`
- Extracts actual ΔF/F values around spike time
- Plots real spike waveform overlaid on timeline
- Shows spike as orange point on the actual trace
- Displays stimulation window, latency arrow, and full trace context

**Updated Spike Review Workflow:**
1. Click "Load Latency Data"
2. **Select the analysis output folder** (not individual CSV)
   - e.g., `analysis_output_20250205_203337/20-1/`
3. Tool automatically loads:
   - `spike_latency_detailed.csv` (latency data)
   - `dff_table.csv` (ΔF/F traces)
4. View each spike with:
   - **Real ΔF/F waveform** in blue
   - **Spike point** marked in orange on the trace
   - Stimulation window shaded in red
   - Latency arrow with measurement
   - Time axis showing context before and after spike

**Visualization Features:**
- Time window: 10s before stim → 15s after spike
- Actual spike amplitude visible on ΔF/F trace
- Grid for easier reading of values
- Legend showing all elements
- Dark theme matching GUI style

---

## Code Changes

### Modified Files:

#### 1. GUI_3.py

**AnalysisWorker class** (lines 147-180):
- Added `output_dir` parameter to constructor
- Creates file-specific subfolder: `output_dir/filename/`
- Sets all output paths before running analysis
- Uses full `bp.run()` pipeline for complete outputs

**BatchAnalysisPage.run_analysis()** (lines 524-548):
- Creates timestamped output folder on START BATCH
- Format: `analysis_output_YYYYMMDD_HHMMSS`
- Passes output directory to all workers
- Prints output directory location to console

**SpikeLatencyReviewPage** (lines 583-850):
- `__init__`: Added `self.dff_data` to store ΔF/F DataFrame
- `load_latency_data()`:
  - Changed from file selector to **folder selector**
  - Loads both latency and ΔF/F CSV files
  - Validates both files exist
- `create_spike_item()`:
  - Extracts time window around spike from ΔF/F data
  - Plots actual trace with `ax.plot(time_plot, dff_plot)`
  - Marks spike point with orange circle
  - Shows 10s before stim to 15s after spike
  - Enhanced plot with grid, better labels, and styling

---

## Testing

### Test 1: Timestamped Output
**Script:** `test_timestamped_output.py`

**Result:**
```
Output location: 0806N\analysis_output_20250205_203337\20-1

Files created:
  [OK] deltaF_F_plot_all.png (1.4 MB)
  [OK] dff_table.csv (163 KB)
  [OK] spike_summary.csv (48 bytes)
  [OK] spike_baseline_stats.csv (1.4 KB)
  [OK] spike_latency_stats.csv (184 bytes)
  [OK] spike_latency_detailed.csv (109 bytes)

[SUCCESS] All files organized in timestamped folder!
```

### Test 2: Spike Waveform Visualization
**Manual test via GUI:**
1. Process files using GUI → creates timestamped folder
2. Go to Spike Review page
3. Load folder: `analysis_output_YYYYMMDD_HHMMSS/20-1/`
4. **Result:** Each spike shows actual ΔF/F trace with spike clearly visible

---

## Usage Examples

### Using GUI with New Features:

```python
# 1. Start GUI
python GUI_3.py

# 2. Go to Batch Process page
#    - Select your CSV files
#    - Enable "Calculate spike latencies" in Settings
#    - Click START BATCH

# → Output created in: <input_folder>/analysis_output_YYYYMMDD_HHMMSS/

# 3. Review spikes with real waveforms:
#    - Go to Spike Review page
#    - Click "Load Latency Data"
#    - Select: analysis_output_YYYYMMDD_HHMMSS/20-1/
#    - View actual spike waveforms
#    - Uncheck unwanted spikes
#    - Save filtered results
```

### Finding Your Results:

After running analysis, look for the timestamped folder:
```bash
# Your input files are here:
0806N/20-1.csv
0806N/20-2.csv

# Your results are here:
0806N/analysis_output_20250205_203337/
  ├── 20-1/  (all outputs for first file)
  └── 20-2/  (all outputs for second file)
```

---

## Benefits Summary

### Organized Output ✅
- ✓ All results in one timestamped folder
- ✓ Easy to compare different analysis runs
- ✓ No clutter in source data folders
- ✓ Clear file organization per analyzed file

### Enhanced Spike Review ✅
- ✓ See actual spike waveform, not just a line
- ✓ Verify spike amplitude and shape
- ✓ Better decision-making on spike inclusion
- ✓ Visual confirmation of spike quality
- ✓ Context of surrounding ΔF/F activity

### Combined Workflow ✅
1. Process files → organized timestamped output
2. Review spikes → load folder with both latency + ΔF/F
3. See real waveforms → make informed decisions
4. Save filtered → ready for analysis

---

## Version
- **GUI Version:** v2.7 (with enhancements)
- **Last Updated:** 2025-02-05
