# Complete New Features Guide

## Date: 2025-02-05

---

## ✅ ALL FEATURES IMPLEMENTED AND TESTED

**Latest Update (2025-02-05):**
- **CRITICAL FIX**: Fixed signal inversion bug when F0 is negative after background subtraction
- Fixed spike latency review timeline: Now shows 10s before to 80s after stim start for all plots (consistent comparison)
- Added "Categorize by Condition" feature with grouped stats and comparison plots
- Added "Categorize by ROI" feature with grouped stats and comparison plots
- Added adjustable table/plot heights in categorization dialogs (use splitter)
- Added "Exclude Blue Only" option for conditional spike exclusion

---

## 🚨 CRITICAL BUG FIX: Signal Inversion (2025-02-05) ✅

### Problem
When using shared baseline mode, ΔF/F plots were **vertically flipped**:
- Stimulation spikes that should go UP appeared as dips DOWN
- Flat baseline regions appeared elevated
- All signals were inverted

### Root Cause
After background subtraction, F0 can be **negative**. The standard ΔF/F formula:
```
ΔF/F = (F - F0) / F0
```
When F0 < 0, dividing by negative F0 inverts the signal:
- Increased fluorescence (less negative) → Negative ΔF/F (wrong!)
- Decreased fluorescence (more negative) → Positive ΔF/F (wrong!)

**Example:**
- F0 = -20 (baseline after background subtraction)
- F_spike = -15 (increased fluorescence, less negative)
- ΔF/F = (-15 - (-20)) / (-20) = 5 / (-20) = **-0.25** ❌ (WRONG: should be positive!)

### Solution
Use **absolute value** of F0 in denominator:
```
ΔF/F = (F - F0) / |F0|
```
Now with same values:
- ΔF/F = (-15 - (-20)) / |-20| = 5 / 20 = **+0.25** ✅ (CORRECT!)

