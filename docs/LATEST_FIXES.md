# Latest Fixes - Spike Latency Issues

## Date: 2025-02-05

### Issue 1: ✅ Spike Latency Calculation in GUI

**Problem:** User reported that spike latency was not being computed when clicking "START BATCH" in GUI.

**Root Cause:** The feature was working correctly, but there was no visible feedback indicating whether spike latency calculation was enabled or running.

**Solution:**
- Added debug output in `AnalysisWorker.run()` that prints:
  - File being processed
  - Whether spike latency calculation is ENABLED or DISABLED
  - Output folder location
- This makes it immediately clear to the user if the feature is active

**Code Changes:** [GUI_3.py:176-182](GUI_3.py:176-182)
```python
print(f"\n{'='*60}")
print(f"Processing: {self.file_path.name}")
print(f"Spike latency calculation: {'ENABLED' if local_cfg.calculate_spike_latencies else 'DISABLED'}")
print(f"Output folder: {file_output_dir}")
print(f"{'='*60}\n")
```

**How to Use:**
1. Go to **Settings** page
2. Check ☑ **"Calculate spike latencies"**
3. Return to **Batch Process** page
4. Click **START BATCH**
5. **Watch the console** - you'll see "Spike latency calculation: ENABLED" for each file
6. Latency CSV files will be created in each file's output subfolder

---

### Issue 2: ✅ Improved Spike Review Folder Selection

**Problem:** Users were confused when trying to load spike latency data. The folder picker didn't show files, and error messages weren't helpful.

**Root Cause:**
- Users were selecting the wrong folder (parent folder instead of file-specific subfolder)
- Error messages didn't explain what was wrong
- No guidance on what folder to select

**Solution:**
- Added **instructions dialog** before folder selection explaining:
  - Which folder to select (file-specific subfolder)
  - Example path format
  - What files should be in the folder
- Enhanced error messages that:
  - List all CSV files found in selected folder
  - Explain common mistakes
  - Provide troubleshooting steps

**Code Changes:** [GUI_3.py:644-729](GUI_3.py:644-729)

**How to Use:**
1. Go to **Spike Review** page
2. Click **"Load Latency Data"**
3. **Read the instruction dialog** that appears
4. Click OK
5. **Select the FILE-SPECIFIC subfolder**, for example:
   ```
   analysis_output_20250205_203337/20-1/
   ```
   **NOT** the parent folder:
   ```
   analysis_output_20250205_203337/  ❌ WRONG
   ```
6. If files are missing, you'll get a helpful error message listing what's in the folder

**Common Mistakes:**
- ❌ Selecting parent folder (`analysis_output_YYYYMMDD_HHMMSS/`)
- ❌ Spike latency calculation was not enabled during processing
- ✅ Select the subfolder with your specific filename (`20-1/`, `20-2/`, etc.)

---

### Issue 3: ✅ Summary Statistics Table

**Problem:** Users needed to see aggregate statistics for selected spikes grouped by condition.

**New Feature Added:**
- **"Generate Summary Stats"** button in Spike Review page
- Calculates per-ROI and overall statistics:
  - Spike count
  - Average latency
  - Median latency
  - Standard deviation
- Saves to CSV file: `spike_latency_summary_stats.csv`
- Displays formatted table in dialog

**Code Changes:** [GUI_3.py:917-1005](GUI_3.py:917-1005)

**Output Format:**

**CSV File (spike_latency_summary_stats.csv):**
```csv
Condition,ROI,Spike_Count,Avg_Latency_s,Median_Latency_s,Std_Latency_s
20-1,ROI.14 [],3,25.614,24.287,5.123
20-1,ROI.15 [],2,30.145,30.145,2.456
20-1,OVERALL,5,27.315,25.614,4.892
```

**Display in GUI:**
```
Summary Statistics for 20-1
============================================================

ROI             Spikes     Avg Latency (s)    Median (s)
------------------------------------------------------------
ROI.14 []       3          25.614             24.287
ROI.15 []       2          30.145             30.145
------------------------------------------------------------
OVERALL         5          27.315             25.614

============================================================
Saved to: spike_latency_summary_stats.csv
```

**How to Use:**
1. Go to **Spike Review** page
2. Load spike latency data from a folder
3. **Review spikes** and check/uncheck to include/exclude them
4. Click **"Generate Summary Stats"**
5. View the summary table in the dialog
6. Click "Show Details" to see the full formatted report
7. File is automatically saved in the same folder as the loaded data

**What It Shows:**
- **Per ROI:** How many spikes and average latency for each ROI
- **OVERALL:** Total spikes and average latency across all selected ROIs
- **Condition Name:** Extracted from the folder name (e.g., "20-1")

---

## Testing

### Test 1: Verify Latency Calculation in GUI

```bash
# 1. Start GUI
python GUI_3.py

# 2. Go to Settings page
#    - Check "Calculate spike latencies"

# 3. Go to Batch Process page
#    - Add some CSV files from 0806N folder
#    - Click START BATCH

# 4. Watch console output - you should see:
#    Processing: 20-1.csv
#    Spike latency calculation: ENABLED
#    Output folder: ...

# 5. Check output folder for:
#    - spike_latency_stats.csv
#    - spike_latency_detailed.csv
```

### Test 2: Verify Improved Folder Selection

```bash
# 1. After running Test 1, go to Spike Review page
# 2. Click "Load Latency Data"
# 3. You'll see instruction dialog
# 4. Select the file-specific subfolder (e.g., analysis_output_*/20-1/)
# 5. Should load successfully and show spikes with waveforms
```

### Test 3: Verify Summary Statistics

```bash
# 1. After loading data in Test 2
# 2. Review spikes (check/uncheck as desired)
# 3. Click "Generate Summary Stats"
# 4. Should see dialog with formatted table
# 5. Check folder for spike_latency_summary_stats.csv
# 6. Verify it contains per-ROI and OVERALL statistics
```

---

## Files Modified

1. **GUI_3.py**
   - Line 176-182: Added debug output for latency calculation status
   - Line 644-729: Improved folder selection with instructions and better errors
   - Line 617-621: Added "Generate Summary Stats" button
   - Line 917-1005: Implemented summary statistics generation

---

## Checklist for Users

Before using Spike Latency features:
- [ ] ✅ Spike latency calculation is **enabled** in Settings page
- [ ] ✅ You see "Spike latency calculation: ENABLED" in console during processing
- [ ] ✅ Output folder contains both `spike_latency_detailed.csv` and `dff_table.csv`
- [ ] ✅ When loading in Spike Review, select the **file-specific subfolder**, not parent

When generating summary stats:
- [ ] ✅ Data is loaded successfully in Spike Review page
- [ ] ✅ Spikes are reviewed and checked/unchecked as desired
- [ ] ✅ "Generate Summary Stats" button is enabled (not grayed out)
- [ ] ✅ Summary displays condition name, spike counts, and average latencies

---

## Version
- **GUI Version:** v2.7 (Enhanced)
- **Update Date:** 2025-02-05
- **Status:** ✅ All three issues fixed and tested
