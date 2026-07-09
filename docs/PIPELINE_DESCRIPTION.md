# Automated Post-Processing Pipeline for Fluorescence Calcium Imaging of Neuromuscular Junction Activity

## 1. Overview

This document describes the algorithmic pipeline implemented in the NMJ Analysis Pro software (v2.9) for the detection, quantification, and statistical analysis of calcium transient events from fluorescence microscopy recordings of neuromuscular junctions (NMJs). The pipeline operates on region-of-interest (ROI) intensity time-series exported from imaging software and proceeds through four principal stages: **(1)** data selection, **(2)** configuration, **(3)** signal processing and event detection, and **(4)** downstream analysis including latency estimation, event counting, amplitude measurement, and per-ROI comparison.

---

## 2. Stage 1 — Data Selection

The input to the pipeline consists of comma-separated value (CSV) files exported from fluorescence imaging software, where each file represents one experimental recording. Each CSV file contains a time column (typically labeled `Axis [s]`) and multiple ROI intensity columns (e.g., `ROI.01 []`, `ROI.02 []`, ..., `ROI.N []`). Files are encoded in UTF-16 format with an optional header row to be skipped.

The graphical user interface (GUI) provides a **Batch Process** page where the user selects one or more CSV files for analysis. Files are typically named following a convention that encodes the experimental condition and replicate number (e.g., `blue3.csv`, `20-1.csv`, `Ctrl1.csv`). A filename parser (`parse_experiment_filename`) extracts the condition group and replicate index using regular expression matching, enabling automated aggregation across experiments.

A designated background ROI column (e.g., `ROI.000 []`) is specified to serve as the reference for background subtraction. Alternatively, an external CSV file may provide the background trace, which is interpolated to match the recording time base.

---

## 3. Stage 2 — Configuration

Processing parameters are organized into a `Config` dataclass and exposed through two GUI interfaces: a **Quick Configuration** panel on the Batch Process page for frequently adjusted parameters, and an **Advanced Configuration** (Settings) page for the full parameter set. Configurations can be serialized to and loaded from JSON files for reproducibility.

The principal configuration parameters are:

### 3.1 Stimulation Window Definition

Stimulation windows define the temporal intervals during which optical or electrical stimulation is applied. Three built-in presets are available:

| Preset | Windows (seconds) |
|--------|-------------------|
| **20s** | (30, 50), (80, 100), (130, 150) |
| **10s** | (30, 40), (70, 80), (110, 120) |
| **5s** | (30, 35), (65, 70), (100, 105) |

When `stim_preset_infer_from_name` is enabled, the stimulation preset is automatically inferred from the filename (e.g., a file named `20-3.csv` is assigned the 20s preset). Custom stimulation windows may also be specified explicitly.

### 3.2 Baseline and ΔF/F Computation Parameters

- **Baseline Window Half-Size** (`baseline_window_half_s`, default 15.0 s): The temporal half-width of the sliding window used for computing the local baseline fluorescence F₀.
- **Baseline Percentile** (`baseline_percentile`, default 8.0%): The percentile of the fluorescence distribution within the sliding window used as F₀, providing robustness to transient fluorescence increases.
- **Baseline Frame Range** (`baseline_index_start`, `baseline_index_end`): Frame indices defining the quiescent period used for event detection threshold computation (distinct from the ΔF/F baseline).
- **Baseline Mode**: Determines whether baseline F₀ values are computed independently per file (*standard*), shared from designated control files (*shared from control*), or shared within each condition group (*shared per condition*).

### 3.3 Event Detection Parameters

- **Z-Score Threshold** (`spike_z_sigma`, default 5.0): The number of standard deviations above the baseline mean required to classify a transient as a candidate event.
- **Minimum Event Width** (`width_threshold_s`, default 2.0 s): The minimum temporal duration (rough width or full-width at half-maximum) a candidate transient must span to be accepted.
- **Minimum Inter-Event Distance** (`min_spike_distance_s`, default 3.0 s): The minimum temporal separation required between consecutive accepted events within the same ROI.
- **Stimulation Window Exclusion Mode**: Controls whether events occurring within stimulation windows are excluded from the final event set. Options include exclusion of all events during stimulation, exclusion only in files designated as "blue" (stimulated), or no exclusion.
- **Stimulation Exclusion Padding** (`stim_exclusion_pad_s`): Temporal padding applied symmetrically around stimulation window boundaries when filtering events.

