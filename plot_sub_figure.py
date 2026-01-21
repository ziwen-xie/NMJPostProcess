from __future__ import annotations
import math
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.image as mpimg


TARGET_FILENAMES = {
    "plot_all": "deltaF_F_plot_all.png",
    "spiking_only": "deltaF_F_spiking_only.png",
}


def find_target_images(base_dir: Path):
    results = {"plot_all": [], "spiking_only": []}
    for kind, filename in TARGET_FILENAMES.items():
        for p in base_dir.rglob(filename):
            if p.is_file():
                label = p.parent.name
                results[kind].append((p, label))
        results[kind].sort(key=lambda t: (t[1].lower(), str(t[0]).lower()))
    return results


def _wrap_label(text: str, max_chars: int = 24) -> str:
    if len(text) <= max_chars:
        return text
    return "\n".join([text[i:i+max_chars] for i in range(0, len(text), max_chars)])


def build_composite(items, title, ncols=3, max_title_chars=24):
    n = len(items)
    if n == 0:
        fig = plt.figure(figsize=(8, 3))
        fig.suptitle(f"{title} — no images found", fontsize=14)
        ax = fig.add_subplot(111)
        ax.axis("off")
        ax.text(0.5, 0.5, "No matching images", ha="center", va="center", fontsize=12)
        return fig

    nrows = math.ceil(n / ncols)
    fig, axes = plt.subplots(
        nrows=nrows, ncols=ncols,
        figsize=(4 * ncols, 3 * nrows),
        squeeze=False
    )
    fig.suptitle(title, fontsize=16, y=0.995)

    for i, (img_path, label) in enumerate(items):
        r, c = divmod(i, ncols)
        ax = axes[r][c]
        try:
            img = mpimg.imread(str(img_path))
            ax.imshow(img)
        except Exception as e:
            ax.text(0.5, 0.5, f"Error loading\n{img_path.name}\n{e}", ha="center", va="center", fontsize=9)
            ax.set_facecolor((0.95, 0.95, 0.95))
        ax.set_xticks([]); ax.set_yticks([])
        ax.set_title(_wrap_label(label, max_title_chars), fontsize=10)

    # hide empty subplots
    for j in range(i + 1, nrows * ncols):
        r, c = divmod(j, ncols)
        axes[r][c].axis("off")

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    return fig


def main():
    base_dir = Path(r"C:\Users\jerse\PycharmProjects\NMJPostProcess\batch_results")
    found = find_target_images(base_dir)

    fig_all = build_composite(found["plot_all"], "deltaF/F — All ROIs")
    fig_all.savefig(base_dir / "combined_deltaF_F_plot_all.png", dpi=200, bbox_inches="tight")
    plt.close(fig_all)

    fig_spk = build_composite(found["spiking_only"], "deltaF/F — Spiking Only")
    fig_spk.savefig(base_dir / "combined_deltaF_F_spiking_only.png", dpi=200, bbox_inches="tight")
    plt.close(fig_spk)

    print("Done!")
    print(f"Found {len(found['plot_all'])} 'plot_all' images.")
    print(f"Found {len(found['spiking_only'])} 'spiking_only' images.")


if __name__ == "__main__":
    main()