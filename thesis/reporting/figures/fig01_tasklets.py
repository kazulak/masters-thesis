"""F1: per-family tasklet speedup from the frozen prepared-call medians in T.csv."""
import csv
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import V4_READOUT, publication_style, save_figure  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402


CASES = (
    ("bb84_n18", "BB84", 18),
    ("bv_n18", "BV", 18),
    ("edc_n17", "EDC", 17),
    ("hs_n18", "HS", 18),
    ("qrng_n18", "QRNG", 18),
    ("xor_n18", "XOR", 18),
)


def main():
    with (V4_READOUT / "T.csv").open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))

    publication_style()
    fig, axes = plt.subplots(2, 3, figsize=(160 / 25.4, 105 / 25.4),
                             sharex=True, sharey=True, layout="constrained")
    for letter, ax, (case, title, qubits) in zip("abcdef", axes.flat, CASES):
        timings = {}
        for row in rows:
            if row["case_id"] != case:
                continue
            tasklets = int(row["point"].removeprefix("T"))
            median = float(row["median_prepared_call_s"])
            mad = float(row["raw_mad"])
            if row["view"] != "T" or row["point"] != f"T{tasklets}" or tasklets in timings:
                raise ValueError(f"Unexpected or duplicate tasklet point for {case}: {row['point']}")
            if int(row["count"]) != 5:
                raise ValueError(f"Expected five measured blocks: {case}/T{tasklets}")
            if not (math.isfinite(median) and math.isfinite(mad) and median > 0 and 0 <= mad < median):
                raise ValueError(f"Invalid median/MAD: {case}/T{tasklets}")
            timings[tasklets] = (median, mad)
        if set(timings) != set(range(1, 25)):
            raise ValueError(f"Expected exactly T1..T24 for {case}")

        baseline = timings[1][0]
        tasklets = list(range(1, 25))
        speedups, lower_errors, upper_errors = [], [], []
        for tasklet in tasklets:
            median, mad = timings[tasklet]
            speedup = baseline / median
            # Descriptive runtime dispersion with fixed T1 normalization, not a CI.
            # Self-normalization at T1 is exactly one, with zero whisker.
            low = baseline / (median + mad) if tasklet != 1 else 1.0
            high = baseline / (median - mad) if tasklet != 1 else 1.0
            speedups.append(speedup)
            lower_errors.append(speedup - low)
            upper_errors.append(high - speedup)

        ax.errorbar(tasklets, speedups, yerr=[lower_errors, upper_errors],
                    color="#0072B2", marker="o", markersize=2.4, linewidth=1.0,
                    elinewidth=0.55, capsize=1.5, capthick=0.55, zorder=3)
        ax.axhline(1, color="#888888", linestyle="--", linewidth=0.55, zorder=2)
        ax.set_title(rf"$\mathbf{{{letter}}}$  {title}", loc="left", pad=7)
        ax.set_title(f"{qubits} qubits", loc="right", fontsize=7.5, pad=7)
        ax.set_xlim(0.5, 24.5)
        ax.set_ylim(0.5, 5.0)
        ax.set_xticks([1, 4, 8, 12, 16, 20, 24])
        ax.set_yticks([1, 2, 3, 4, 5])
        ax.grid(axis="y", color="#e3e3e3", linewidth=0.45, zorder=0)

    fig.supxlabel("Tasklets $T$ (one physical DPU)", fontsize=8)
    fig.supylabel("Prepared-call speedup vs T1", fontsize=8)
    save_figure(fig, "fig01_tasklets")


if __name__ == "__main__":
    main()