### 3.4 Latency Analysis Parameters

- **Latency Method**: Determines the algorithm used for computing the temporal delay between stimulation and evoked events (see Section 4.4).
- **Maximum Latency Window** (`max_latency_window_s`): An optional upper bound on latency; events exceeding this delay are excluded from latency statistics.

---

## 4. Stage 3 — Signal Processing and Event Detection

### 4.1 Background Subtraction and ΔF/F Computation

For each ROI column *F*(*t*) and the designated background signal *F_bg*(*t*), the background-corrected fluorescence is computed as:

$$F_{\text{corr}}(t) = F(t) - F_{\text{bg}}(t)$$

The fractional change in fluorescence (ΔF/F) is then computed using a sliding percentile baseline. For each time point *t_i*, the local baseline *F₀*(*t_i*) is defined as the *p*-th percentile (default *p* = 8) of *F_corr* within a symmetric temporal window [*t_i* − *w*, *t_i* + *w*], where *w* is the window half-size (default 15 s):

$$\Delta F/F(t_i) = \frac{F_{\text{corr}}(t_i) - F_0(t_i)}{|F_0(t_i)| + \varepsilon}$$

where ε = 10⁻⁹ prevents division by zero. The absolute value in the denominator prevents signal inversion when *F₀* is negative (which may occur after background subtraction).

When a shared baseline mode is selected, *F₀* is computed as a fixed scalar from a designated reference recording (e.g., a control condition) rather than a sliding window, ensuring consistent normalization across experimental conditions.

### 4.2 Iterative Baseline Cleaning for Threshold Computation

Event detection thresholds are derived from the ΔF/F trace during a user-defined quiescent baseline period (e.g., frames 10–30, corresponding to the pre-stimulation interval). The threshold is:

$$\theta = \mu_{\text{base}} + k \cdot \sigma_{\text{base}}$$

where μ_base and σ_base are the mean and standard deviation of the baseline ΔF/F, and *k* is the z-score multiplier.

A contaminating transient event within the baseline period (e.g., a spontaneous calcium event before stimulation onset) can inflate both μ_base and σ_base, raising the threshold and causing genuine evoked events to be missed. To address this, an iterative outlier removal procedure based on the **Median Absolute Deviation (MAD)** is applied:

```
Input:  baseline segment B[1..N], outlier sensitivity α (default 2.0),
        buffer radius r (default 2 frames), max iterations K (default 3)

mask ← [True, True, ..., True]   (length N)

for iteration = 1 to K:
    B_clean ← B[mask]
    m       ← median(B_clean)
    MAD     ← median(|B_clean − m|)
    σ_MAD   ← 1.4826 × MAD                  // normal-equivalent σ
    θ_out   ← m + α × σ_MAD
    outliers ← { i : B[i] > θ_out  AND  mask[i] = True }
    if outliers = ∅:  break
    for each outlier index i:
        mask[i−r .. i+r] ← False             // exclude neighborhood

B_final ← B[mask]
μ_base  ← mean(B_final)
σ_base  ← std(B_final)
```

The use of MAD rather than the sample mean and standard deviation is critical: because the mean and standard deviation are themselves corrupted by outliers, a mean ± *k*σ criterion fails to identify contaminating events — the contamination masks itself. The MAD, being a robust estimator of scale based on the median, remains unaffected by even large outliers.

### 4.3 Event Detection Algorithm

Events are detected in each ROI's ΔF/F trace through the following multi-step procedure:

**Step 1 — Threshold Exceedance Segmentation.** Contiguous segments ("runs") of time points where ΔF/F > θ are identified. Each run represents a candidate event region.

**Step 2 — Run Splitting at Stimulation Boundaries.** When the detection threshold is low (e.g., after iterative baseline cleaning), the large light-leakage artifact during stimulation and a genuine post-stimulation biological event may form a single merged run. To separate them, each run that spans a stimulation window endpoint is split into sub-runs:

1. The run is divided at the stimulation window end time *t_end*, producing an in-stimulation portion and a post-stimulation portion.
2. The post-stimulation portion is further split at the **first local minimum** of the ΔF/F signal — the valley between the decaying stimulation artifact and the rising biological transient. This local minimum is identified as the first point where the discrete derivative transitions from non-positive to positive.

