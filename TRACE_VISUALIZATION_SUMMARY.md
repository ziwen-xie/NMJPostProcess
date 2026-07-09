# Trace Visualization Feature - Implementation Summary

## Overview

Added a comprehensive **Trace Visualization** feature to plot and export ΔF/F traces from multiple conditions and ROIs to SVG format with interactive selection, preview, and export capabilities.

**Version:** v2.8 (February 2026)

---

## What Was Added

### 1. Core Function in BatchProcess.py

**Function:** `plot_multi_roi_traces_svg()`

**Location:** BatchProcess.py, inserted before `generate_flat_figs_for_all_rois()` (around line 2091)

**Features:**
- ✅ Loads ΔF/F data from multiple condition subfolders
- ✅ Filters by selected conditions and ROIs
- ✅ Three layout modes: stacked, grid, overlay
- ✅ Automatically infers stimulation windows from condition names
- ✅ Plots spike markers if spike data available
- ✅ Generates high-quality SVG output
- ✅ Color-coded by condition
- ✅ Comprehensive error handling and progress reporting

**Parameters:**
```python
def plot_multi_roi_traces_svg(
    analysis_output_folder: str,
    selected_conditions: Optional[List[str]] = None,
    selected_rois: Optional[List[str]] = None,
    output_path: Optional[str] = None,
    layout_mode: str = "stacked",  # "stacked", "grid", "overlay"
    figsize: Tuple[float, float] = (16, 12),
    show_stim_windows: bool = True,
    show_spike_markers: bool = True,
) -> str
```

---

### 2. New GUI Page: TraceVisualizationPage

**Location:** GUI_3.py, added as section 5 before MainWindow class (around line 1767)

**UI Components:**

#### Left Panel (Controls):
1. **Load Data Section**
   - Button to select analysis output folder
   - Status label showing loaded conditions/ROIs

2. **Select Conditions Section**
   - Multi-select list widget
   - Select All / Deselect All buttons

3. **Select ROIs Section**
   - Multi-select list widget
   - Select All / Deselect All buttons

4. **Visualization Options Section**
   - Layout mode combo box (stacked/grid/overlay)
   - Show stimulation windows checkbox
   - Show spike markers checkbox

5. **Generate & Save Section**
   - Generate SVG Preview button
   - Save SVG As... button
   - Open in Browser button
   - Status label

#### Right Panel (Preview):
- Scrollable preview area
- Displays SVG using QSvgWidget (if available)
- Fallback to text message if QtSvg not installed

**Key Methods:**
- `load_analysis_folder()`: Discovers conditions and ROIs from folder structure
- `generate_svg()`: Calls BatchProcess function to generate SVG
- `show_svg_preview()`: Displays SVG preview (uses QSvgWidget if available)
- `save_svg_as()`: Copies SVG to user-selected location
- `open_svg_external()`: Opens SVG in default browser

---

### 3. GUI Integration Updates

**Updated Files:**
- `GUI_3.py`

**Changes:**

#### Imports (lines 8-21):
```python
# Added QComboBox to main imports
from PyQt6.QtWidgets import (..., QComboBox)

# Added optional QSvgWidget import
try:
    from PyQt6.QtSvgWidgets import QSvgWidget
    HAS_SVG_WIDGET = True
except ImportError:
    HAS_SVG_WIDGET = False
```

#### MainWindow Updates:
- Added `btn_page4` navigation button for "Trace Visualizer" (line ~1999)
- Added `page_trace_viz = TraceVisualizationPage()` instance (line ~2020)
- Added page to stack widget (line ~2024)
- Connected navigation button (line ~2031)
- Updated `switch_page()` to handle 4th button (line ~2043)
- Updated version label to "v2.8" (line ~2008)

#### Removed Duplicate Imports:
- Removed 3 instances of local `from PyQt6.QtWidgets import QComboBox`
  - In SettingsPage (~line 312)
  - In BatchAnalysisPage (~line 362)
  - In TraceVisualizationPage (~line 1893)

---

### 4. Test Script

**File:** `test_trace_visualization.py`

**Tests Included:**
1. `test_trace_visualization_stacked()`: Test stacked layout
2. `test_trace_visualization_overlay()`: Test overlay layout for single ROI
3. `test_trace_visualization_grid()`: Test grid layout
4. `test_trace_visualization_all_data()`: Test with all conditions/ROIs

