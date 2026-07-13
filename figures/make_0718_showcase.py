"""0718 academic data-showcase figure (journal style), matching the 0714 layout.

  a  contact FOV (placeholder = the LAS X two-colour merge the user supplied;
     save it to figures/0718/assets/contact_0718.png). LED pixel is by ROI 08/10/12.
  b  ΔF/F traces: near-pixel leakage ROI (10) kept separate from biological
     responders (03, 04); no-light control + one representative recording per
     condition (5s/10s/20s/1mW/2mW/2Hz/5Hz), concatenated.
  c  per-condition event rate (duration / intensity / frequency vs controls).

Background = bg.csv (the ROI.00 corner). Detection: corrected-baseline ΔF/F,
prominence threshold tuned so the no-light control is silent (kp=8, kh=6), FWHM
>= 1 s; ROI 08/10/12 (on the pixel) have in-window events excluded (leakage).
Run:  python figures/make_0718_showcase.py
"""
from __future__ import annotations
import glob, re, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import BatchProcess as bp                          # noqa: E402
import matplotlib                                  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                    # noqa: E402
import matplotlib.image as mpimg                   # noqa: E402
from matplotlib.patches import Rectangle           # noqa: E402
from scipy.signal import find_peaks                # noqa: E402

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "svg.fonttype": "none", "pdf.fonttype": 42, "font.size": 12,
    "axes.linewidth": 1.1, "xtick.major.width": 1.1, "ytick.major.width": 1.1,
    "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": "white",
})
NAVY, STIM, GREY, BAND = "#12365B", "#D55E00", "#8A8A8A", "#F4C39C"
CYAN, LEAKC = "#0E8C9B", "#E8871E"
DIR = ROOT / "data" / "raw" / "single_color_red" / "0718"
IMG = ROOT / "figures" / "0718" / "assets" / "contact_0718.png"
LEAK, KP, KH = {8, 10, 12}, 8.0, 6.0
LEAK_ROW, BIO_ROWS = 10, [3, 4]
PLET = dict(fontsize=19, fontweight="bold", va="top")
# per-condition columns for panel c
CONDS = ["NoLight", "Far", "5s", "10s", "20s", "1mW", "2mW", "2Hz", "5Hz"]
CLAB = {"NoLight": "No light", "Far": "Far light", "5s": "5 s", "10s": "10 s",
        "20s": "20 s", "1mW": "1 mW", "2mW": "2 mW", "2Hz": "2 Hz", "5Hz": "5 Hz"}
CCOL = {"NoLight": "#636363", "Far": "#BDBDBD", "5s": "#9ECAE1", "10s": "#3182BD",
        "20s": "#08306B", "1mW": "#FDAE6B", "2mW": "#E6550D", "2Hz": "#74C476", "5Hz": "#005A32"}

_bg = pd.read_csv(DIR / "bg.csv", encoding="utf-16", skiprows=1)
_bgc = [c for c in _bg.columns if "ROI" in c][0]
_BT, _BV = _bg["Axis [s]"].to_numpy(float), _bg[_bgc].to_numpy(float)


def roin(c): return int(re.search(r"ROI\.(\d+)", c).group(1))


def cond_of(fn):
    low = Path(fn).stem.lower()
    if low == "ctrl":
        return "NoLight"
    if low.startswith("ctrl"):
        return "Far"
    g = bp.parse_experiment_filename(Path(fn).name)
    g = g[0] if g else None
    g = {"5": "5s", "10": "10s", "20": "20s"}.get(g, g)
    return g if g in CONDS else None


def windows(fn):
    cfg = bp.Config(); bp.apply_inferred_stim_preset(cfg, name_hint=Path(fn).name)
    return cfg.stim_windows


def prep(f):
    df = pd.read_csv(f, encoding="utf-16", skiprows=1)
    t = df["Axis [s]"].to_numpy(float); bgv = np.interp(t, _BT, _BV)
    cols = [c for c in df.columns if "ROI" in c]; dd = {}
    for c in cols:
        raw = df[c].to_numpy(float); fl = 0.03 * abs(float(np.percentile(raw, 8)))
        dff, _ = bp.dff_percentile_window(raw - bgv, t, 15.0, 8.0, denom_floor=fl)
        dd[c] = dff
    tab = pd.DataFrame(dd); tab.insert(0, "Time (s)", t)
    return tab, cols, t


