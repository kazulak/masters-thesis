"""F3: cumulative implementation changes from the frozen A.csv medians."""
import csv
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import V4_READOUT, publication_style, save_figure  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import PercentFormatter  # noqa: E402


CASES = (
    ("bb84_n18", "BB84", 18),
    ("bv_n18", "BV", 18),
    ("edc_n17", "EDC", 17),
    ("hs_n18", "HS", 18),
    ("qrng_n18", "QRNG", 18),
    ("xor_n18", "XOR", 18),
)
STEPS = ("A0", "A1", "A2", "A3", "A4")
STEP_LABELS = ("Baseline", "8\ntasklets", "4\nDPUs", "Launch\nfusion", "DAG")


def main():
    with (V4_READOUT / "A.csv").open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))

    publication_style()
    fig, axes = plt.subplots(2, 3, figsize=(160 / 25.4, 115 / 25.4),
                             sharex=True, sharey=True, layout="constrained")
    for letter, ax, (case, title, qubits) in zip("abcdef", axes.flat, CASES):
        timings = {}
        for row in rows:
            if row["case_id"] != case:
                continue
            step = row["point"]
            median, mad = float(row["median_prepared_call_s"]), float(row["raw_mad"])
            if row["view"] != "A" or step not in STEPS or step in timings:
                raise ValueError(f"Unexpected or duplicate ablation point: {case}/{step}")
            if int(row["count"]) != 7:
                raise ValueError(f"Expected seven measured blocks: {case}/{step}")
            if not (math.isfinite(median) and math.isfinite(mad) and median > 0 and 0 <= mad < median):
                raise ValueError(f"Invalid median/MAD: {case}/{step}")
            timings[step] = (median, mad)
        if set(timings) != set(STEPS):
            raise ValueError(f"Expected exactly A0..A4 for {case}")

        baseline = timings["A0"][0]
        normalized = [timings[step][0] / baseline for step in STEPS]
        # Descriptive MAD scaled by a fixed A0 median; A0 self-normalizes exactly.
        errors = [0 if step == "A0" else timings[step][1] / baseline for step in STEPS]
        ax.bar(range(5), normalized, width=0.6, color=["#999999"] + ["#0072B2"] * 4,
               yerr=errors, capsize=1.5, zorder=3,
               error_kw={"elinewidth": 0.55, "capthick": 0.55, "ecolor": "#333333"})
        ax.axhline(1, color="#888888", linestyle="--", linewidth=0.55, zorder=2)
        ax.set_title(rf"$\mathbf{{{letter}}}$  {title}", loc="left", pad=7)
        ax.set_title(f"{qubits} qubits", loc="right", fontsize=7.5, pad=7)
        ax.set_xticks(range(5), labels=STEP_LABELS)
        ax.tick_params(axis="x", labelsize=7)
        ax.set_ylim(0, 1.1)
        ax.set_yticks([0, 0.25, 0.5, 0.75, 1])
        ax.yaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=0, symbol=""))
        ax.grid(axis="y", color="#e3e3e3", linewidth=0.45, zorder=0)

    fig.supylabel("Runtime (% of baseline)", fontsize=8)
    fig.supxlabel("Cumulative changes", fontsize=8)
    save_figure(fig, "fig03_ablation")


if __name__ == "__main__":
    main()
