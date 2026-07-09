#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test script for the new trace visualization feature.
Demonstrates how to generate SVG plots of ΔF/F traces with condition/ROI selection.
"""

import BatchProcess as bp

def test_trace_visualization_stacked():
    """Test generating stacked trace visualization"""
    print("\n" + "="*60)
    print("TEST 1: Stacked Layout - Multiple ROIs, Multiple Conditions")
    print("="*60)

    # Example: Use one of your existing analysis output folders
    analysis_folder = "./0806N/analysis_output_20260205_203337"

    # Select specific conditions (or None for all)
    selected_conditions = ["20-1", "20-2", "20-3"]  # Or None for all

    # Select specific ROIs (or None for all)
    selected_rois = ["ROI.02 []", "ROI.05 []", "ROI.08 []"]  # Or None for all

    try:
        svg_path = bp.plot_multi_roi_traces_svg(
            analysis_output_folder=analysis_folder,
            selected_conditions=selected_conditions,
            selected_rois=selected_rois,
            output_path="./test_traces_stacked.svg",
            layout_mode="stacked",
            figsize=(16, 12),
            show_stim_windows=True,
            show_spike_markers=True,
        )
        print(f"\n✓ SUCCESS: Stacked plot saved to {svg_path}")
    except Exception as e:
        print(f"\n✗ FAILED: {e}")


def test_trace_visualization_overlay():
    """Test generating overlay trace visualization"""
    print("\n" + "="*60)
    print("TEST 2: Overlay Layout - All traces on same axes")
    print("="*60)

    analysis_folder = "./0806N/analysis_output_20260205_203337"

    # Compare all conditions for a single ROI
    selected_conditions = None  # All conditions
    selected_rois = ["ROI.05 []"]  # Single ROI

    try:
        svg_path = bp.plot_multi_roi_traces_svg(
            analysis_output_folder=analysis_folder,
            selected_conditions=selected_conditions,
            selected_rois=selected_rois,
            output_path="./test_traces_overlay.svg",
            layout_mode="overlay",
            figsize=(14, 8),
            show_stim_windows=True,
            show_spike_markers=True,
        )
        print(f"\n✓ SUCCESS: Overlay plot saved to {svg_path}")
    except Exception as e:
        print(f"\n✗ FAILED: {e}")


def test_trace_visualization_grid():
    """Test generating grid trace visualization"""
    print("\n" + "="*60)
    print("TEST 3: Grid Layout - ROI x Condition grid")
    print("="*60)

    analysis_folder = "./0806N/analysis_output_20260205_203337"

    # Grid of multiple ROIs
    selected_conditions = ["20-1", "20-2", "20-3"]
    selected_rois = ["ROI.02 []", "ROI.05 []", "ROI.08 []", "ROI.10 []"]

    try:
        svg_path = bp.plot_multi_roi_traces_svg(
            analysis_output_folder=analysis_folder,
            selected_conditions=selected_conditions,
            selected_rois=selected_rois,
            output_path="./test_traces_grid.svg",
            layout_mode="grid",
            figsize=(18, 14),
            show_stim_windows=True,
            show_spike_markers=True,
        )
        print(f"\n✓ SUCCESS: Grid plot saved to {svg_path}")
    except Exception as e:
        print(f"\n✗ FAILED: {e}")


def test_trace_visualization_all_data():
    """Test with all conditions and all ROIs"""
    print("\n" + "="*60)
    print("TEST 4: All Data - All conditions, all ROIs (stacked)")
    print("="*60)

    analysis_folder = "./0806N/analysis_output_20260205_203337"

    try:
        svg_path = bp.plot_multi_roi_traces_svg(
            analysis_output_folder=analysis_folder,
            selected_conditions=None,  # All
            selected_rois=None,  # All
            output_path="./test_traces_all.svg",
            layout_mode="stacked",
            figsize=(16, 20),  # Larger figure for many ROIs
            show_stim_windows=True,
            show_spike_markers=True,
        )
        print(f"\n✓ SUCCESS: Complete plot saved to {svg_path}")
    except Exception as e:
        print(f"\n✗ FAILED: {e}")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Trace Visualization Test Suite")
    print("="*60)

    # NOTE: Update the analysis_folder path to match your actual data location
    print("\nNOTE: Make sure to update analysis_folder paths to match your data!")
    print("Example path: './0806N/analysis_output_20260205_203337'")

    # Run tests
    try:
        test_trace_visualization_stacked()
        test_trace_visualization_overlay()
        test_trace_visualization_grid()
        # test_trace_visualization_all_data()  # Uncomment to test with all data
    except Exception as e:
        print(f"\nTest suite error: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*60)
    print("Test suite complete!")
    print("="*60 + "\n")
