"""F4: physical float32/int8 execution-time ratios at matched DPU/tasklet counts."""
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
F32 = "split_complex_float32_v1"
INT8 = "complex_int8_shared_scale_v1"


def main():
    with (V4_READOUT / "Q.csv").open(newline="", encoding="utf-8") as source:
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
            dpu_label, tasklet_label, policy = row["point"].split("/")
            dpus, tasklets = int(dpu_label.removeprefix("D")), int(tasklet_label.removeprefix("T"))
            key = (dpus, tasklets, policy)
            if row["view"] != "Q" or row["point"] != f"D{dpus}/T{tasklets}/{policy}" or key in timings:
                raise ValueError(f"Unexpected or duplicate quantization point: {case}/{row['point']}")
            if int(row["count"]) != 5:
                raise ValueError(f"Expected five measured blocks: {case}/{row['point']}")
            median = float(row["median_prepared_call_s"])
            if not math.isfinite(median) or median <= 0:
                raise ValueError(f"Invalid median: {case}/{row['point']}")
            timings[key] = median
        if set(timings) != {(d, t, p) for d in DPUS for t in (8, 24) for p in (F32, INT8)}:
            raise ValueError(f"Incomplete or unexpected matched topologies/policies for {case}")

        for tasklets, color, marker, linestyle in (
            (8, "#0072B2", "o", "-"),
            (24, "#D55E00", "s", "--"),
        ):
            ratios = [timings[d, tasklets, F32] / timings[d, tasklets, INT8] for d in DPUS]
            curve, = ax.plot(DPUS, ratios, color=color, marker=marker, linestyle=linestyle,
                             markersize=3, linewidth=1, zorder=3,
                             label=f"T{tasklets} ({tasklets} tasklets)")
            if letter == "a":
                legend_handles.append(curve)

        ax.axhline(1, color="#888888", linestyle="--", linewidth=0.55, zorder=2)
        ax.set_title(rf"$\mathbf{{{letter}}}$  {title}", loc="left", pad=7)
        ax.set_title(f"{qubits} qubits", loc="right", fontsize=7.5, pad=7)
        ax.set_xscale("log", base=2)
        ax.set_xticks(DPUS, labels=[str(d) for d in DPUS])
        ax.set_xlim(0.8, 80)
        ax.set_ylim(0.8, 2.3)
        ax.set_yticks([1, 1.25, 1.5, 1.75, 2, 2.25])
        ax.minorticks_off()
        ax.grid(axis="y", color="#e3e3e3", linewidth=0.45, zorder=0)

    fig.legend(handles=legend_handles, loc="outside upper center", ncol=2,
               frameon=False, fontsize=7.5, handlelength=2.2, columnspacing=2)
    fig.supxlabel("Physical DPUs $D$ (matched topology; logarithmic scale)", fontsize=8)
    fig.supylabel("Runtime ratio: float32 / int8 (×)", fontsize=8)
    save_figure(fig, "fig04_quantization")


if __name__ == "__main__":
    main()
