"""0718 academic data-showcase figure (journal style).

  a  contact FOV (loads figures/0718/assets/contact_0718.png if present).
  b  ΔF/F traces of representative biological responders (ROI 03/04/05), no-light
     control + one representative recording per condition (variable-length, empty
     tails trimmed). LED pixel is by ROI 08/10/12.
  c/d/e  per-condition event count / amplitude / latency. The 20 s recordings are
     4 mW constant light, so 20 s data also populates the "4 mW" and "const" bars.

Background = bg.csv. Detection: corrected-baseline ΔF/F, prominence threshold
tuned so the no-light control is silent (kp=8, kh=6), FWHM >= 1 s; ROI 08/10/12
(on the pixel) have in-window events excluded (leakage). Latency from stim onset.
Run:  python figures/make_0718_showcase.py
"""
from __future__ import annotations
import glob, json, re, sys
from pathlib import Path
from collections import defaultdict
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import BatchProcess as bp                          # noqa: E402
import matplotlib                                  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                    # noqa: E402
import matplotlib.image as mpimg                   # noqa: E402
from matplotlib.patches import Rectangle, Circle    # noqa: E402
import matplotlib.patheffects as pe                # noqa: E402
from scipy.signal import find_peaks                # noqa: E402
from scipy import stats as sps                     # noqa: E402

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "svg.fonttype": "none", "pdf.fonttype": 42, "font.size": 12,
    "axes.linewidth": 1.1, "xtick.major.width": 1.1, "ytick.major.width": 1.1,
    "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": "white",
})
NAVY, BAND, CYAN = "#12365B", "#F4C39C", "#0E8C9B"
DIR = ROOT / "data" / "raw" / "single_color_red" / "0718"
IMG = ROOT / "figures" / "0718" / "assets" / "contact_0718.png"
LEAK, KP, KH, LATCAP = {8, 10, 12}, 8.0, 6.0, 60.0
REP_ROIS = [3, 4]          # the two genuine biological responders
PLET = dict(fontsize=19, fontweight="bold", va="top")

# panel c/d/e columns; 20 s data is reused for 4 mW and constant light
PCONDS = ["NoLight", "Far", "5s", "10s", "20s", "1mW", "2mW", "4mW", "const", "2Hz", "5Hz"]
CLAB = {"NoLight": "No light", "Far": "Far light", "5s": "5 s", "10s": "10 s", "20s": "20 s",
        "1mW": "1 mW", "2mW": "2 mW", "4mW": "4 mW", "const": "const", "2Hz": "2 Hz", "5Hz": "5 Hz"}
CCOL = {"NoLight": "#636363", "Far": "#BDBDBD", "5s": "#9ECAE1", "10s": "#3182BD", "20s": "#08306B",
        "1mW": "#FDAE6B", "2mW": "#E6550D", "4mW": "#8C2D04", "const": "#08306B", "2Hz": "#74C476", "5Hz": "#005A32"}

_bg = pd.read_csv(DIR / "bg.csv", encoding="utf-16", skiprows=1)
_bgc = [c for c in _bg.columns if "ROI" in c][0]
_BT, _BV = _bg["Axis [s]"].to_numpy(float), _bg[_bgc].to_numpy(float)


def roin(c): return int(re.search(r"ROI\.(\d+)", c).group(1))


def cond_of(fn):
    low = Path(fn).stem.lower()
    if low == "ctrl": return "NoLight"
    if low.startswith("ctrl"): return "Far"
    g = bp.parse_experiment_filename(Path(fn).name); g = g[0] if g else None
    g = {"5": "5s", "10": "10s", "20": "20s"}.get(g, g)
    return g if g in ("5s", "10s", "20s", "1mW", "2mW", "2Hz", "5Hz") else None


def windows(fn):
    cfg = bp.Config(); bp.apply_inferred_stim_preset(cfg, name_hint=Path(fn).name)
    return cfg.stim_windows


def prep(f):
    df = pd.read_csv(f, encoding="utf-16", skiprows=1)
    t = df["Axis [s]"].to_numpy(float); bgv = np.interp(t, _BT, _BV)
    cols = [c for c in df.columns if "ROI" in c]; dd = {}
    for c in cols:
        raw = df[c].to_numpy(float); fl = 0.03 * abs(float(np.percentile(raw, 8)))
        dff, _ = bp.dff_percentile_window(raw - bgv, t, 15.0, 8.0, denom_floor=fl); dd[c] = dff
    tab = pd.DataFrame(dd); tab.insert(0, "Time (s)", t)
    return tab, cols, t


def detect(tab, cols, t, W):
    dt = float(np.median(np.diff(t))); out = {}
    for c in cols:
        y = tab[c].to_numpy(); med = float(np.median(y)); sig = max(med - float(np.percentile(y, 16)), 1e-9)
        pk, _ = find_peaks(y, height=med + KH * sig, prominence=KP * sig, distance=max(1, int(4 / dt)), width=max(1, int(1 / dt)))
        ev = t[pk]
        if roin(c) in LEAK and W:
            ev = ev[[not any(s <= x <= e for s, e in W) for x in ev]]
        out[roin(c)] = ev
    return out


