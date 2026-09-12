"""App03: supplemental matched quantization ratios and final Stress routes."""
import csv
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import V4_READOUT, publication_style, save_figure  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402


CASES = (("stress_n16_l2", "Stress16", 16),
         ("stress_n18_l2", "Stress18", 18),
         ("ghz_n18", "GHZ18", 18))
DPUS = (1, 2, 4, 8, 16, 32, 64)
F32 = "split_complex_float32_v1"
INT8 = "complex_int8_shared_scale_v1"
WIDTHS = (8, 12, 16, 18)
ROUTES = (
    ("upmem_f32", "UPMEM float32", "#0072B2", "o", "-"),
    ("upmem_int8", "UPMEM int8", "#D55E00", "s", "--"),
    ("numpy_f32_p1", "NumPy same-DAG (P1)", "#009E73", "v", "-."),
    ("quest32_p8", "QuEST (P8)", "#CC79A7", "D", "-"),
    ("quest32_p1", "QuEST (P1)", "#666666", "^", ":"),
)


def main():
    with (V4_READOUT / "Q.csv").open(newline="", encoding="utf-8") as source:
        quantization_rows = list(csv.DictReader(source))
    with (V4_READOUT / "S.csv").open(newline="", encoding="utf-8") as source:
        stress_rows = list(csv.DictReader(source))

    publication_style()
    fig, axes = plt.subplots(2, 2, figsize=(160 / 25.4, 145 / 25.4), layout="constrained")
    tasklet_handles = []
    for letter, ax, (case, title, qubits) in zip("abc", axes.flat, CASES):
        timings = {}
        for row in quantization_rows:
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
            # F4 definition: ratio of prepared-call medians at matched D/T.
            ratios = [timings[d, tasklets, F32] / timings[d, tasklets, INT8] for d in DPUS]
            curve, = ax.plot(DPUS, ratios, color=color, marker=marker, linestyle=linestyle,
                             markersize=3, linewidth=1, zorder=3,
                             label=f"T{tasklets} ({tasklets} tasklets)")
            if letter == "a":
                tasklet_handles.append(curve)
        ax.axhline(1, color="#888888", linestyle="--", linewidth=0.55, zorder=2)
        ax.set_title(rf"$\mathbf{{{letter}}}$  {title}", loc="left", pad=7)
        ax.set_title(f"{qubits} qubits", loc="right", fontsize=7.5, pad=7)
        ax.set_xscale("log", base=2)
        ax.set_xticks(DPUS, labels=[str(d) for d in DPUS])
        ax.set_xlim(0.8, 80)
        ax.set_ylim(0.8, 2.9)
        ax.set_yticks([1, 1.5, 2, 2.5])
        ax.minorticks_off()
        ax.set_xlabel("Physical DPUs $D$ (logarithmic scale)")
        ax.set_ylabel("Runtime ratio: float32 / int8 (×)")
        ax.grid(axis="y", color="#e3e3e3", linewidth=0.45, zorder=0)

    timings = {}
    expected = {(f"stress_n{width:02d}_l2", route[0]) for width in WIDTHS for route in ROUTES}
    for row in stress_rows:
        key = (row["case_id"], row["role"])
        if row["view"] != "S" or key in timings or key not in expected:
            raise ValueError(f"Unexpected or duplicate final Stress timing: {key}")
        if int(row["count"]) != 5:
            raise ValueError(f"Expected five measured blocks: {key}")
        median, mad = float(row["median_job_to_state_cached_path_s"]), float(row["raw_mad_cached_s"])
        if not (math.isfinite(median) and math.isfinite(mad) and median > 0 and 0 <= mad < median):
            raise ValueError(f"Invalid cached-path median/MAD: {key}")
        timings[key] = (median, mad)
    if set(timings) != expected:
        raise ValueError("Expected all five final routes at Stress widths 8, 12, 16 and 18")

    ax = axes[1, 1]
    route_handles = []
    for role, label, color, marker, linestyle in ROUTES:
        medians = [timings[f"stress_n{width:02d}_l2", role][0] for width in WIDTHS]
        mads = [timings[f"stress_n{width:02d}_l2", role][1] for width in WIDTHS]
        # Final-route definition: cached-path job-to-state median ± raw MAD.
        curve = ax.errorbar(WIDTHS, medians, yerr=mads, color=color, marker=marker,
                            linestyle=linestyle, markersize=2.7, linewidth=1,
                            elinewidth=0.5, capsize=1.2, capthick=0.5, zorder=3, label=label)
        route_handles.append(curve)
    ax.set_title(r"$\mathbf{d}$  Final Stress width comparison", loc="left", pad=7)
    ax.set_xticks(WIDTHS)
    ax.set_xlim(WIDTHS[0] - 0.7, WIDTHS[-1] + 0.7)
    ax.set_yscale("log")
    ax.set_ylim(1e-4, 1e1)
    ax.set_yticks([1e-4, 1e-3, 1e-2, 1e-1, 1, 10])
    ax.minorticks_off()
    ax.set_xlabel("Circuit width (qubits)")
    ax.set_ylabel("Cached-path job-to-state time (s)")
    ax.grid(axis="y", color="#e3e3e3", linewidth=0.45, zorder=0)

    fig.legend(handles=tasklet_handles, loc="outside upper center", ncol=2,
               frameon=False, fontsize=7.5, handlelength=2.2, columnspacing=2,
               title="Quantization tasklets (panels a–c)", title_fontsize=8)
    fig.legend(handles=route_handles, loc="outside lower center", ncol=3,
               frameon=False, fontsize=7, handlelength=2.2, columnspacing=1.5,
               title="Final comparison routes (panel d)", title_fontsize=8)
    save_figure(fig, "app03_supplemental_quantization")


if __name__ == "__main__":
    main()