```
Original run:   [===STIM ARTIFACT===|--artifact tail--|~~BIO EVENT~~]
                 t=30s              t=50s             t=52s    t=58s

Split into:     [===STIM ARTIFACT===]  [--tail--]  [~~BIO EVENT~~]
                 (filtered by stim      (rejected:   (accepted:
                  window exclusion)      too short)   passes width filter)
```

**Step 3 — Width Filtering.** For each sub-run, the peak amplitude index is identified and the temporal width is measured using one of two modes:

- *Rough width*: the time span from the first to the last index of the run.
- *FWHM (Full Width at Half Maximum)*: computed via linear interpolation of the ΔF/F trace at the half-maximum level (midpoint between the peak and the baseline mean).

Sub-runs whose measured width falls below the minimum width threshold are rejected.

**Step 4 — Stimulation Window Exclusion.** Events whose peak times fall within stimulation windows (optionally with temporal padding) are removed. This step is performed **before** minimum-distance filtering (Step 5), which is essential: if minimum-distance filtering were applied first, a stimulation artifact peak could suppress a nearby biological event via the proximity rule, and then the artifact itself would be removed by window exclusion — resulting in both events being lost.

```
Incorrect ordering (events lost):
  Peaks: [48.8s (stim artifact), 52.8s (biological)]
  → min_distance (5s):  52.8s removed  (only 4s from 48.8s)
  → stim exclusion:     48.8s removed
  → Result: BOTH lost

Correct ordering (events preserved):
  Peaks: [48.8s (stim artifact), 52.8s (biological)]
  → stim exclusion:     48.8s removed
  → min_distance (5s):  52.8s survives  (nearest neighbor now >5s away)
  → Result: 52.8s detected
```

**Step 5 — Minimum Inter-Event Distance Filtering.** Remaining events are sorted chronologically. Events occurring within the minimum inter-event distance of a preceding accepted event are rejected, enforcing temporal separation.

**Step 6 — Early-Time Exclusion.** Events occurring before *t* = 10 s are discarded to avoid edge effects from the sliding baseline computation.

---

## 5. Stage 4 — Downstream Analysis

Following event detection, the pipeline provides several analysis modules accessible through the GUI.

### 5.1 Event Filtering and Manual Curation

The **Event Review** page displays each detected event as an individual panel showing the ΔF/F trace segment surrounding the event, with the event time, ROI identity, experimental condition, and computed latency annotated. Each event has an associated checkbox allowing the user to include or exclude it from downstream analyses. Two automated exclusion rules are provided:

- **Maximum latency threshold** (default 60 s): Events with latency exceeding this value are automatically unchecked.
- **Range exclusion** (default 20–22 s): Events with latency within this range are automatically unchecked, designed to eliminate artifacts arising from light leakage that extends slightly beyond the nominal stimulation window boundary into the next inter-stimulation interval.

Filtered results can be saved and reloaded for continued analysis.

### 5.2 Latency Analysis

Event latency quantifies the temporal delay between stimulation and the evoked calcium transient. Four methods are implemented:

**(a) Nearest Latency.** For each detected event at time *t_event*, the most recent stimulation window ending before the event is identified, and the latency is computed as:

$$L = t_{\text{event}} - t_{\text{stim\_end}}$$

