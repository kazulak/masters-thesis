"""App02: Stress16 tasklet, DPU and cumulative-change views from frozen readouts."""
import csv
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import V4_READOUT, publication_style, save_figure  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import PercentFormatter  # noqa: E402


CASE = "stress_n16_l2"
DPUS = (1, 2, 4, 8, 16, 32, 64)
STEPS = ("A0", "A1", "A2", "A3", "A4")
STEP_LABELS = ("Baseline", "8\ntasklets", "4\nDPUs", "Launch\nfusion", "DAG")


def main():
    with (V4_READOUT / "T.csv").open(newline="", encoding="utf-8") as source:
        tasklet_rows = list(csv.DictReader(source))
    with (V4_READOUT / "D.csv").open(newline="", encoding="utf-8") as source:
        dpu_rows = list(csv.DictReader(source))
    with (V4_READOUT / "A.csv").open(newline="", encoding="utf-8") as source:
        ablation_rows = list(csv.DictReader(source))

    tasklet_timings = {}
    for row in tasklet_rows:
        if row["case_id"] != CASE:
            continue
        tasklets = int(row["point"].removeprefix("T"))
        median, mad = float(row["median_prepared_call_s"]), float(row["raw_mad"])
        if row["view"] != "T" or row["point"] != f"T{tasklets}" or tasklets in tasklet_timings:
            raise ValueError(f"Unexpected or duplicate tasklet point: {CASE}/{row['point']}")
        if int(row["count"]) != 5:
            raise ValueError(f"Expected five measured blocks: {CASE}/{row['point']}")
        if not (math.isfinite(median) and math.isfinite(mad) and median > 0 and 0 <= mad < median):
            raise ValueError(f"Invalid median/MAD: {CASE}/{row['point']}")
        tasklet_timings[tasklets] = (median, mad)
    if set(tasklet_timings) != set(range(1, 25)):
        raise ValueError(f"Expected exactly T1..T24 for {CASE}")

    dpu_timings = {}
    for row in dpu_rows:
        if row["case_id"] != CASE:
            continue
        dpu_label, tasklet_label = row["point"].split("/")
        dpus, tasklets = int(dpu_label.removeprefix("D")), int(tasklet_label.removeprefix("T"))
        median, mad = float(row["median_prepared_call_s"]), float(row["raw_mad"])
        if row["view"] != "D" or row["point"] != f"D{dpus}/T{tasklets}" or (dpus, tasklets) in dpu_timings:
            raise ValueError(f"Unexpected or duplicate DPU point: {CASE}/{row['point']}")
        if int(row["count"]) != 5:
            raise ValueError(f"Expected five measured blocks: {CASE}/{row['point']}")
        if not (math.isfinite(median) and math.isfinite(mad) and median > 0 and 0 <= mad < median):
            raise ValueError(f"Invalid median/MAD: {CASE}/{row['point']}")
        dpu_timings[dpus, tasklets] = (median, mad)
    if set(dpu_timings) != {(d, t) for d in DPUS for t in (8, 24)}:
        raise ValueError(f"Expected D1,2,4,8,16,32,64 at both T8 and T24 for {CASE}")

    ablation_timings = {}
    for row in ablation_rows:
        if row["case_id"] != CASE:
            continue
        step = row["point"]
        median, mad = float(row["median_prepared_call_s"]), float(row["raw_mad"])
        if row["view"] != "A" or step not in STEPS or step in ablation_timings:
            raise ValueError(f"Unexpected or duplicate ablation point: {CASE}/{step}")
        if int(row["count"]) != 7:
            raise ValueError(f"Expected seven measured blocks: {CASE}/{step}")
        if not (math.isfinite(median) and math.isfinite(mad) and median > 0 and 0 <= mad < median):
            raise ValueError(f"Invalid median/MAD: {CASE}/{step}")
        ablation_timings[step] = (median, mad)
    if set(ablation_timings) != set(STEPS):
        raise ValueError(f"Expected exactly A0..A4 for {CASE}")

    publication_style()
    fig, axes = plt.subplots(3, 1, figsize=(160 / 25.4, 190 / 25.4), layout="constrained")

    ax = axes[0]
    baseline = tasklet_timings[1][0]
    tasklets = list(range(1, 25))
    speedups, lower_errors, upper_errors = [], [], []
    for tasklet in tasklets:
        median, mad = tasklet_timings[tasklet]
        speedup = baseline / median
        # F1 definition: fixed T1 median, transformed descriptive MAD, no CI.
        low = baseline / (median + mad) if tasklet != 1 else 1.0
        high = baseline / (median - mad) if tasklet != 1 else 1.0
        speedups.append(speedup)
        lower_errors.append(speedup - low)
        upper_errors.append(high - speedup)
    ax.errorbar(tasklets, speedups, yerr=[lower_errors, upper_errors],
                color="#0072B2", marker="o", markersize=2.4, linewidth=1.0,
                elinewidth=0.55, capsize=1.5, capthick=0.55, zorder=3)
    ax.axhline(1, color="#888888", linestyle="--", linewidth=0.55, zorder=2)
    ax.set_title(r"$\mathbf{a}$  Tasklet scaling", loc="left", pad=7)
    ax.set_title("Stress16 · 16 qubits", loc="right", fontsize=7.5, pad=7)
    ax.set_xlim(0.5, 24.5)
    ax.set_ylim(0.5, 5.0)
    ax.set_xticks([1, 4, 8, 12, 16, 20, 24])
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_xlabel("Tasklets $T$ (one physical DPU)")
    ax.set_ylabel("Speedup relative to 1 tasklet (×)")

    ax = axes[1]
    for tasklets, color, marker, linestyle in (
        (8, "#0072B2", "o", "-"),
        (24, "#D55E00", "s", "--"),
    ):
        baseline = dpu_timings[1, tasklets][0]
        speedups, lower_errors, upper_errors = [], [], []
        for dpus in DPUS:
            median, mad = dpu_timings[dpus, tasklets]
            speedup = baseline / median
            # F2 definition: fixed tasklet-matched D1 median; D1 has no whisker.
            low = baseline / (median + mad) if dpus != 1 else 1.0
            high = baseline / (median - mad) if dpus != 1 else 1.0
            speedups.append(speedup)
            lower_errors.append(speedup - low)
            upper_errors.append(high - speedup)
        ax.errorbar(DPUS, speedups, yerr=[lower_errors, upper_errors],
                    color=color, marker=marker, linestyle=linestyle,
                    markersize=3, linewidth=1.0, elinewidth=0.55,
                    capsize=1.5, capthick=0.55, zorder=3,
                    label=f"T{tasklets} ({tasklets} tasklets)")
    ax.axhline(1, color="#888888", linestyle="--", linewidth=0.55, zorder=2)
    ax.set_title(r"$\mathbf{b}$  DPU scaling", loc="left", pad=7)
    ax.set_title("Stress16 · 16 qubits", loc="right", fontsize=7.5, pad=7)
    ax.set_xscale("log", base=2)
    ax.set_xticks(DPUS, labels=[str(d) for d in DPUS])
    ax.set_xlim(0.8, 80)
    ax.set_ylim(0.8, 3.0)
    ax.set_yticks([1, 1.5, 2, 2.5, 3])
    ax.minorticks_off()
    ax.set_xlabel("Physical DPUs $D$ (one rank; logarithmic scale)")
    ax.set_ylabel("Speedup relative to 1 DPU (×)")
    ax.legend(loc="upper left", ncol=2, frameon=False, fontsize=7.5,
              handlelength=2.2, columnspacing=2)

    ax = axes[2]
    baseline = ablation_timings["A0"][0]
    normalized = [ablation_timings[step][0] / baseline for step in STEPS]
    # F3 definition: fixed A0 median and scaled descriptive MAD, with A0 exact.
    errors = [0 if step == "A0" else ablation_timings[step][1] / baseline for step in STEPS]
    ax.bar(range(5), normalized, width=0.6, color=["#999999"] + ["#0072B2"] * 4,
           yerr=errors, capsize=1.5, zorder=3,
           error_kw={"elinewidth": 0.55, "capthick": 0.55, "ecolor": "#333333"})
    ax.axhline(1, color="#888888", linestyle="--", linewidth=0.55, zorder=2)
    ax.set_title(r"$\mathbf{c}$  Cumulative changes", loc="left", pad=7)
    ax.set_title("Stress16 · 16 qubits", loc="right", fontsize=7.5, pad=7)
    ax.set_xticks(range(5), labels=STEP_LABELS)
    ax.tick_params(axis="x", labelsize=7)
    ax.set_ylim(0, 1.1)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1])
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=0, symbol=""))
    ax.set_xlabel("Cumulative changes")
    ax.set_ylabel("Runtime (% of baseline)")

    for ax in axes:
        ax.grid(axis="y", color="#e3e3e3", linewidth=0.45, zorder=0)
    save_figure(fig, "app02_supplemental_resources")


if __name__ == "__main__":
    main()
