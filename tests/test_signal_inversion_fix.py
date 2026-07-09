"""
Test to verify the signal inversion fix for negative F0 values.
"""
import numpy as np
import BatchProcess as bp

print("="*60)
print("Testing Signal Inversion Fix")
print("="*60)

# Simulate background-corrected fluorescence
# After background subtraction, baseline could be negative
F0_negative = -20.0
F_baseline = np.array([-20, -19, -21, -20, -20])  # Around baseline
F_spike = np.array([-15, -10, -5, -10, -15])      # Spike (less negative = increase)

# Combine into a trace
F_trace = np.concatenate([F_baseline, F_spike, F_baseline])
print(f"\nSimulated trace (background-corrected):")
print(f"  Baseline values: {F_baseline} (around {F0_negative})")
print(f"  Spike values: {F_spike} (increased fluorescence)")

# Test the fixed dff_fixed_baseline function
dff, F0_array = bp.dff_fixed_baseline(F_trace, F0_negative)

print(f"\nResults with fixed formula:")
print(f"  F0 = {F0_negative}")
print(f"  Baseline dF/F: {dff[:5]} (should be near 0)")
print(f"  Spike dF/F: {dff[5:10]} (should be POSITIVE)")
print(f"  Mean spike dF/F: {dff[5:10].mean():.3f}")

# Check if signal is correctly oriented
if dff[5:10].mean() > 0:
    print("\n[SUCCESS] Signal is correctly oriented!")
    print("  Increased fluorescence -> Positive dF/F")
else:
    print("\n[FAILED] Signal is inverted!")
    print("  Increased fluorescence -> Negative dF/F")

print("\n" + "="*60)
print("Test complete")
print("="*60)