def detect(tab, cols, t, W):
    dt = float(np.median(np.diff(t))); out = {}
    for c in cols:
        y = tab[c].to_numpy(); med = float(np.median(y)); sig = max(med - float(np.percentile(y, 16)), 1e-9)
        pk, _ = find_peaks(y, height=med + KH * sig, prominence=KP * sig,
                           distance=max(1, int(4 / dt)), width=max(1, int(1 / dt)))
        ev = t[pk]
        if roin(c) in LEAK and W:
            ev = ev[[not any(s <= x <= e for s, e in W) for x in ev]]
        out[roin(c)] = ev
    return out


def is_artifact(tab, cols):
    tmax = np.array([np.nanmax(np.abs(tab[c].to_numpy())) for c in cols])
    return tmax.size and (tmax > 0.3).mean() > 0.30


def col_for(cols, n):
    return next((c for c in cols if roin(c) == n), None)


# ---------------------------------------------------------------- panel c data
def condition_rates():
    rate = {}
    for c in CONDS:
        rate[c] = []
    for f in sorted(glob.glob(str(DIR / "*.csv"))):
        if Path(f).stem == "bg":
            continue
        c = cond_of(f)
        if c is None:
            continue
        tab, cols, t = prep(f)
        if is_artifact(tab, cols):
            continue
        W = windows(f); sp = detect(tab, cols, t, W)
        rate[c].append(sum(len(v) for v in sp.values()))
    return rate


# ---------------------------------------------------------------- panel b recs
def pick_recordings():
    """no-light control + the highest-event recording of each stim condition."""
    best = {}
    ctrl = None
    for f in sorted(glob.glob(str(DIR / "*.csv"))):
        if Path(f).stem == "bg":
            continue
        c = cond_of(f)
        if c is None:
            continue
        tab, cols, t = prep(f)
        if is_artifact(tab, cols):
            continue
        W = windows(f); sp = detect(tab, cols, t, W)
        ne = sum(len(v) for v in sp.values())
        if c == "NoLight":
            ctrl = (tab, cols, t, [], "control")
        elif c != "Far":
            if c not in best or ne > best[c][0]:
                best[c] = (ne, tab, cols, t, W, c)
    recs = [ctrl]
    for c in ["5s", "10s", "20s", "1mW", "2mW", "2Hz", "5Hz"]:
        if c in best:
            _, tab, cols, t, W, name = best[c]
            recs.append((tab, cols, t, W, CLAB[c]))
    return recs


def panel_image(ax):
    if IMG.exists():
        ax.imshow(mpimg.imread(str(IMG)))
    else:
        ax.add_patch(Rectangle((0, 0), 1, 1, facecolor="#EFEFEF", edgecolor="#BBB"))
        ax.text(0.5, 0.5, "contact image\n(save merge to\nfigures/0718/assets/\ncontact_0718.png)",
                ha="center", va="center", fontsize=12, color="#888")
    ax.axis("off")


