# NMJ Post-Process

Calcium-imaging analysis pipeline for the paper **"A Dual-Color µLED Array for
Spectrally Selective Optogenetic Control of In-Vitro Neuromuscular Co-Cultures"**
(Xie et al., UMass Amherst).

The tool processes ΔF/F₀ traces from ROI intensity CSVs exported by Leica LAS X,
detects calcium events (baseline mean + 3σ threshold with width filtering), and
computes event counts, amplitudes, and stimulation latencies across experimental
conditions. A PyQt6 GUI drives batch processing and visualization.

## Running

```bash
pip install -r requirements.txt
python GUI_3.py      # launch the GUI
# or
python main.py       # entry point
```

`GUI_3.py` imports `BatchProcess.py` and requires it to be in the same directory.

## Repository layout

```
BatchProcess.py      Core processing: ΔF/F, event detection, latency, aggregation
GUI_3.py             PyQt6 GUI (batch analysis, latency review, trace/ROI viz)
main.py              Entry point
nmj_config.json      Default processing parameters
requirements.txt     Python dependencies

data/
  raw/               Raw ROI-intensity CSVs, grouped by experiment type:
    single_color_red/    Red µLED sweeps (duration / intensity / frequency + controls)
    dual_color/          Blue-vs-red µLED stimulation comparison experiments
    blue_stim_series/    Blue µLED stimulation frequency/duration series
    validation/          Microscope-light validation & earliest simple runs (incl. mc_ files)
    misc/                C2C12_test and other one-off runs
    _loose_root_csvs/    Un-foldered CSVs recovered from the old repo root
  results/           Generated batch_results/ output folders (spike summaries, stats).
                     Regenerable; plot PNG/SVG/HTML are git-ignored (see .gitignore).
    _loose_root_csvs/    Aggregate output CSVs recovered from the old repo root

docs/                Feature/fix notes and pipeline documentation (Markdown)
tests/               Test scripts and their output fixtures
legacy/              Superseded scripts (older GUIs, deltaF*.py, standalone plotters)
figures/             µLED IV-curve device-characterization data and scripts
paper/               Manuscript .docx (git-ignored; local only, ~286 MB)
```

## Experiment conditions

Data files are named by stimulation condition (e.g. `20s1.csv`, `1mw2.csv`,
`2hz1.csv`, `blue1.csv`, `red1.csv`, `Ctrl1.csv`):

- **Duration:** 5 s / 10 s / 20 s stimulation windows
- **Intensity:** 1 / 2 / 4 mW/mm² (no events detected at 1 mW/mm²)
- **Frequency:** constant / 2 Hz / 5 Hz pulsed
- **Controls:** no-light (`Ctrl`) and far-light (`Ctrl_far`) controls
- **Dual-color:** `blue` (ChR2→PC12 NMJ activation) vs `red` (direct ChrimsonR muscle stimulation)

Imaging: 2 frame/s, GCaMP8s calcium reporter; first 30 s is baseline (no light).

## Branches

- `master` — original history (includes the large legacy commit with plot images)
- `snapshot-lite-2026-07-09` / `v2` — lightweight snapshot (source + data, plot
  artifacts excluded). **Active development happens on `v2`.**
- `snapshot-2026-07-09` — *local-only* full backup including all PNG/SVG artifacts
