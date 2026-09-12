"""F5: accepted path-method contrasts and their frozen bootstrap intervals."""
import csv
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import P6_RESULTS, publication_style, save_figure  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402


FAMILIES = ("BB84", "BV", "EDC", "HS", "QRNG", "XOR")
CONTRASTS = ("G/F", "F/R", "R/U", "G/U")
GROUPS = ("all", "1dpu_t8", "4dpu_t8")
TITLES = (
    ("FLOP-guided search", "greedy"),
    ("Cost-model reranking", "FLOP-guided search"),
    ("UPMEM-guided search", "cost-model reranking"),
    ("UPMEM-guided search", "greedy"),
)


def main():
    with (P6_RESULTS / "readout/aggregates.csv").open(newline="", encoding="utf-8") as source:
        aggregate_rows = list(csv.DictReader(source))
    with (P6_RESULTS / "readout/contrasts.csv").open(newline="", encoding="utf-8") as source:
        cell_rows = list(csv.DictReader(source))

    aggregates, cells = {}, {}
    for rows, target, value_field in (
        (aggregate_rows, aggregates, "family_balanced_geometric_ratio"),
        (cell_rows, cells, "ratio_of_medians"),
    ):
        for row in rows:
            if row["metric"] != "session_inclusive_s" or row["contrast"] not in CONTRASTS:
                continue
            key = ((row["group"], row["contrast"]) if target is aggregates
                   else (row["family"], row["topology_id"], row["contrast"]))
            if key in target:
                raise ValueError(f"Duplicate path-selection contrast: {key}")
            ratio, low, high = (float(row[field]) for field in
                                (value_field, "paired_bootstrap_low", "paired_bootstrap_high"))
            if not all(math.isfinite(v) and v > 0 for v in (ratio, low, high)) or low > high:
                raise ValueError(f"Invalid path-selection ratio/interval: {key}")
            if target is aggregates:
                expected_cells = 12 if row["group"] == "all" else 6
                if int(row["cells"]) != expected_cells or int(row["families"]) != 6:
                    raise ValueError(f"Unexpected path-selection aggregate membership: {key}")
            target[key] = (ratio, low, high)
    if set(aggregates) != {(g, c) for g in GROUPS for c in CONTRASTS}:
        raise ValueError("Missing or unexpected path-selection aggregate contrasts")
    if set(cells) != {(f, t, c) for f in FAMILIES for t in GROUPS[1:] for c in CONTRASTS}:
        raise ValueError("Missing or unexpected path-selection circuit/topology contrasts")

    publication_style()
    fig, axes = plt.subplots(2, 2, figsize=(160 / 25.4, 165 / 25.4),
                             sharex=True, sharey=True, layout="constrained")
    for letter, ax, contrast, (method, reference) in zip("abcd", axes.flat, CONTRASTS, TITLES):
        labels = ["Overall", "1 DPU overall", "4 DPUs overall"]
        values = [aggregates[g, contrast] for g in GROUPS]
        colors = ["#333333", "#0072B2", "#D55E00"]
        markers = ["D", "o", "s"]
        for family in FAMILIES:
            for topology, short, color, marker in (
                ("1dpu_t8", "1 DPU", "#0072B2", "o"),
                ("4dpu_t8", "4 DPUs", "#D55E00", "s"),
            ):
                labels.append(f"{family} · {short}")
                values.append(cells[family, topology, contrast])
                colors.append(color)
                markers.append(marker)
        positions = list(range(14, -1, -1))
        for index, (y, (ratio, low, high), color, marker) in enumerate(zip(positions, values, colors, markers)):
            # Draw the actual stored interval, even if it does not contain the point estimate.
            ax.hlines(y, low, high, color=color, linewidth=1.3 if index == 0 else 0.7, zorder=3)
            ax.plot(ratio, y, marker=marker, color=color, markersize=5.5 if index == 0 else 3,
                    linestyle="none", zorder=4)
        ax.axhspan(13.5, 14.5, color="#eeeeee", linewidth=0, zorder=0)
        ax.text(0.97, 14, f"{values[0][0]:.3f}×", transform=ax.get_yaxis_transform(),
                ha="right", va="center", fontsize=8, fontweight="bold")
        ax.axvline(1, color="#888888", linestyle="--", linewidth=0.55, zorder=2)
        ax.axhline(11.5, color="#cccccc", linewidth=0.5, zorder=1)
        ax.set_yticks(positions, labels=labels)
        ax.tick_params(axis="y", labelleft=True, length=0, labelsize=7)
        ax.get_yticklabels()[0].set_fontweight("bold")
        ax.set_ylim(-0.6, 14.6)
        ax.set_xlim(0.5, 3.0)
        ax.set_xticks([0.5, 1, 1.5, 2, 2.5, 3], labels=["0.5", "1", "1.5", "2", "2.5", "3"])
        ax.tick_params(axis="x", labelbottom=True)
        ax.minorticks_off()
        ax.set_title(rf"$\mathbf{{{letter}}}$  {method}" + f"\nReference: {reference}",
                     loc="left", fontsize=8, pad=8)
        ax.grid(axis="x", color="#e3e3e3", linewidth=0.45, zorder=0)

    handles = [Line2D([], [], color=color, marker=marker, linestyle="none", markersize=4, label=label)
               for color, marker, label in (("#333333", "D", "Overall"),
                                             ("#0072B2", "o", "1 DPU"),
                                             ("#D55E00", "s", "4 DPUs"))]
    fig.legend(handles=handles, loc="outside upper center", ncol=3, frameon=False,
               fontsize=7.5, title="Float32 · 8 tasklets per DPU", title_fontsize=8)
    fig.supxlabel("Execution speedup (×; higher is faster)", fontsize=8)
    save_figure(fig, "fig05_path_selection")


if __name__ == "__main__":
    main()