def panel_traces(fig, sub, recs):
    T = 156.0
    axes = [fig.add_subplot(sub[i]) for i in range(3)]
    rows = [(LEAK_ROW, LEAKC, (-0.06, 0.30), False), (BIO_ROWS[0], CYAN, (-0.09, 0.55), True),
            (BIO_ROWS[1], CYAN, (-0.06, 0.30), True)]
    for ax, (rnum, colr, (ymin, ytop), mark) in zip(axes, rows):
        for k, rec in enumerate(recs):
            if rec is None:
                continue
            tab, cols, t, W, lab = rec
            off = k * T
            col = col_for(cols, rnum); y = tab[col].to_numpy() if col else np.zeros_like(t)
            for (s, e) in W:
                ax.add_patch(Rectangle((s + off, ymin), e - s, ytop - ymin, facecolor=BAND, edgecolor="none", zorder=0))
            if not W:
                ax.add_patch(Rectangle((off, ymin), T, ytop - ymin, facecolor="#EEEEEE", edgecolor="none", zorder=0))
            ax.plot(t + off, np.clip(y, ymin, ytop), color=NAVY, lw=1.1, zorder=2)
            if mark and col is not None:
                W2 = windows("x") if False else W
                sp = detect(tab, cols, t, W2)
                ev = sp.get(rnum, [])
                ey = [float(np.clip(y[np.argmin(np.abs(t - e2))], ymin, ytop)) for e2 in ev]
                ax.scatter(np.asarray(ev) + off, ey, s=46, facecolor="white", edgecolor="black", linewidths=1.1, zorder=3)
            if k > 0:
                ax.axvline(off, color="#D2D2D2", lw=0.8, ls="--", zorder=1)
            if rnum == LEAK_ROW:
                ax.text(off + T / 2, ytop, lab, ha="center", va="bottom", fontsize=10, color="#555")
        ax.set_ylim(ymin, ytop); ax.set_xlim(0, len(recs) * T)
        ax.tick_params(labelsize=10); ax.set_ylabel("ΔF/F", fontsize=14)
        tagc = LEAKC if rnum == LEAK_ROW else CYAN
        ax.text(0.006, 0.92, f"ROI {rnum:02d}", transform=ax.transAxes, va="top", fontsize=13, color=tagc, fontweight="bold")
    axes[0].set_facecolor("#FCF3E6")
    for ax in axes[:2]:
        ax.tick_params(labelbottom=False)
    axes[-1].set_xlabel("no-light control, then one representative recording per condition", fontsize=13)


def panel_conditions(ax, rate):
    xs = np.arange(len(CONDS))
    means = [np.mean(rate[c]) if rate[c] else 0.0 for c in CONDS]
    from scipy import stats as sps
    sems = [sps.sem(rate[c]) if len(rate[c]) > 1 else 0.0 for c in CONDS]
    for x, c, m, s in zip(xs, CONDS, means, sems):
        ax.bar(x, m, 0.7, color=CCOL[c], edgecolor="black", lw=0.9,
               yerr=s if s else None, capsize=3, error_kw=dict(lw=0.9), zorder=2)
    ax.set_xticks(xs); ax.set_xticklabels([CLAB[c] for c in CONDS], rotation=32, ha="right", fontsize=11)
    ax.set_ylabel("Events / recording", fontsize=14)
    ax.tick_params(axis="y", labelsize=11)
    # group brackets
    ax.axvspan(1.5, 4.5, color="#3182BD", alpha=0.05, zorder=0)
    ax.axvspan(4.5, 6.5, color="#E6550D", alpha=0.05, zorder=0)
    ax.axvspan(6.5, 8.5, color="#2E7D32", alpha=0.05, zorder=0)
    ax.set_xlim(-0.6, len(CONDS) - 0.4)


def main():
    rate = condition_rates()
    recs = pick_recordings()
    fig = plt.figure(figsize=(13.4, 8.2), dpi=300)
    gs = fig.add_gridspec(2, 2, width_ratios=[1.0, 1.6], height_ratios=[1.08, 0.92],
                          hspace=0.5, wspace=0.24, left=0.06, right=0.985, top=0.9, bottom=0.15)
    panel_image(fig.add_subplot(gs[0, 0]))
    panel_conditions(fig.add_subplot(gs[1, 0]), rate)
    panel_traces(fig, gs[:, 1].subgridspec(3, 1, hspace=0.2), recs)
    fig.text(0.012, 0.95, "a", **PLET)
    fig.text(0.43, 0.95, "b", **PLET)
    fig.text(0.012, 0.47, "c", **PLET)
    fig.text(0.985, 0.95, "Red µLED · 625 nm · 4 mW/mm²", ha="right", va="top", fontsize=14, color="#333")
    base = ROOT / "figures" / "0718" / "fig_0718_showcase"
    for ext, kw in [(".svg", {}), (".png", {"dpi": 300})]:
        try: fig.savefig(base.with_suffix(ext), facecolor="white", **kw)
        except PermissionError: print("locked", ext)
    plt.close(fig)
    print("condition events/rec:", {c: round(np.mean(rate[c]), 2) if rate[c] else 0 for c in CONDS})
    print("wrote", base.with_suffix(".png"))


if __name__ == "__main__":
    main()
