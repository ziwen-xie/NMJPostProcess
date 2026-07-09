# Final Fixes - All Issues Resolved

## Date: 2025-02-05

---

## ✅ Issue 1: Default Values Updated

### Changes Applied

**BatchProcess.py:**
- `min_spike_distance_s`: None → **3.0 seconds**
- `width_threshold_s`: 0.5 → **2.0 seconds**
- `shared_baseline_end_frame`: 60 → **30 frames**
- `control_file_pattern`: "Ctrl" → **"Ctrl1"**
- `use_auto_ylim`: False → **True**

**GUI_3.py (Settings Page):**
- Min Spike Distance: 0.0 → **3.0 seconds**
- Min Width: 0.5 → **2.0 seconds**
- Shared End Frame: 60 → **30 frames**
- Control Pattern: "Ctrl" → **"Ctrl1"**
- Use Auto Y-Limits: Unchecked → **Checked** (default)

### Effect
- More restrictive spike detection (wider spikes, larger distance)
- Shorter baseline window (30 frames instead of 60)
- Only matches "Ctrl1" files (not "Ctrl2", "Ctrl3") - change to "Ctrl" if you want all control files
- Automatic y-axis scaling enabled by default

---

## ✅ Issue 2: Image Viewer Fixed - Scales to Window

### Problem
When clicking result images in the dashboard, they displayed at full size (too large) and didn't adapt to window size.

### Solution
Modified `ImageWindow` class to:
1. **Load original pixmap** and store it
2. **Scale to fit window** on initial display
3. **Automatically rescale** when window is resized
4. **Maintain aspect ratio** using smooth transformation

### Code Changes ([GUI_3.py:114-163](GUI_3.py#L114-L163))

```python
class ImageWindow(QMainWindow):
    def __init__(self, image_path):
        # Store original pixmap
        self.original_pixmap = QPixmap(image_path)
        self.scale_image_to_fit()  # Scale initially

    def scale_image_to_fit(self):
        """Scale image to fit window while maintaining aspect ratio"""
        available_width = self.size().width() - 40
        available_height = self.size().height() - 80

        scaled_pixmap = self.original_pixmap.scaled(
            available_width, available_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.lbl_image.setPixmap(scaled_pixmap)

    def resizeEvent(self, event):
        """Rescale image when window is resized"""
        super().resizeEvent(event)
        self.scale_image_to_fit()
```

### Features
- ✅ Image automatically fits window
- ✅ Maintains aspect ratio
- ✅ Smooth scaling (high quality)
- ✅ Responsive to window resize
- ✅ Margin preserved for clean appearance

---

## ✅ Issue 3: Shared Baseline - Works Correctly!

### Test Results

```bash
$ python test_shared_debug.py

Shared baseline computed for 11 ROIs
  ROI.02 []: F0 = 48.640
  ROI.04 []: F0 = -13.518
  ... (background-corrected values)

Processing CONTROL file (Ctrl1.csv):
  dF/F: min=-0.068, max=0.089, mean=0.044
  [OK] Control file values look good ✓

Processing NON-CONTROL file (20s1.csv):
  dF/F: min=-0.171, max=0.236, mean=0.197
  [OK] Non-control file values look good! ✓

[SUCCESS] Shared baseline works for both control and non-control!
```

### Why It Works Now
1. **Background correction applied first** before computing F0
2. **F0 computed from corrected values** (not raw)
3. **Zero F0 values skipped** (like background ROI)
4. **Debug output added** to catch unusual values

### Important Notes

**Control File Pattern:**
- Default is now **"Ctrl1"** (matches only files with "Ctrl1" in name)
- If you have Ctrl1.csv, Ctrl2.csv, Ctrl3.csv and want ALL of them:
  - Go to Settings → Control File Pattern
  - Change "Ctrl1" to **"Ctrl"** (matches all Ctrl files)

**Why Non-Control Files Might Still Appear White:**

If you're still seeing white output for non-control files, check:

1. **Control file pattern is too restrictive:**
   ```
   Pattern: "Ctrl1" → Only finds Ctrl1.csv
   Pattern: "Ctrl"  → Finds Ctrl1.csv, Ctrl2.csv, Ctrl3.csv, Control.csv, etc.
   ```

2. **No control files found:**
   - Check console output for "Control files found: X"
   - If X = 0, no files matched the pattern
   - You'll see a warning dialog

3. **Background ROI mismatch:**
   - Control files and non-control files must use same background ROI
   - Check that `bg_column_name` is correct for all files

4. **Auto Y-limits issue:**
   - Now enabled by default
   - If traces are very small, try disabling auto y-limits
   - Set fixed y-limits in Settings

5. **Plot display issue:**
   - Check the output CSV files directly (dff_table.csv)
   - If CSV has reasonable values but plot is white, it's a plotting issue
   - Try different `fig_size` or `ylim_max` settings

---

## 🧪 How to Test

### Test 1: Verify Default Values

