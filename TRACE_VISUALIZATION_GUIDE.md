# Trace Visualization Feature Guide

## Overview

The new **Trace Visualizer** feature allows you to:
- Plot ΔF/F traces from multiple conditions and ROIs in a single SVG file
- Select specific conditions and ROIs to include
- Choose between different layout modes (stacked, grid, overlay)
- Preview the SVG visualization
- Export high-quality SVG files for publications

## Version

Added in **v2.8** (February 2026)

---

## Using the GUI

### Step-by-Step Guide

#### 1. Navigate to Trace Visualizer
- Launch the GUI: `python GUI_3.py`
- Click on **"Trace Visualizer"** in the sidebar navigation

#### 2. Load Analysis Data
- Click **"📁 Select Analysis Output Folder"**
- Select the parent analysis output folder (e.g., `analysis_output_20260205_203337/`)
- The tool will automatically discover all conditions (subfolders) and ROIs
- Status will show: "✓ Loaded: X conditions, Y ROIs"

#### 3. Select Conditions
- In the **"2. Select Conditions"** section, choose which experimental conditions to include
- Use **"Select All"** / **"Deselect All"** buttons for quick selection
- Each condition corresponds to a subfolder in your analysis output

#### 4. Select ROIs
- In the **"3. Select ROIs"** section, choose which ROIs to plot
- Use **"Select All"** / **"Deselect All"** buttons for quick selection
- All available ROIs from the loaded data will be listed

#### 5. Choose Visualization Options
- **Layout Mode:**
  - **Stacked (ROIs vertically)**: Each ROI in its own subplot, all conditions overlaid
  - **Grid (ROI x Condition)**: ROIs arranged in a grid
  - **Overlay (All on same axes)**: All traces overlaid on single axes (best for comparing conditions)

- **Show stimulation windows**: Display shaded regions for stim windows
- **Show spike markers**: Display detected spike points on traces

#### 6. Generate & Preview
- Click **"🎨 Generate SVG Preview"**
- The SVG will be generated and displayed in the preview panel
- **Note:** Preview quality depends on PyQt6-QtSvg installation (see requirements below)

#### 7. Save & Export
- **💾 Save SVG As...**: Save the SVG to a custom location
- **🌐 Open in Browser**: View the SVG in your default web browser for full quality

---

## Using the Python API

### Basic Usage

```python
import BatchProcess as bp

# Generate stacked plot
svg_path = bp.plot_multi_roi_traces_svg(
    analysis_output_folder="./analysis_output_20260205_203337",
    selected_conditions=["20-1", "20-2", "20-3"],
    selected_rois=["ROI.02 []", "ROI.05 []", "ROI.08 []"],
    output_path="./my_traces.svg",
    layout_mode="stacked",
    figsize=(16, 12),
    show_stim_windows=True,
    show_spike_markers=True,
)
print(f"SVG saved to: {svg_path}")
```

### Function Parameters

#### `plot_multi_roi_traces_svg()`

**Parameters:**

- **analysis_output_folder** (str): Path to analysis output folder containing condition subfolders
  - Example: `"./0806N/analysis_output_20260205_203337"`

- **selected_conditions** (Optional[List[str]]): List of condition names to include
  - If `None`, includes all conditions
  - Example: `["20-1", "20-2", "Ctrl1"]`

- **selected_rois** (Optional[List[str]]): List of ROI column names to include
  - If `None`, includes all ROIs
  - Example: `["ROI.02 []", "ROI.05 []"]`

- **output_path** (Optional[str]): Path to save SVG file
  - If `None`, saves to `analysis_output_folder/traces_visualization.svg`

- **layout_mode** (str): Layout mode
  - `"stacked"`: ROIs stacked vertically (default)
  - `"grid"`: ROI x Condition grid layout
  - `"overlay"`: All traces overlaid on same axes

- **figsize** (Tuple[float, float]): Figure size in inches (width, height)
  - Default: `(16, 12)`
  - Adjust based on number of ROIs/conditions

- **show_stim_windows** (bool): Show stimulation windows as shaded regions
  - Default: `True`

- **show_spike_markers** (bool): Show detected spike markers
  - Default: `True`

**Returns:**
- `str`: Path to saved SVG file

---

## Layout Modes Explained

### 1. Stacked Layout
```python
layout_mode="stacked"
```
- **Best for:** Comparing multiple conditions for each ROI
- **Layout:** Each ROI gets its own subplot, stacked vertically
- **Use case:** See how different conditions affect each ROI individually
- **Recommended for:** 2-10 ROIs, any number of conditions

### 2. Grid Layout
```python
layout_mode="grid"
```
- **Best for:** Overview of many ROIs
- **Layout:** ROIs arranged in a grid (3 columns)
- **Use case:** Quick comparison across many ROIs
- **Recommended for:** 4+ ROIs, 2-4 conditions

### 3. Overlay Layout
```python
layout_mode="overlay"
```
- **Best for:** Direct comparison of all conditions
- **Layout:** All traces on same axes
- **Use case:** Compare how one ROI responds across all conditions
- **Recommended for:** 1-3 ROIs, all conditions

---

## Examples