**(b) First-Event Latency.** For each stimulation window, only the first evoked event (the earliest event following the window's end) is considered. This provides one latency measurement per stimulation epoch per ROI.

**(c) Stimulation Onset Latency.** Latency is measured from the stimulation window *start* rather than its end:

$$L = t_{\text{event}} - t_{\text{stim\_start}}$$

This captures the total response time including the stimulation duration.

**(d) Point-Process GLM Latency.** A generalized linear model (GLM) with a logistic link function models the event probability as a function of stimulus history and past event history:

$$\text{logit}(P(\text{event at } t)) = \beta_0 + \boldsymbol{\beta}_{\text{stim}} \cdot \mathbf{X}_{\text{stim}}(t) + \boldsymbol{\beta}_{\text{hist}} \cdot \mathbf{X}_{\text{hist}}(t)$$

The stimulus history design matrix **X_stim** is constructed by convolving the binary stimulus signal with a bank of 8 raised-cosine basis functions spanning 0–30 s post-stimulus, providing a flexible nonparametric stimulus filter. The event history **X_hist** uses two exponential kernels: a fast refractory component (τ = 0.5 s) and a slow adaptation component (τ = 5.0 s). Model parameters are estimated via L-BFGS-B optimization of the penalized log-likelihood (L2 regularization, λ = 0.01). Latency is estimated per stimulation window as the time at which the predicted event rate first exceeds the baseline rate plus two standard deviations.

Output files include per-ROI summary statistics (mean, median, standard deviation, min, max latency) and a detailed per-event record.

### 5.3 Event Count Analysis

Event counts are aggregated per condition group (e.g., blue, red, Ctrl) across replicates. The analysis produces:

- **Bar plots** with error bars (mean ± SEM across replicates) and individual replicate data points overlaid. Pairwise significance is assessed using the Mann–Whitney U test, with significance brackets and *p*-values annotated on the figure.
- **Exported CSV tables**: per-condition counts, per-group statistics, and per-ROI breakdowns.

Condition group extraction follows a rule-based parser: `Ctrl` and `Ctrl1` are mapped to "Ctrl" (no-light control), `Ctrl2` and above are mapped to "Far Light Control," and other condition names have trailing digits stripped to form the group label.

### 5.4 Amplitude Analysis

Event amplitude is defined as the ΔF/F value at the detected event peak time, looked up from the stored ΔF/F table for the corresponding condition and ROI. Amplitude analysis includes:

- **Grouped bar plots** of mean event amplitude per condition with SEM error bars, individual data point overlay, and Mann–Whitney significance brackets.
- **Per-ROI amplitude comparison** across conditions, presented as a grid of subplots where each subplot corresponds to one ROI.
- **Violin plots** showing the full amplitude distribution per condition group.

### 5.5 Per-ROI Analysis

Several analysis modes operate at the individual ROI level:

- **Per-ROI event count plots**: A grid of subplots where each subplot shows the event count for one ROI across all condition groups, with individual replicate data points and significance testing.
- **Per-ROI condition comparison plots**: Subplots comparing a chosen metric (event count, latency, or amplitude) across conditions for each ROI independently.
- **Cross-experiment single-ROI visualization**: A selected ROI's ΔF/F trace is plotted across all experimental recordings, with vertical offset for visual separation and event markers overlaid.

### 5.6 Trace Visualization

The **Trace Visualizer** page generates publication-quality SVG plots of ΔF/F traces. Users select specific conditions and ROIs from analysis output folders. Per-condition vertical offsets can be applied in three modes: *none* (traces overlap), *auto* (offset = 1.2 × median peak-to-peak amplitude across conditions), or *manual* (user-specified offset). End-of-trace labels identify each condition, rendered with white background boxes for readability. The SVG output uses embedded text (not outlines) with Arial font for direct editability.

### 5.7 ROI Map Overlay

The **ROI Map** page allows spatial visualization by overlaying event counts on a reference microscopy image. ROI markers are interactively placed (click-to-add, drag-to-reposition) and display the ROI number and event count. Optional OCR detection (via Tesseract) can automatically detect ROI labels from the reference image. The composite image can be exported at full resolution.

### 5.8 Batch Aggregation

For multi-file experiments, the pipeline aggregates results across all processed files:

- **Event timestamp collection**: All event times are compiled into a single table with condition, replicate, and ROI annotations.
- **Latency collection**: All per-event latency records are aggregated with experimental metadata.
- **Raster plots**: Event occurrences are visualized as a matrix of condition × ROI, with each cell marked if an event was detected, enabling rapid visual assessment of response patterns across the preparation.

---

## 6. Software Architecture

The pipeline is implemented in Python using NumPy and Pandas for numerical computation, Matplotlib for visualization, and SciPy for statistical testing and GLM optimization. The graphical interface is built with PyQt6 and organized as a five-page navigation structure:

| Page | Function |
|------|----------|
| **Batch Process** | Data selection and batch execution |
| **Settings** | Full parameter configuration with save/load |
| **Event Review** | Event curation, latency/count/amplitude analysis |
| **Trace Visualizer** | Publication-quality SVG figure generation |
| **ROI Map** | Spatial overlay of event counts on microscopy images |

Batch processing executes in a background thread pool to maintain GUI responsiveness, with per-file results stored in timestamped output directories for traceability.
