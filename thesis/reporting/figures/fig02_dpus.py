"""F2: DPU speedup at matched tasklet counts from the frozen medians in D.csv."""
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
DPUS = (1, 2, 4, 8, 16, 32, 64)


def main():
    with (V4_READOUT / "D.csv").open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))

    publication_style()
    fig, axes = plt.subplots(2, 3, figsize=(160 / 25.4, 110 / 25.4),
                             sharex=True, sharey=True, layout="constrained")
    legend_handles = []
    for letter, ax, (case, title, qubits) in zip("abcdef", axes.flat, CASES):
        timings = {}
        for row in rows:
            if row["case_id"] != case:
                continue
            dpu_label, tasklet_label = row["point"].split("/")
            dpus = int(dpu_label.removeprefix("D"))
            tasklets = int(tasklet_label.removeprefix("T"))
            median = float(row["median_prepared_call_s"])
            mad = float(row["raw_mad"])
            if row["view"] != "D" or row["point"] != f"D{dpus}/T{tasklets}" or (dpus, tasklets) in timings:
                raise ValueError(f"Unexpected or duplicate DPU point for {case}: {row['point']}")
            if int(row["count"]) != 5:
                raise ValueError(f"Expected five measured blocks: {case}/{row['point']}")
            if not (math.isfinite(median) and math.isfinite(mad) and median > 0 and 0 <= mad < median):
                raise ValueError(f"Invalid median/MAD: {case}/{row['point']}")
            timings[dpus, tasklets] = (median, mad)
        if set(timings) != {(d, t) for d in DPUS for t in (8, 24)}:
            raise ValueError(f"Expected D1,2,4,8,16,32,64 at both T8 and T24 for {case}")

        for tasklets, color, marker, linestyle in (
            (8, "#0072B2", "o", "-"),
            (24, "#D55E00", "s", "--"),
        ):
            baseline = timings[1, tasklets][0]
            speedups, lower_errors, upper_errors = [], [], []
            for dpus in DPUS:
                median, mad = timings[dpus, tasklets]
                speedup = baseline / median
                # Descriptive dispersion with a fixed, tasklet-matched D1 median.
                # D1 self-normalizes to one with zero whisker; these are not CIs.
                low = baseline / (median + mad) if dpus != 1 else 1.0
                high = baseline / (median - mad) if dpus != 1 else 1.0
                speedups.append(speedup)
                lower_errors.append(speedup - low)
                upper_errors.append(high - speedup)

            curve = ax.errorbar(DPUS, speedups, yerr=[lower_errors, upper_errors],
                                color=color, marker=marker, linestyle=linestyle,
                                markersize=3, linewidth=1.0, elinewidth=0.55,
                                capsize=1.5, capthick=0.55, zorder=3,
                                label=f"T{tasklets} ({tasklets} tasklets)")
            if letter == "a":
                legend_handles.append(curve)

        ax.axhline(1, color="#888888", linestyle="--", linewidth=0.55, zorder=2)
        ax.set_title(rf"$\mathbf{{{letter}}}$  {title}", loc="left", pad=7)
        ax.set_title(f"{qubits} qubits", loc="right", fontsize=7.5, pad=7)
        ax.set_xscale("log", base=2)
        ax.set_xticks(DPUS, labels=[str(d) for d in DPUS])
        ax.set_xlim(0.8, 80)
        ax.set_ylim(0.8, 3.0)
        ax.set_yticks([1, 1.5, 2, 2.5, 3])
        ax.minorticks_off()
        ax.grid(axis="y", color="#e3e3e3", linewidth=0.45, zorder=0)

    fig.legend(handles=legend_handles, loc="outside upper center", ncol=2,
               frameon=False, fontsize=7.5, handlelength=2.2, columnspacing=2)
    fig.supxlabel("Physical DPUs $D$ (one rank; logarithmic scale)", fontsize=8)
    fig.supylabel("Speedup relative to 1 DPU (×)", fontsize=8)
    save_figure(fig, "fig02_dpus")


if __name__ == "__main__":
    main()
