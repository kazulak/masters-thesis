"""F6: all five final routes and the declared R-path admission frontier."""
import csv
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import V4_READOUT, V4_RESULTS, publication_style, save_figure  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402


FAMILIES = (("bb84", "BB84"), ("bv", "BV"), ("edc", "EDC"),
            ("hs", "HS"), ("qrng", "QRNG"), ("xor", "XOR"))
WIDTHS = (8, 12, 16, 18, 20, 22, 24, 26)
ROUTES = (
    ("upmem_f32", "UPMEM float32", "#0072B2", "o", "-"),
    ("upmem_int8", "UPMEM int8", "#D55E00", "s", "--"),
    ("numpy_f32_p1", "NumPy same-DAG (P1)", "#009E73", "v", "-."),
    ("quest32_p8", "QuEST (P8)", "#CC79A7", "D", "-"),
    ("quest32_p1", "QuEST (P1)", "#666666", "^", ":"),
)
R_ROUTES = ("upmem_f32", "upmem_int8", "numpy_f32_p1")


def main():
    with (V4_READOUT / "W.csv").open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    with (V4_RESULTS / "final_manifest.json").open(encoding="utf-8") as source:
        manifest = json.load(source)
    with (V4_RESULTS / "path_records.json").open(encoding="utf-8") as source:
        path_rows = json.load(source)
    paths = {p["case_id"]: p for p in path_rows}
    if (len(paths) != 52 or len(path_rows) != 52
            or sum(p["status"] == "selected" for p in path_rows) != 46
            or sum(p["status"] == "no_selected_R_path" for p in path_rows) != 6):
        raise ValueError("Expected 46 selected R paths and six no-path outcomes")

    case_widths = {f"{family}_n{w - (family == 'edc'):02d}": w - (family == "edc")
                   for family, _ in FAMILIES for w in WIDTHS}
    planned = [c for c in manifest["cells"] if c["view"] == "W"]
    cells = {(c["case_id"], c["role"]): c for c in planned}
    if len(cells) != len(planned) or set(cells) != {(c, r[0]) for c in case_widths for r in ROUTES}:
        raise ValueError("Missing, duplicate or unexpected primary final-route cells")
    timings = {}
    for row in rows:
        key = (row["case_id"], row["role"])
        if row["view"] != "W" or key in timings or key not in cells or row["cell_id"] != cells[key]["cell_id"]:
            raise ValueError(f"Unexpected or duplicate final timing: {key}")
        if int(row["count"]) != 5:
            raise ValueError(f"Expected five measured blocks: {key}")
        median, mad = float(row["median_job_to_state_cached_path_s"]), float(row["raw_mad_cached_s"])
        if not (math.isfinite(median) and math.isfinite(mad) and median > 0 and 0 <= mad < median):
            raise ValueError(f"Invalid cached-path median/MAD: {key}")
        timings[key] = (median, mad)
    if set(timings) != {key for key, cell in cells.items() if cell["eligible_for_runtime_admission"]}:
        raise ValueError("Observed timings differ from admitted final routes")

    frontiers = []
    for case in case_widths:
        path = paths[case]
        if path["status"] == "selected":
            if path["admitted_candidate_count"] <= 0 or any((case, r[0]) not in timings for r in ROUTES):
                raise ValueError(f"Selected path is missing an admitted route: {case}")
            if any(cells[case, role]["selected_path_id"] != path["path_id"] for role in R_ROUTES):
                raise ValueError(f"Final TN routes do not share the selected R path: {case}")
        else:
            if (path["status"] != "no_selected_R_path" or path["reason"] != "no_admitted_candidate"
                    or path["admitted_candidate_count"] != 0):
                raise ValueError(f"Unknown final frontier reason: {case}")
            if any((case, role) in timings or cells[case, role]["not_runnable_reason"] != "no_selected_R_path"
                   for role in R_ROUTES):
                raise ValueError(f"Unexpected execution at R frontier: {case}")
            if any((case, role) not in timings for role in ("quest32_p8", "quest32_p1")):
                raise ValueError(f"Missing QuEST endpoint at R frontier: {case}")
            frontiers.append(case)
    expected_frontiers = {f"{f}_n{26 - (f == 'edc'):02d}" for f, _ in FAMILIES}
    if set(frontiers) != expected_frontiers:
        raise ValueError("Expected the six declared maximum-width R frontiers")

    publication_style()
    fig, axes = plt.subplots(2, 3, figsize=(160 / 25.4, 125 / 25.4),
                             sharey=True, layout="constrained")
    legend_handles = []
    for letter, ax, (family, title) in zip("abcdef", axes.flat, FAMILIES):
        cases = sorted((c for c in case_widths if c.startswith(f"{family}_n")), key=case_widths.get)
        ns = [case_widths[c] for c in cases]
        for role, label, color, marker, linestyle in ROUTES:
            available = [c for c in cases if (c, role) in timings]
            x = [case_widths[c] for c in available]
            medians = [timings[c, role][0] for c in available]
            mads = [timings[c, role][1] for c in available]
            curve = ax.errorbar(x, medians, yerr=mads, color=color, marker=marker,
                                linestyle=linestyle, markersize=2.7, linewidth=1,
                                elinewidth=0.5, capsize=1.2, capthick=0.5, zorder=3, label=label)
            if letter == "a":
                legend_handles.append(curve)
        # An admission frontier has no numerical runtime coordinate.
        ax.axvspan(ns[-1] - 0.45, ns[-1] + 0.45, color="#e6e6e6", linewidth=0, zorder=0)
        ax.set_title(rf"$\mathbf{{{letter}}}$  {title}", loc="left", pad=7)
        ax.set_xticks(ns)
        ax.set_xlim(ns[0] - 0.7, ns[-1] + 0.7)
        ax.set_yscale("log")
        ax.set_ylim(1e-4, 1e2)
        ax.set_yticks([1e-4, 1e-3, 1e-2, 1e-1, 1, 10, 100])
        ax.minorticks_off()
        ax.grid(axis="y", color="#e3e3e3", linewidth=0.45, zorder=0)

    legend_handles.append(Patch(facecolor="#e6e6e6", edgecolor="none",
                                label="R path unavailable\n(no admitted candidate)"))
    fig.legend(handles=legend_handles, loc="outside upper center", ncol=3,
               frameon=False, fontsize=7, handlelength=2.2, columnspacing=1.5)
    fig.supxlabel("Circuit width (qubits)", fontsize=8)
    fig.supylabel("Cached-path job-to-state time (s)", fontsize=8)
    save_figure(fig, "fig06_final_cpu")


if __name__ == "__main__":
    main()