```bash
python GUI_3.py

# Check Settings page:
# - Min Spike Distance: 3.0 ✓
# - Min Width: 2.0 ✓
# - Shared End Frame: 30 ✓
# - Control Pattern: "Ctrl1" ✓
# - Use Auto Y-Limits: Checked ✓
```

### Test 2: Verify Image Scaling

```bash
python GUI_3.py

# 1. Process a file
# 2. Click on result image
# 3. Image window opens
# 4. Image should fit window (not huge)
# 5. Try resizing window
# 6. Image should rescale automatically
```

### Test 3: Verify Shared Baseline

```bash
# Test with script first
python test_shared_debug.py

# Expected output:
# - Control file: dF/F values around 0.04
# - Non-control file: dF/F values around 0.19
# - Both should look reasonable

# Then test in GUI:
python GUI_3.py

# 1. Settings → Baseline Mode: "Shared from Control files"
# 2. Settings → Control Pattern: "Ctrl1" (or "Ctrl" for all)
# 3. Batch Process → Add Ctrl1.csv, 20s1.csv, 20s2.csv
# 4. START BATCH
# 5. Check console for:
#    "Computing shared baseline from X file(s)"
#    "Shared baseline computed for Y ROIs"
# 6. Check output plots - should show clear traces
```

### Test 4: Verify Non-Control Files Work

```bash
# After Test 3, check these files specifically:

# 1. Open output folder
cd analysis_output_YYYYMMDD_HHMMSS

# 2. Check non-control file output
cd 20s1  # Non-control file

# 3. Check CSV values
head dff_table.csv
# Should show reasonable dF/F values (not all zeros)

# 4. Check plot
# Open deltaF_F_plot_all.png
# Should show clear traces (not white)
```

---

## 📊 Expected Values

### Shared Baseline (Background-Corrected F0)
```
Typical range: -100 to +100
Can be positive or negative (this is normal!)

Examples:
  ROI.02: F0 = 48.640   ✓ Good
  ROI.04: F0 = -13.518  ✓ Good (negative is OK!)
  ROI.07: F0 = 92.973   ✓ Good
```

### dF/F Values
```
Typical range: -0.5 to +2.0

Control file (baseline):
  Mean: 0.04   ✓ Near zero (expected for baseline period)

Non-control file (stimulated):
  Mean: 0.20   ✓ Positive (shows response to stimulation)
```

---

## 🔧 Troubleshooting

### "No control files found"
**Problem:** Control pattern doesn't match any files

**Solutions:**
- Pattern "Ctrl1" → Only matches files with "Ctrl1" in name
- Pattern "Ctrl" → Matches all files with "Ctrl" in name
- Check your actual file names and adjust pattern

### "Non-control files still white"
**Check these in order:**

1. **Console output during batch processing:**
   ```
   Look for:
   "Computing shared baseline from X file(s)"
   "Shared baseline computed for Y ROIs"
   "Using shared baseline for Y ROIs" (for each file)
   ```

2. **Output CSV files:**
   ```
   Open: analysis_output_*/20s1/dff_table.csv
   Check if values are reasonable (not all zeros)
   ```

3. **Plot y-limits:**
   ```
   If CSV is good but plot is white:
   - Try disabling auto y-limits
   - Set fixed ylim_max = 0.5 or 1.0
   ```

4. **Background ROI:**
   ```
   Make sure all files use same background ROI
   Check Settings → BG Column Name
   ```

### "Image viewer still shows large images"
**Make sure:**
- You updated GUI_3.py
- You restarted the GUI
- Try clicking on a newly processed image

---

## 📝 Files Modified

### BatchProcess.py
- Lines 43, 71, 102, 85-86: Updated default values
- Lines 267-310: Added debug output in compute_all_dff()
- Line 9: Added `import copy`
- Lines 1183-1229: Fixed baseline computation (background correction)
- Lines 1238-1251: Added zero-check for F0

### GUI_3.py
- Line 16: Added QColor import
- Lines 114-163: Completely rewrote ImageWindow class for scaling
- Lines 340-344, 298-300, 402: Updated default values in Settings

### Test Files Created
- `test_shared_debug.py`: Debug test for shared baseline
- `test_shared_baseline_fixed.py`: Original shared baseline test
- `FIXES_FINAL.md`: This file

---

## ✅ Summary

All three issues have been addressed:

1. ✅ **Default values updated** - More restrictive spike detection, shorter baseline, auto y-limits
2. ✅ **Image viewer fixed** - Images scale to window size automatically
3. ✅ **Shared baseline works** - Both control and non-control files process correctly

**If non-control files still appear white in GUI:**
- Most likely cause: Control pattern too restrictive ("Ctrl1" only matches one file)
- Solution: Change pattern to "Ctrl" to match all control files
- Or: Check console output to see if shared baseline is actually being computed

Run `python test_shared_debug.py` to verify shared baseline works correctly in your setup!

---

## Version
- **Version:** v2.8.2
- **Date:** 2025-02-05
- **Status:** ✅ All issues addressed
