# New Features - 2025-02-05

## Summary of 5 New Features

---

## ✅ Feature 1: Spike Latency Default Enabled

### Change
The "Calculate spike latencies" checkbox is now **CHECKED by default**.

### Why
Users often forgot to enable this setting, leading to missing spike latency files. Now it's enabled by default for convenience.

### Location
- [GUI_3.py:296](GUI_3.py#L296) - Changed `setChecked(False)` to `setChecked(True)`
- [GUI_3.py:300](GUI_3.py#L300) - Updated initial status label to show "ENABLED"

### User Experience
```
Before: ☐ Calculate spike latencies
        ⚠️ DISABLED - No latency files will be created

After:  ☑ Calculate spike latencies (default)
        ✓ ENABLED - Latency files will be created
```

---

## ✅ Feature 4: Spikes Inside Stim Window Have Latency 0

### Change
When a spike occurs INSIDE a stimulation window, its latency is now set to **0.0 seconds** instead of being skipped.

### Why
Spikes that occur during stimulation are important events and should be included in the analysis with latency = 0 to indicate immediate response.

### Implementation
Modified `calculate_spike_latencies()` in [BatchProcess.py:668-695](BatchProcess.py#L668-L695):

```python
# Check if spike is INSIDE any stimulation window
for window_start, window_end in sorted_windows:
    if window_start <= spike_time <= window_end:
        # Spike is inside this stim window - latency is 0
        latency = 0.0
        inside_window = True
        break

if not inside_window:
    # Calculate normal latency from end of preceding window
    ...
```

### Output Example
```csv
ROI,spike_time_s,latency_s,stim_window_start_s,stim_window_end_s
ROI.09 [],35.5,0.0,30,50          ← Spike inside window
ROI.09 [],60.3,10.3,30,50          ← Spike after window
```

---

## ✅ Feature 5: Improved Stats Display

### Change
Spike latency summary statistics are now displayed in a **resizable table widget** with color-coded rows and professional formatting.

### Before (Old)
- Plain text in QMessageBox detailed text
- Fixed size, not resizable
- Hard to read with many conditions

### After (New)
- Resizable QDialog window (900x600 default)
- QTableWidget with styled rows
- Alternating row colors for readability
- Bold highlighting for TOTAL and OVERALL rows
- Auto-sized columns
- Professional table styling

### Implementation
Added `show_stats_table()` method in [GUI_3.py:1150-1219](GUI_3.py#L1150-L1219):

```python
def show_stats_table(self, stats_df, save_path, n_conditions):
    """Display statistics in a resizable table dialog with nice formatting"""
    # Create resizable dialog
    dialog = QDialog(self)
    dialog.resize(900, 600)  # User can resize as needed

    # Create styled table
    table = QTableWidget()
    # ... styling and data population ...
```

### Features
- ✅ Resizable window - drag to desired size
- ✅ Color-coded rows (TOTAL/OVERALL highlighted)
- ✅ Professional table styling with grid lines
- ✅ Alternating row colors for easy reading
- ✅ Auto-sized columns to fit content
- ✅ Shows file path where CSV was saved

---

## 🔄 Features 2 & 3: Shared Baseline Options (IN PROGRESS)

### Overview
Two new baseline calculation modes that share baseline values across files instead of calculating per-file.

### Feature 2: Shared Baseline from Control

**Mode:** "Shared from Control files"

**How it works:**
1. Identifies all files matching the control pattern (default: "Ctrl")
2. Extracts frames 10-60 from control files
3. Calculates baseline (F0) from these frames
4. Uses this shared baseline for ALL files (including non-control)
5. **Does NOT exclude first 30s** from spike detection in non-control files

**Use case:** When you have dedicated control experiments and want to use their baseline for all conditions.

**Example:**
```
Files:
- Ctrl1.csv, Ctrl2.csv  ← Use these for baseline
- 20s1.csv, 20s2.csv    ← Apply control baseline
- 10s1.csv, 10s2.csv    ← Apply control baseline
```

### Feature 3: Shared Baseline per Condition

**Mode:** "Shared per Condition"

**How it works:**
1. Groups files by condition (e.g., 20s, 10s, 5s, Ctrl)
2. Identifies the FIRST file of each condition:
   - Files with no number suffix (e.g., "20s.csv")
   - OR files ending with "1" (e.g., "20s1.csv")
3. Extracts frames 10-60 from first files
4. Uses this baseline for ALL files in that condition
5. **Does NOT exclude first 30s** from spike detection in subsequent files

**Use case:** When each condition has its own baseline pattern, and you want consistency within each condition.

**Example:**
```
Condition "20s":
- 20s1.csv  ← Use as baseline for 20s condition
- 20s2.csv  ← Apply 20s1 baseline
- 20s3.csv  ← Apply 20s1 baseline

Condition "10s":
- 10s1.csv  ← Use as baseline for 10s condition
- 10s2.csv  ← Apply 10s1 baseline
- 10s3.csv  ← Apply 10s1 baseline
```

### GUI Controls

**Location:** Settings page → "Shared Baseline Options" group

**Controls:**
1. **Baseline Mode** (dropdown):
   - Standard (per-file) - Default behavior
   - Shared from Control files - Use Ctrl files' baseline
   - Shared per Condition - Use first file of each condition

2. **Shared Start Frame** (spin box):
   - Default: 10
   - First frame to use for baseline calculation

3. **Shared End Frame** (spin box):
   - Default: 60
   - Last frame to use for baseline calculation

4. **Control File Pattern** (text input):
   - Default: "Ctrl"
   - Pattern to identify control files

### Config Parameters

Added to [BatchProcess.py:81-86](BatchProcess.py#L81-L86):

```python
# Shared baseline options
baseline_mode: str = "standard"  # "standard", "shared_control", "shared_per_condition"
shared_baseline_start_frame: int = 10  # Start frame for shared baseline
shared_baseline_end_frame: int = 60    # End frame for shared baseline
control_file_pattern: str = "Ctrl"     # Pattern to identify control files
shared_baseline_values: Optional[Dict[str, float]] = None  # Computed baseline {ROI: F0}
```

### Implementation Status

**✅ Completed:**
- Config parameters added to BatchProcess.py
- GUI controls added to Settings page
- Config reading in get_config() method

**🔄 In Progress:**
- Implement shared baseline calculation logic
- Modify run() function to use shared baseline
- Modify spike detection to skip first 30s exclusion for shared mode
- Testing with 0806FS2 data

---

## Testing

### Test Feature 1 & 4 & 5

```bash
# Run GUI
python GUI_3.py

# Feature 1: Check Settings page
# - Verify "Calculate spike latencies" is CHECKED by default
# - Verify status shows "✓ ENABLED" in green

# Process some files
# - Go to Batch Process
# - Add files from 0806FS2 folder
# - Click START BATCH
# - No warning dialog should appear

# Feature 4: Check latency values
# - Navigate to output folder
# - Open spike_latency_detailed.csv
# - Look for spikes with spike_time_s INSIDE stim windows
# - Verify latency_s = 0.0 for these spikes

# Feature 5: Check stats display
# - Go to Spike Review page
# - Load latency data from analysis_output folder
# - Click "Generate Summary Stats"
# - Verify table displays in resizable window
# - Try resizing the window
# - Verify TOTAL and OVERALL rows are bold
# - Verify alternating row colors
```

### Test Features 2 & 3 (When Complete)

```bash
# Test Feature 2: Shared from Control
python GUI_3.py

# 1. Go to Settings → Shared Baseline Options
#    - Set Mode: "Shared from Control files"
#    - Set Start Frame: 10
#    - Set End Frame: 60
#    - Set Control Pattern: "Ctrl"

# 2. Go to Batch Process
#    - Add files: Ctrl1.csv, Ctrl2.csv, 20s1.csv, 20s2.csv
#    - Click START BATCH

# 3. Verify:
#    - All files use baseline from Ctrl files
#    - First 30s of 20s files NOT excluded from spike detection
#    - Spikes detected in first 30s of 20s files

# Test Feature 3: Shared per Condition
# 1. Go to Settings → Shared Baseline Options
#    - Set Mode: "Shared per Condition"
#    - Set Start Frame: 10
#    - Set End Frame: 60

# 2. Go to Batch Process
#    - Add files: 20s1.csv, 20s2.csv, 20s3.csv, 10s1.csv, 10s2.csv
#    - Click START BATCH

# 3. Verify:
#    - 20s files use 20s1 baseline
#    - 10s files use 10s1 baseline
#    - First 30s NOT excluded from 20s2, 20s3, 10s2
```

---

## Version History

- **v2.7** (2025-02-05) - Added 5 new features:
  1. Spike latency default enabled
  2. Shared baseline from control (in progress)
  3. Shared baseline per condition (in progress)
  4. Spikes in stim window have latency 0
  5. Improved stats display with resizable table

---

## Files Modified

### BatchProcess.py
- Lines 81-86: Added shared baseline config options
- Lines 668-695: Modified spike latency calculation to handle in-window spikes

### GUI_3.py
- Line 16: Added QColor import
- Line 296: Changed spike latency checkbox to default checked
- Line 300: Updated initial status label
- Lines 280-315: Added shared baseline options group in Settings
- Lines 567-576: Added shared baseline config reading in get_config()
- Lines 1138-1145: Replaced QMessageBox with custom table dialog
- Lines 1150-1219: Added show_stats_table() method with resizable table

---

## Next Steps

1. ✅ Complete Features 1, 4, 5 (DONE)
2. 🔄 Implement shared baseline calculation logic (IN PROGRESS)
3. 🔄 Test with 0806FS2 data
4. 📝 Update documentation
5. 🎉 Release v2.8

---

## Notes

- All new features are backwards compatible
- Default behavior unchanged unless shared baseline mode is selected
- Spike latency now includes spikes during stimulation (latency = 0)
- Stats display is much more professional and user-friendly
- Shared baseline features enable more sophisticated experimental designs