### Example 1: Compare Control vs Treatment
```python
svg_path = bp.plot_multi_roi_traces_svg(
    analysis_output_folder="./analysis_output_20260205_203337",
    selected_conditions=["Ctrl1", "20-1", "20-2"],
    selected_rois=["ROI.05 []"],
    layout_mode="overlay",
    figsize=(14, 8),
)
```

### Example 2: All ROIs, Selected Conditions
```python
svg_path = bp.plot_multi_roi_traces_svg(
    analysis_output_folder="./analysis_output_20260205_203337",
    selected_conditions=["20-1", "20-2", "20-3"],
    selected_rois=None,  # All ROIs
    layout_mode="stacked",
    figsize=(16, 20),
)
```

### Example 3: Grid Overview
```python
svg_path = bp.plot_multi_roi_traces_svg(
    analysis_output_folder="./analysis_output_20260205_203337",
    selected_conditions=["Ctrl1", "20-1"],
    selected_rois=["ROI.02 []", "ROI.05 []", "ROI.08 []", "ROI.10 []"],
    layout_mode="grid",
    figsize=(18, 14),
)
```

---

## Requirements

### Core Requirements (Already Installed)
- Python 3.7+
- matplotlib
- pandas
- numpy
- PyQt6

### Optional: For SVG Preview in GUI
To enable inline SVG preview in the GUI:

```bash
pip install PyQt6-QtSvg
```

**Without PyQt6-QtSvg:**
- SVG files are still generated correctly
- Preview will show a text message instead
- Use "Open in Browser" to view the SVG

**With PyQt6-QtSvg:**
- SVG preview displays directly in the GUI
- More convenient for quick iterations

---

## Data Requirements

The feature requires analysis output folders with this structure:

```
analysis_output_20260205_203337/
├── 20-1/
│   ├── dff_table.csv          (Required)
│   ├── spike_summary.csv      (Optional, for spike markers)
│   └── ...
├── 20-2/
│   ├── dff_table.csv
│   ├── spike_summary.csv
│   └── ...
└── Ctrl1/
    ├── dff_table.csv
    ├── spike_summary.csv
    └── ...
```

**Required files per condition:**
- `dff_table.csv`: Contains "Time (s)" column and ROI columns with ΔF/F values

**Optional files per condition:**
- `spike_summary.csv`: Contains spike timing information for markers

---

## Tips & Best Practices

### File Naming
- SVG files are vector graphics - they scale perfectly for publications
- Default filename: `traces_visualization.svg`
- Use descriptive names: `roi05_control_vs_treatment.svg`

### Figure Sizing
- **Stacked layout:** Increase height for more ROIs: `figsize=(16, 4*num_rois)`
- **Grid layout:** Use wider figures: `figsize=(18, 12)`
- **Overlay layout:** Standard size works: `figsize=(14, 8)`

### Color Scheme
- Colors are automatically assigned per condition using matplotlib's tab10 colormap
- Stimulation windows: Red shaded regions (alpha=0.15)
- Spike markers: Condition color with black edges

### Performance
- Loading many conditions/ROIs may take a few seconds
- SVG files can be large (1-5 MB) for complex plots
- Use condition/ROI filtering to reduce file size

---

## Troubleshooting

### "No subfolders found"
- Ensure you selected the parent analysis output folder (not a condition subfolder)
- Correct: `analysis_output_20260205_203337/`
- Incorrect: `analysis_output_20260205_203337/20-1/`

### "No valid condition data loaded"
- Check that subfolders contain `dff_table.csv` files
- Verify CSV files are not corrupted

### "No matching ROIs found"
- Selected ROIs must match column names in `dff_table.csv`
- ROI names are case-sensitive: `"ROI.05 []"` not `"roi.05"`

### SVG Preview Not Showing
- Install PyQt6-QtSvg: `pip install PyQt6-QtSvg`
- Or use "Open in Browser" to view in web browser

### SVG File Too Large
- Reduce number of conditions/ROIs
- Use filtering to focus on specific comparisons
- SVG files can be optimized with tools like SVGO

---

## Integration with Other Features

### Workflow Integration
1. **Batch Process** → Generate analysis output folders
2. **Trace Visualizer** → Create publication-quality plots
3. **Spike Review** → Verify spike detection quality
4. Export SVG → Import into Illustrator/Inkscape for final touches

### Compatible with Existing Features
- Works with all spike detection settings
- Compatible with shared baseline modes
- Works with auto-inferred stimulation windows

---

## Future Enhancements (Planned)

- [ ] Export to PNG/PDF in addition to SVG
- [ ] Customizable color schemes
- [ ] Statistical annotations (mean, SEM, etc.)
- [ ] Zoom/pan controls in preview
- [ ] Batch export multiple ROI combinations

---

## Support

For issues or questions:
1. Check the test script: `test_trace_visualization.py`
2. Review example output files
3. Report issues with error messages and data structure

---

## Changelog

### v2.8 (February 2026)
- ✨ Added Trace Visualizer page to GUI
- ✨ Added `plot_multi_roi_traces_svg()` function to BatchProcess.py
- ✨ Support for stacked, grid, and overlay layouts
- ✨ Condition and ROI selection interface
- ✨ SVG preview with optional PyQt6-QtSvg support
- ✨ Browser integration for full-quality viewing