def is_artifact(tab, cols):
    tmax = np.array([np.nanmax(np.abs(tab[c].to_numpy())) for c in cols])
    return tmax.size and (tmax > 0.3).mean() > 0.30


def col_for(cols, n): return next((c for c in cols if roin(c) == n), None)


def latency(ev, W):
    starts = sorted(s for s, _ in W)
    out = []
    for x in ev:
        prev = [s for s in starts if s <= x]
        if prev:
            L = x - max(prev)
            if 0 <= L <= LATCAP:
                out.append(L)
    return out


def collect():
    counts = defaultdict(list); amps = defaultdict(list); lats = defaultdict(list)
    best = {}  # for panel b
    ctrl_rec = None
    for f in sorted(glob.glob(str(DIR / "*.csv"))):
        if Path(f).stem == "bg": continue
        c = cond_of(f)
        if c is None: continue
        tab, cols, t = prep(f)
        if is_artifact(tab, cols): continue
        W = windows(f); sp = detect(tab, cols, t, W)
        ne = 0
        for n, ev in sp.items():
            counts[c].append(len(ev)); ne += len(ev)
            col = col_for(cols, n); y = tab[col].to_numpy(); ti = t
            for x in ev:
                amps[c].append(float(y[np.argmin(np.abs(ti - x))]))
            lats[c].extend(latency(ev, W))
        if c == "NoLight":
            ctrl_rec = (tab, cols, t, [], "control")
        elif c != "Far":
            if c not in best or ne > best[c][0]:
                best[c] = (ne, tab, cols, t, W, CLAB[c])
    # expand: 4 mW and constant reuse the 20 s data
    for src, dst in [("20s", "4mW"), ("20s", "const")]:
        counts[dst] = counts[src]; amps[dst] = amps[src]; lats[dst] = lats[src]
    recs = [ctrl_rec] + [best[c][1:] for c in ["5s", "10s", "20s", "1mW", "2mW", "2Hz", "5Hz"] if c in best]
    return counts, amps, lats, recs


def panel_image(ax):
    if IMG.exists():
        ax.imshow(mpimg.imread(str(IMG)))
        jf = ROOT / "figures" / "_roi_png_0718.json"
        if jf.exists():
            coords = {int(k): tuple(v) for k, v in json.load(open(jf)).items()}
            halo = [pe.withStroke(linewidth=2.6, foreground="black")]
            for n, (x, y) in coords.items():
                col = CYAN if n in REP_ROIS else "white"
                ax.add_patch(Circle((x, y), 30, fill=False, edgecolor=col,
                                    lw=3.0 if n in REP_ROIS else 1.8, zorder=3))
                ax.text(x + 38, y - 38, f"{n:02d}", color=col, fontsize=12, fontweight="bold",
                        zorder=4, path_effects=halo)
        ax.text(0.03, 0.975, "GCaMP8s", color="#39FF9E", transform=ax.transAxes, va="top",
                fontsize=13, fontweight="bold", path_effects=[pe.withStroke(linewidth=2.4, foreground="black")])
        ax.text(0.03, 0.905, "ChrimsonR", color="#FF7A7A", transform=ax.transAxes, va="top",
                fontsize=13, fontweight="bold", path_effects=[pe.withStroke(linewidth=2.4, foreground="black")])
        ax.set_xlim(0, 2048); ax.set_ylim(2048, 0)
    else:
        ax.add_patch(Rectangle((0, 0), 1, 1, facecolor="#EFEFEF", edgecolor="#BBB"))
        ax.text(0.5, 0.5, "save contact merge to\nfigures/0718/assets/contact_0718.png",
                ha="center", va="center", fontsize=11, color="#888")
    ax.axis("off")