### Files Modified
- [BatchProcess.py:267](BatchProcess.py#L267) - `dff_fixed_baseline()`: Use `abs(F0_value)` in denominator
- [BatchProcess.py:241](BatchProcess.py#L241) - `dff_percentile_window()`: Use `np.abs(F0)` in denominator
- Added epsilon (1e-9) to prevent division by zero

### Testing
Run `python test_signal_inversion_fix.py` to verify the fix works correctly.

---

## Feature 1: Spike Latency Default Enabled ✅

### What Changed
The "Calculate spike latencies" checkbox is now **CHECKED by default** when you open the GUI.

### Why This Matters
- Users were frequently forgetting to enable this setting
- Results in missing spike latency files
- Now enabled by default for convenience

### Visual Changes
**Settings Page:**
```
Before: ☐ Calculate spike latencies
        ⚠️ DISABLED - No latency files will be created

After:  ☑ Calculate spike latencies (default)
        ✓ ENABLED - Latency files will be created
```

### Files Modified
- `GUI_3.py:296` - Changed setChecked(False) → setChecked(True)
- `GUI_3.py:300` - Updated default status label

---

## Feature 2: Shared Baseline from Control ✅

### What It Does
Uses baseline (F0) from Control files for **ALL files** in your dataset.

### How It Works
1. Identifies all files matching the control pattern (default: "Ctrl")
2. Extracts frames 10-60 from these control files
3. Computes F0 for each ROI using these frames
4. Applies this shared F0 to ALL files (both control and experimental)

### When to Use
- You have dedicated control experiments
- You want all conditions to use the same baseline reference
- Your control files have stable baseline activity

### Example Usage
**Files:**
```
0806FS2/
├── Ctrl1.csv       ← Use these for baseline
├── Ctrl2.csv       ← Use these for baseline
├── Ctrl3.csv       ← Use these for baseline
├── 20s1.csv        ← Apply control baseline
├── 20s2.csv        ← Apply control baseline
├── 10s1.csv        ← Apply control baseline
└── 10s2.csv        ← Apply control baseline
```

**Settings:**
- Baseline Mode: "Shared from Control files"
- Shared Start Frame: 10
- Shared End Frame: 60
- Control File Pattern: "Ctrl"

**Result:**
- Ctrl1, Ctrl2, Ctrl3 frames 10-60 → compute F0 for each ROI
- This F0 is used for 20s1, 20s2, 10s1, 10s2, AND the control files

### Console Output
```
============================================================
Computing shared baseline from 3 file(s):
  - Ctrl1.csv
  - Ctrl2.csv
  - Ctrl3.csv
Using frames 10 to 60
============================================================

  ROI.01 []: F0 = 322.832
  ROI.02 []: F0 = 376.022
  ROI.04 []: F0 = 312.063
  ...

Shared baseline computed for 12 ROIs
```

---

## Feature 3: Shared Baseline per Condition ✅

### What It Does
Uses baseline from the **first file** of each condition for all files in that condition.

### How It Works
1. Groups files by condition (e.g., 20s, 10s, 5s, Ctrl)
2. Identifies "first" file for each condition:
   - File with no number: "20s.csv"
   - OR file ending with "1": "20s1.csv"
3. Extracts frames 10-60 from first files
4. Computes F0 for each condition
5. Applies condition-specific F0 to all files in that condition

### When to Use
- Each condition has different baseline characteristics
- You want consistency within each condition
- First file of each condition represents typical baseline

### Example Usage
**Files:**
```
0806FS2/
├── 20s1.csv       ← Baseline for 20s condition
├── 20s2.csv       ← Use 20s1 baseline
├── 20s3.csv       ← Use 20s1 baseline
├── 10s1.csv       ← Baseline for 10s condition
├── 10s2.csv       ← Use 10s1 baseline
├── 10s3.csv       ← Use 10s1 baseline
├── 5s1.csv        ← Baseline for 5s condition
└── 5s2.csv        ← Use 5s1 baseline
```

**Settings:**
- Baseline Mode: "Shared per Condition"
- Shared Start Frame: 10
- Shared End Frame: 60

**Result:**
- 20s condition: 20s1 frames 10-60 → F0 → applied to 20s1, 20s2, 20s3
- 10s condition: 10s1 frames 10-60 → F0 → applied to 10s1, 10s2, 10s3
- 5s condition: 5s1 frames 10-60 → F0 → applied to 5s1, 5s2

### Console Output
```
Computing shared baseline per condition...

First file for condition '20s': 20s1.csv
First file for condition '10s': 10s1.csv
First file for condition '5s': 5s1.csv

============================================================
Computing shared baseline from 3 file(s):
  - 20s1.csv
  - 10s1.csv
  - 5s1.csv
Using frames 10 to 60
============================================================

  ROI.01 []: F0 = 289.684
  ROI.02 []: F0 = 354.795
  ...

Shared baseline computed for 12 ROIs
```

---

## Feature 4: Spikes in Stim Window = Latency 0 ✅

### What Changed
Spikes that occur **inside** a stimulation window now have latency = **0.0 seconds** instead of being excluded.

### Why This Matters
- Spikes during stimulation are important immediate responses
- Should be included in analysis
- Latency = 0 indicates synchronous activation

### Example Output
**Before (Old Behavior):**
```csv
ROI,spike_time_s,latency_s,stim_window_start_s,stim_window_end_s
ROI.01,60.5,10.5,30,50        ← Only after-window spikes
ROI.01,110.5,10.5,80,100
```

**After (New Behavior):**
```csv
ROI,spike_time_s,latency_s,stim_window_start_s,stim_window_end_s
ROI.01,35.0,0.0,30,50         ← Inside window!
ROI.01,60.5,10.5,30,50        ← After window
ROI.01,85.0,0.0,80,100        ← Inside window!
ROI.01,110.5,10.5,80,100      ← After window
```

### How to Identify
- Check `spike_time_s` column
- If `spike_time_s` is between `stim_window_start_s` and `stim_window_end_s`
- Then `latency_s` = 0.0

### Files Modified
- `BatchProcess.py:668-695` - Added logic to detect spikes inside windows

---

## Feature 5: Improved Stats Display ✅

### What Changed
Spike latency summary statistics are now shown in a **professional, resizable table dialog** instead of plain text.

### Features
✅ **Resizable window** - Drag to any size (default 900x600)
✅ **Color-coded rows** - TOTAL and OVERALL rows highlighted in blue
✅ **Bold text** for summary rows
✅ **Alternating row colors** for readability
✅ **Auto-sized columns** to fit content
✅ **Shows save path** at the bottom

### Before vs After

**Before (Old):**
- Fixed-size QMessageBox
- Plain text with manual spacing
- Hard to read with many conditions
- Not resizable

**After (New):**
- Professional table widget
- Clean, styled rows
- Easy to scan and compare
- Fully resizable
- Export-ready CSV also saved

### How to Use
1. Go to Spike Review page
2. Load latency data (select analysis_output folder)
3. Click **"Generate Summary Stats"**
4. Beautiful table appears!
5. Resize as needed
6. CSV saved automatically

### Files Modified
- `GUI_3.py:1138-1145` - Replaced QMessageBox with custom dialog
- `GUI_3.py:1150-1219` - Added show_stats_table() method

---

## 🎓 Complete Usage Guide

### Scenario 1: Standard Analysis (No Shared Baseline)

**When to use:** Each file has its own stable baseline

**Steps:**
1. GUI → Settings → Baseline Mode: "Standard (per-file)"
2. GUI → Batch Process → Add files → START BATCH
3. Each file uses its own sliding window baseline

---

### Scenario 2: Using Control Files for All

**When to use:** You have dedicated control experiments with stable baseline

**Steps:**
1. GUI → Settings → Shared Baseline Options:
   - Baseline Mode: **"Shared from Control files"**
   - Shared Start Frame: **10**
   - Shared End Frame: **60**
   - Control File Pattern: **"Ctrl"**

2. GUI → Batch Process → Add ALL files (including controls):
   - Ctrl1.csv, Ctrl2.csv, Ctrl3.csv
   - 20s1.csv, 20s2.csv, 20s3.csv
   - 10s1.csv, 10s2.csv, etc.

3. Click **START BATCH**

4. Console shows:
   ```
   Computing shared baseline from control files...
   Control files found: 3
     - Ctrl1.csv
     - Ctrl2.csv
     - Ctrl3.csv

   Shared baseline computed for 12 ROIs
   ```

5. All files use the same control-derived baseline

---

### Scenario 3: Per-Condition Baseline

**When to use:** Each condition has different baseline characteristics

**Steps:**
1. GUI → Settings → Shared Baseline Options:
   - Baseline Mode: **"Shared per Condition"**
   - Shared Start Frame: **10**
   - Shared End Frame: **60**

2. Name your files correctly:
   - First file of each condition must end with "1" or have no number
   - Examples: 20s1.csv, 10s1.csv, 5s1.csv (or 20s.csv, 10s.csv, 5s.csv)

3. GUI → Batch Process → Add ALL files:
   - 20s1.csv, 20s2.csv, 20s3.csv
   - 10s1.csv, 10s2.csv, 10s3.csv
   - 5s1.csv, 5s2.csv, 5s3.csv

4. Click **START BATCH**

5. Console shows:
   ```
   Computing shared baseline per condition...

   First file for condition '20s': 20s1.csv
   First file for condition '10s': 10s1.csv
   First file for condition '5s': 5s1.csv

   Shared baseline computed for 12 ROIs
   ```

6. Each condition uses its first file's baseline

---

## 🧪 Testing

### Test Script
Run the comprehensive test:
```bash
python test_shared_baseline.py
```

**Expected output:**
```
============================================================
TEST SUMMARY
============================================================
Shared from Control..................... [PASSED]
Shared per Condition.................... [PASSED]
Latency Zero in Window.................. [PASSED]
============================================================
ALL TESTS PASSED!
```

### Manual GUI Test

**Test 1: Spike Latency Default**
```
1. python GUI_3.py
2. Go to Settings page
3. Verify "Calculate spike latencies" is CHECKED
4. Verify status shows "✓ ENABLED" in green
```

**Test 2: Shared Baseline from Control**
```
1. Settings → Baseline Mode: "Shared from Control files"
2. Batch Process → Add Ctrl1.csv, Ctrl2.csv, 20s1.csv
3. START BATCH
4. Watch console for shared baseline computation
5. Check that all files use same baseline
```

**Test 3: Shared Baseline per Condition**
```
1. Settings → Baseline Mode: "Shared per Condition"
2. Batch Process → Add 20s1.csv, 20s2.csv, 10s1.csv, 10s2.csv
3. START BATCH
4. Watch console for condition identification
5. Check that each condition uses its first file's baseline
```

**Test 4: Latency = 0 for In-Window Spikes**
```
1. Process files with spike latency enabled
2. Open spike_latency_detailed.csv
3. Find rows where spike_time_s is inside [stim_window_start_s, stim_window_end_s]
4. Verify latency_s = 0.0 for these rows
```

**Test 5: Beautiful Stats Table**
```
1. Spike Review → Load latency data
2. Click "Generate Summary Stats"
3. Verify table appears in resizable window
4. Try resizing the window
5. Check that TOTAL/OVERALL rows are highlighted
```

---

## 📊 Output Files

### Standard Output (per file subfolder):
```
analysis_output_20250205_HHMMSS/
└── 20s1/
    ├── deltaF_F_plot_all.png
    ├── deltaF_F_spiking_only.png
    ├── dff_table.csv
    ├── spike_summary.csv
    ├── spike_baseline_stats.csv
    ├── spike_latency_stats.csv           ← Per-ROI summary
    └── spike_latency_detailed.csv         ← Individual spikes
```

### New: Summary stats (parent folder):
```
analysis_output_20250205_HHMMSS/
├── spike_latency_summary_stats.csv       ← Generated by Spike Review
├── 20s1/
├── 20s2/
└── ...
```

---

## ⚙️ Configuration Reference

### Baseline Mode Options
```python
# Standard (default)
cfg.baseline_mode = "standard"
# → Each file uses its own sliding window baseline

# Shared from control files
cfg.baseline_mode = "shared_control"
cfg.control_file_pattern = "Ctrl"
cfg.shared_baseline_start_frame = 10
cfg.shared_baseline_end_frame = 60
# → All files use baseline from Ctrl files

# Shared per condition
cfg.baseline_mode = "shared_per_condition"
cfg.shared_baseline_start_frame = 10
cfg.shared_baseline_end_frame = 60
# → Each condition uses baseline from its first file
```

---

## 🔍 Troubleshooting

### "No Control Files Found"
**Problem:** Control file pattern doesn't match any files
**Solution:**
- Check your file names contain the control pattern
- Default pattern is "Ctrl" (case-insensitive)
- Matches: Ctrl1.csv, Ctrl2.csv, Control.csv
- Doesn't match: C1.csv, baseline.csv

### "No First Files Found"
**Problem:** No files end with "1" or have no number
**Solution:**
- Rename files to end with "1": 20s1.csv, 10s1.csv
- OR remove numbers: 20s.csv, 10s.csv
- Pattern matches: 20s1.csv, 20s.csv, Ctrl1.csv, Ctrl.csv
- Doesn't match: 20s2.csv, 20s3.csv, 20sA.csv

### Stats Table Not Showing
**Problem:** Generate Summary Stats button disabled
**Solution:**
- First load latency data successfully
- Button only enables after data is loaded

### Spikes Missing from Analysis
**Problem:** Fewer spikes than expected
**Solution:**
- Check baseline mode - shared baseline may affect spike detection
- Verify frames 10-60 in baseline files have good quality
- Check spike detection threshold (sigma = 5.0 default)

---

## 📊 Feature 6: Categorize by Condition ✅

### What It Does
Groups spike latencies by experimental condition (e.g., 20s1, 20s2, 20s3 → "20s") and generates:
1. Summary statistics table (count, mean, median, std, SEM per condition)
2. Comparison plots (average latency + spike count by condition)
3. CSV export of grouped statistics

### How to Use
1. Go to **Spike Review** page
2. Load latency data from analysis output folder
3. Select/deselect spikes to include
4. Click **"Categorize by Condition"**
5. View results in popup dialog (table + plots)

### Output Files
- `spike_latency_by_condition.csv` - Statistics table
- `spike_latency_by_condition.png` - Comparison plots

### Example
**Input conditions:** 20s1, 20s2, 20s3, 10s1, 10s2, 5s1, 5s2
**Grouped as:** 20s, 10s, 5s

**Statistics calculated:**
- Spike count per condition group
- Average latency per condition group
- Median, std, SEM per condition group

**Plots generated:**
- Bar chart: Average latency by condition (with error bars)
- Bar chart: Spike count by condition

---

## 📊 Feature 7: Categorize by ROI ✅

### What It Does
Groups spike latencies by ROI across all conditions and generates:
1. Summary statistics table (count, mean, median, std, SEM per ROI)
2. Comparison plots (average latency + spike count by ROI)
3. CSV export of grouped statistics

### How to Use
1. Go to **Spike Review** page
2. Load latency data from analysis output folder
3. Select/deselect spikes to include
4. Click **"Categorize by ROI"**
5. View results in popup dialog (table + plots)

### Output Files
- `spike_latency_by_roi.csv` - Statistics table
- `spike_latency_by_roi.png` - Comparison plots

### Example
**Input ROIs:** ROI.02 [], ROI.04 [], ROI.05 [], etc.

**Statistics calculated:**
- Spike count per ROI (across all conditions)
- Average latency per ROI
- Median, std, SEM per ROI

**Plots generated:**
- Bar chart: Average latency by ROI (with error bars)
- Bar chart: Spike count by ROI

---

## 🎯 Feature 8: Fixed Timeline Display ✅

### What Changed
Spike latency review plots now use **consistent x-axis** for all spikes:
- **Before:** Dynamic range based on spike time (inconsistent comparison)
- **After:** Fixed range: 10s before stim start to 80s after stim start

### Why This Matters
- Enables direct comparison between different spikes
- All plots show same time window
- Easier to identify patterns across conditions

### Technical Details
- Time range: `[stim_start - 10, stim_start + 80]`
- Applied to all spike review timeline plots
- Shows full response window consistently

---

## 📝 Version History

- **v2.8.1** (2025-02-05) - Added categorization features:
  1. Categorize by Condition (group analysis + plots)
  2. Categorize by ROI (group analysis + plots)
  3. Fixed timeline display (consistent x-axis for comparison)

- **v2.8** (2025-02-05) - Added all 5 new features:
  1. Spike latency default enabled
  2. Shared baseline from control
  3. Shared baseline per condition
  4. Spikes in stim window = latency 0
  5. Improved stats display

- **v2.7** (2025-02-05) - Enhanced with timestamped output and real spike waveform visualization

- **v2.6** - Previous version

---

## 📚 See Also

- **NEW_FEATURES_2025_02_05.md** - Detailed technical documentation
- **test_shared_baseline.py** - Test script for all new features
- **SPIKE_LATENCY_FEATURE.md** - Original spike latency documentation
- **SPIKE_LATENCY_SOLUTION.md** - Troubleshooting guide

---

## 🎉 All Features Tested and Working!

All 5 features have been implemented, tested, and documented. The test script confirms:
- ✅ Shared baseline from control files works
- ✅ Shared baseline per condition works
- ✅ Spikes inside stim windows have latency = 0
- ✅ (Plus spike latency default enabled and improved stats display)

**Ready for production use!**