**Usage:**
```bash
python test_trace_visualization.py
```

---

### 5. Documentation

**File:** `TRACE_VISUALIZATION_GUIDE.md`

**Sections:**
- Overview and features
- GUI step-by-step guide
- Python API documentation
- Layout modes explained
- Examples
- Requirements
- Data structure requirements
- Tips & best practices
- Troubleshooting
- Integration with other features
- Changelog

---

## Features Implemented

### ✅ Data Loading & Discovery
- Automatically discovers all conditions from analysis output folder
- Extracts all ROI names from dff_table.csv files
- Handles missing or corrupted files gracefully
- Reports loading status with detailed feedback

### ✅ Selection Interface
- Multi-select lists for conditions and ROIs
- Select All / Deselect All quick controls
- Clear visual indication of selected items
- Works with any number of conditions/ROIs

### ✅ Layout Modes

**1. Stacked Layout**
- Each ROI in separate subplot
- All conditions overlaid per ROI
- Best for comparing conditions within each ROI
- Ideal for 2-10 ROIs

**2. Grid Layout**
- ROIs arranged in 3-column grid
- Compact overview of many ROIs
- Best for quick comparisons
- Ideal for 4+ ROIs

**3. Overlay Layout**
- All traces on single axes
- Direct comparison of all conditions
- Best for single ROI analysis
- Ideal for 1-3 ROIs

### ✅ Visualization Options
- Toggle stimulation windows (red shaded regions)
- Toggle spike markers (circles with black edges)
- Automatic color assignment per condition
- Baseline reference line (y=0)
- Grid lines for readability
- Automatic legend generation

### ✅ SVG Generation
- High-quality vector graphics (scalable)
- Automatic stimulation window inference from condition names
- Spike data integration from spike_summary.csv
- Configurable figure size
- Professional formatting

### ✅ Preview & Export
- Optional inline SVG preview (requires PyQt6-QtSvg)
- Fallback text message if QtSvg not available
- "Open in Browser" for full-quality viewing
- "Save As" for custom file location
- Default save location in analysis folder

### ✅ Error Handling
- Validates folder structure
- Handles missing files gracefully
- Clear error messages
- Progress reporting during generation
- Comprehensive exception handling

---

## Technical Implementation Details

### Data Flow

```
1. User selects analysis output folder
   ↓
2. GUI scans for subfolders (conditions)
   ↓
3. GUI reads dff_table.csv from each subfolder
   ↓
4. GUI extracts ROI column names
   ↓
5. User selects conditions + ROIs + options
   ↓
6. GUI calls plot_multi_roi_traces_svg()
   ↓
7. Function loads data for selected items
   ↓
8. Function generates matplotlib figure
   ↓
9. Function saves as SVG
   ↓
10. GUI displays preview and enables export
```

### File Requirements

**Input Structure:**
```
analysis_output_YYYYMMDD_HHMMSS/
├── condition1/
│   ├── dff_table.csv          (Required)
│   ├── spike_summary.csv      (Optional)
│   └── ...
├── condition2/
│   ├── dff_table.csv
│   └── ...
└── ...
```

**dff_table.csv Format:**
- Must have "Time (s)" column
- ROI columns with ΔF/F values
- Example: "ROI.02 []", "ROI.05 []", etc.

**spike_summary.csv Format:**
- Must have "ROI" column
- Must have "spike_times_s" column (semicolon-separated values)
- Example: "12.345;45.678;78.901"

### Dependencies

**Required (Core):**
- matplotlib (plotting)
- pandas (data loading)
- numpy (numerical operations)
- PyQt6 (GUI framework)

**Optional:**
- PyQt6-QtSvg (for inline SVG preview in GUI)

### Color Scheme
- Conditions: matplotlib tab10 colormap (automatic)
- Stimulation windows: Red with alpha=0.15
- Spike markers: Condition color with black edges
- Baseline: Gray dashed line
- Grid: Gray with alpha=0.3

---

## Usage Examples

### GUI Usage
1. Launch GUI: `python GUI_3.py`
2. Navigate to "Trace Visualizer"
3. Click "📁 Select Analysis Output Folder"
4. Select conditions and ROIs (or use Select All)
5. Choose layout mode and options
6. Click "🎨 Generate SVG Preview"
7. Click "🌐 Open in Browser" for full quality
8. Click "💾 Save SVG As..." to export

