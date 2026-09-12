"""F5: accepted P6 path-method contrasts and their frozen bootstrap intervals."""
import csv
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import P6_RESULTS, publication_style, save_figure  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402


FAMILIES = ("BB84", "BV", "EDC", "HS", "QRNG", "XOR")
CONTRASTS = ("G/F", "F/R", "R/U", "G/U")
GROUPS = ("all", "1dpu_t8", "4dpu_t8")


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
                raise ValueError(f"Duplicate P6 contrast: {key}")
            ratio, low, high = (float(row[field]) for field in
                                (value_field, "paired_bootstrap_low", "paired_bootstrap_high"))
            if not all(math.isfinite(v) and v > 0 for v in (ratio, low, high)) or low > high:
                raise ValueError(f"Invalid P6 ratio/interval: {key}")
            if target is aggregates:
                expected_cells = 12 if row["group"] == "all" else 6
                if int(row["cells"]) != expected_cells or int(row["families"]) != 6:
                    raise ValueError(f"Unexpected P6 aggregate membership: {key}")
            target[key] = (ratio, low, high)
    if set(aggregates) != {(g, c) for g in GROUPS for c in CONTRASTS}:
        raise ValueError("Missing or unexpected P6 aggregate contrasts")
    if set(cells) != {(f, t, c) for f in FAMILIES for t in GROUPS[1:] for c in CONTRASTS}:
        raise ValueError("Missing or unexpected P6 cell contrasts")

    publication_style()
    fig, axes = plt.subplots(2, 2, figsize=(160 / 25.4, 165 / 25.4),
                             sharey=True, layout="constrained")
    limits = ((0.6, 2.6), (0.94, 1.42), (0.96, 1.10), (0.6, 3.0))
    ticks = ([0.75, 1, 1.5, 2, 2.5], [1, 1.1, 1.2, 1.3, 1.4],
             [0.98, 1, 1.02, 1.04, 1.06, 1.08], [0.75, 1, 1.5, 2, 2.5, 3])
    for letter, ax, contrast, xlim, xticks in zip("abcd", axes.flat, CONTRASTS, limits, ticks):
        labels = ["All (12 cells)", "D1/T8 (6 cells)", "D4/T8 (6 cells)"]
        values = [aggregates[g, contrast] for g in GROUPS]
        colors = ["#333333", "#0072B2", "#D55E00"]
        markers = ["D"] * 3
        for family in FAMILIES:
            for topology, short, color, marker in (
                ("1dpu_t8", "D1", "#0072B2", "o"),
                ("4dpu_t8", "D4", "#D55E00", "s"),
            ):
                labels.append(f"{family} · {short}")
                values.append(cells[family, topology, contrast])
                colors.append(color)
                markers.append(marker)
        positions = list(range(14, -1, -1))
        for index, (y, (ratio, low, high), color, marker) in enumerate(zip(positions, values, colors, markers)):
            # Draw the actual stored interval, even if it does not contain the point estimate.
            ax.hlines(y, low, high, color=color, linewidth=1 if index < 3 else 0.7, zorder=3)
            ax.plot(ratio, y, marker=marker, color=color, markersize=4 if index < 3 else 3,
                    linestyle="none", zorder=4)
        ax.axvline(1, color="#888888", linestyle="--", linewidth=0.55, zorder=2)
        ax.axhline(11.5, color="#cccccc", linewidth=0.5, zorder=1)
        ax.set_yticks(positions, labels=labels)
        ax.tick_params(axis="y", labelleft=True, length=0, labelsize=7)
        ax.set_ylim(-0.6, 14.6)
        ax.set_xscale("log")
        ax.set_xlim(*xlim)
        ax.set_xticks(xticks, labels=[f"{x:g}" for x in xticks])
        ax.minorticks_off()
        ax.set_title(rf"$\mathbf{{{letter}}}$  {contrast}", loc="left", pad=7)
        ax.set_title("P6 primary" if contrast == "R/U" else "P6", loc="right", fontsize=7.5, pad=7)
        ax.grid(axis="x", color="#e3e3e3", linewidth=0.45, zorder=0)

    fig.supxlabel("Session-time ratio: numerator / denominator (×; log scale)\n"
                  "G: greedy · F: FLOP-guided · R: cost-model reranking · U: UPMEM-guided",
                  fontsize=7)
    save_figure(fig, "fig05_path_selection")


if __name__ == "__main__":
    main()