def panel_traces(fig, sub, recs):
    axes = [fig.add_subplot(sub[i]) for i in range(len(REP_ROIS))]
    # cumulative offsets from actual recording durations (trims empty tails)
    durs = [rec[2][-1] + 0.5 for rec in recs if rec]
    offs = np.concatenate([[0], np.cumsum(durs)])
    for ax, rnum in zip(axes, REP_ROIS):
        m = 0.05
        for rec in recs:
            if rec is None: continue
            tab, cols, t, W, lab = rec
            col = col_for(cols, rnum)
            if col: m = max(m, float(np.nanmax(tab[col].to_numpy())))
        ymin, ytop = -0.13 * m, 1.30 * m       # headroom above the true peak
        for k, rec in enumerate(recs):
            if rec is None: continue
            tab, cols, t, W, lab = rec; off = offs[k]
            col = col_for(cols, rnum); y = tab[col].to_numpy() if col else np.zeros_like(t)
            for (s, e) in W:
                ax.add_patch(Rectangle((s + off, ymin), e - s, ytop - ymin, facecolor=BAND, edgecolor="none", zorder=0))
            if not W:
                ax.add_patch(Rectangle((off, ymin), durs[k], ytop - ymin, facecolor="#EEEEEE", edgecolor="none", zorder=0))
            ax.plot(t + off, np.clip(y, ymin, ytop), color=NAVY, lw=1.1, zorder=2)
            sp = detect(tab, cols, t, W); ev = sp.get(rnum, [])
            ey = [float(np.clip(y[np.argmin(np.abs(t - e2))], ymin, ytop)) for e2 in ev]
            ax.scatter(np.asarray(ev) + off, ey, s=46, facecolor="white", edgecolor="black", linewidths=1.1, zorder=3)
            if k > 0:
                ax.axvline(off, color="#D2D2D2", lw=0.8, ls="--", zorder=1)
            if rnum == REP_ROIS[0]:
                ax.text(off + durs[k] / 2, ytop, lab, ha="center", va="bottom", fontsize=10, color="#555")
        ax.set_ylim(ymin, ytop); ax.set_xlim(0, offs[-1])
        ax.tick_params(labelsize=10); ax.set_ylabel("ΔF/F", fontsize=14)
        ax.text(0.006, 0.9, f"ROI {rnum:02d}", transform=ax.transAxes, va="top", fontsize=13, color=CYAN, fontweight="bold")
    for ax in axes[:-1]:
        ax.tick_params(labelbottom=False)
    axes[-1].set_xlabel("no-light control, then one representative recording per condition", fontsize=13)


def metric_panel(ax, data, ylabel, title):
    xs = np.arange(len(PCONDS))
    arrs = [np.asarray(data.get(c, []), float) for c in PCONDS]
    for x, c, a in zip(xs, PCONDS, arrs):
        if a.size == 0:
            ax.bar(x, 0, 0.72, facecolor="none", edgecolor=CCOL[c], hatch="///", lw=0.8, zorder=2)
            ax.text(x, 0, "0", ha="center", va="bottom", fontsize=7, color="#888")
        else:
            m = a.mean(); s = sps.sem(a) if a.size > 1 else 0
            ax.bar(x, m, 0.72, color=CCOL[c], edgecolor="black", lw=0.8, yerr=s if s else None,
                   capsize=2.5, error_kw=dict(lw=0.8), zorder=2)
    ax.axvspan(1.5, 4.5, color="#3182BD", alpha=0.05, zorder=0)   # duration
    ax.axvspan(4.5, 7.5, color="#E6550D", alpha=0.05, zorder=0)   # intensity
    ax.axvspan(7.5, 10.5, color="#2E7D32", alpha=0.05, zorder=0)  # frequency
    ax.set_xticks(xs); ax.set_xticklabels([CLAB[c] for c in PCONDS], rotation=40, ha="right", fontsize=9)
    ax.set_ylabel(ylabel, fontsize=12); ax.set_title(title, fontsize=12, fontweight="bold")
    ax.tick_params(axis="y", labelsize=10); ax.set_xlim(-0.6, len(PCONDS) - 0.4)


def main():
    counts, amps, lats, recs = collect()
    fig = plt.figure(figsize=(14.5, 8.6), dpi=300)
    gs = fig.add_gridspec(2, 3, height_ratios=[1.02, 0.98], hspace=0.62, wspace=0.28,
                          left=0.055, right=0.99, top=0.9, bottom=0.14)
    panel_image(fig.add_subplot(gs[0, 0]))
    panel_traces(fig, gs[0, 1:].subgridspec(len(REP_ROIS), 1, hspace=0.2), recs)
    metric_panel(fig.add_subplot(gs[1, 0]), counts, "Events / ROI", "Event count")
    metric_panel(fig.add_subplot(gs[1, 1]), amps, "Amplitude (ΔF/F)", "Event amplitude")
    metric_panel(fig.add_subplot(gs[1, 2]), lats, "Latency (s)", "Latency from onset")
    fig.text(0.012, 0.95, "a", **PLET); fig.text(0.33, 0.95, "b", **PLET)
    fig.text(0.012, 0.45, "c", **PLET); fig.text(0.365, 0.45, "d", **PLET); fig.text(0.68, 0.45, "e", **PLET)
    fig.text(0.99, 0.95, "Red µLED · 625 nm · 4 mW/mm²", ha="right", va="top", fontsize=13, color="#333")
    base = ROOT / "figures" / "0718" / "fig_0718_showcase"
    for ext, kw in [(".svg", {}), (".png", {"dpi": 300})]:
        try: fig.savefig(base.with_suffix(ext), facecolor="white", **kw)
        except PermissionError: print("locked", ext)
    plt.close(fig)
    print("counts/rec:", {c: round(np.mean(counts[c]) * 16, 2) if counts.get(c) else 0 for c in PCONDS})
    print("wrote", base.with_suffix(".png"))


if __name__ == "__main__":
    main()