### Python API Usage
```python
import BatchProcess as bp

# Generate stacked plot
svg_path = bp.plot_multi_roi_traces_svg(
    analysis_output_folder="./analysis_output_20260205_203337",
    selected_conditions=["20-1", "20-2", "Ctrl1"],
    selected_rois=["ROI.02 []", "ROI.05 []"],
    output_path="./my_plot.svg",
    layout_mode="stacked",
    figsize=(16, 12),
    show_stim_windows=True,
    show_spike_markers=True,
)
```

---

## Testing

### Test Coverage
- ✅ Stacked layout generation
- ✅ Grid layout generation
- ✅ Overlay layout generation
- ✅ All conditions/ROIs (comprehensive test)
- ✅ Condition filtering
- ✅ ROI filtering
- ✅ Stimulation window display
- ✅ Spike marker display

### Test Files
- `test_trace_visualization.py`: Automated test suite
- `TRACE_VISUALIZATION_GUIDE.md`: User documentation

---

## Future Enhancements (Potential)

### Planned
- [ ] Export to PNG/PDF formats
- [ ] Customizable color schemes
- [ ] Statistical overlays (mean, SEM, etc.)
- [ ] Interactive zoom/pan in preview
- [ ] Batch export multiple combinations

### Under Consideration
- [ ] Time window selection (zoom to specific time range)
- [ ] Y-axis normalization options
- [ ] Baseline subtraction toggle
- [ ] Custom figure styling (fonts, colors, etc.)
- [ ] Export configuration presets

---

## Version History

### v2.8 (February 2026)
- ✨ **NEW:** Added Trace Visualization feature
- ✨ **NEW:** `plot_multi_roi_traces_svg()` function in BatchProcess.py
- ✨ **NEW:** TraceVisualizationPage in GUI
- ✨ **NEW:** Three layout modes (stacked, grid, overlay)
- ✨ **NEW:** Condition and ROI selection interface
- ✨ **NEW:** SVG preview with optional QtSvg support
- ✨ **NEW:** Browser integration for viewing
- 🔧 **FIX:** Removed duplicate QComboBox imports
- 🔧 **FIX:** Improved import structure with optional QSvgWidget
- 📝 **DOCS:** Added comprehensive user guide
- 📝 **DOCS:** Added test script with examples

---

## File Changes Summary

### New Files
1. `TRACE_VISUALIZATION_GUIDE.md` - User documentation (500+ lines)
2. `TRACE_VISUALIZATION_SUMMARY.md` - Implementation summary (this file)
3. `test_trace_visualization.py` - Test script (150+ lines)

### Modified Files
1. `BatchProcess.py` - Added `plot_multi_roi_traces_svg()` function (250+ lines)
2. `GUI_3.py` - Added TraceVisualizationPage class (400+ lines) + MainWindow updates

### Lines of Code Added
- **BatchProcess.py:** ~250 lines
- **GUI_3.py:** ~450 lines
- **Documentation:** ~800 lines
- **Tests:** ~150 lines
- **Total:** ~1,650 lines

---

## Integration Points

### With Existing Features

**Batch Process Page:**
- Uses output from batch processing
- Requires completed analysis output folders
- Compatible with all processing options

**Settings Page:**
- Respects spike detection settings
- Compatible with shared baseline modes
- Uses stimulation preset inference

**Spike Review Page:**
- Can visualize same data
- Shows detected spikes as markers
- Complementary analysis views

---

## Success Criteria

✅ **All criteria met:**

1. ✅ Plot ΔF/F traces to SVG format
2. ✅ Select conditions for plotting
3. ✅ Select ROIs for plotting
4. ✅ Preview SVG in GUI
5. ✅ Save SVG to custom location
6. ✅ Support multiple layout modes
7. ✅ Show stimulation windows
8. ✅ Show spike markers
9. ✅ Professional quality output
10. ✅ Comprehensive documentation
11. ✅ Test script provided
12. ✅ Error handling implemented

---

## Conclusion

The Trace Visualization feature is now fully implemented and integrated into the NMJ Analysis application. Users can generate publication-quality SVG plots of ΔF/F traces with flexible condition and ROI selection through both the GUI and Python API.

The feature is production-ready and includes comprehensive documentation, examples, and test coverage.
