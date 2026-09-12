"""AT6: all seven workloads and five cumulative ablation configurations."""
import csv
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import PRIMARY_FAMILIES, TABLE_OUTPUT, V4_READOUT, V4_RESULTS  # noqa: E402


def cell(value):
    return f"text({json.dumps(str(value), ensure_ascii=False)})"


def build():
    with (V4_READOUT / "A.csv").open(newline="") as source_file:
        rows = list(csv.DictReader(source_file))
    manifest = json.loads((V4_RESULTS / "manifest/manifest.json").read_text())
    cells = {c["cell_id"]: c for c in manifest["calibration_cells"]}
    decoder = {
        "A0": (1, 1, False, "serial_nodes_v1"),
        "A1": (1, 8, False, "serial_nodes_v1"),
        "A2": (4, 8, False, "serial_nodes_v1"),
        "A3": (4, 8, True, "serial_nodes_v1"),
        "A4": (4, 8, True, "static_dag_waves_v1"),
    }
    by_case = {}
    for r in rows:
        c = cells[r["cell_id"]]
        arm = c["arm"]
        assert c["case_id"] == r["case_id"] and c["path_role"] == "greedy"
        assert (arm["dpus"], arm["tasklets"], arm["fuse"], arm["schedule"]) == decoder[r["point"]]
        assert arm["backend"] == "upmem" and arm["policy"] == "split_complex_float32_v1"
        assert arm["geometry"] == "panel_only_v1" and arm["transport"] == "packed_wave_v1"
        assert int(r["count"]) == 7
        case = by_case.setdefault(r["case_id"], {})
        assert r["point"] not in case
        case[r["point"]] = r
    assert len(rows) == 35 and len(by_case) == 7
    assert all(set(points) == set(decoder) for points in by_case.values())
    primary = [c for c in by_case if c.split("_")[0] in PRIMARY_FAMILIES]
    assert len(primary) == 6
    ratios = [float(by_case[c]["A0"]["median_prepared_call_s"]) / float(by_case[c]["A4"]["median_prepared_call_s"]) for c in primary]
    gm = math.exp(sum(map(math.log, ratios)) / len(ratios))
    assert math.isclose(gm, 6.247068649713234, rel_tol=1e-12)
    out = ["#set text(size: 8pt)", "#table(",
           "  columns: (30mm, 15mm, 29mm, 26mm, 30mm, 30mm),",
           "  align: (left, left, right, right, right, right), inset: (x: 3pt, y: 3pt), stroke: none,",
           "  table.header(repeat: true, table.hline(stroke: 0.6pt),",
           "    " + ", ".join(cell(h) for h in ("Case", "Config", "Prepared-call median (s)", "Raw MAD (s)", "Baseline time (%)", "Baseline/config speedup")) + ",",
           "    table.hline(stroke: 0.4pt)),"]
    for case, points in by_case.items():
        baseline = float(points["A0"]["median_prepared_call_s"])
        for point in decoder:
            r = points[point]
            median = float(r["median_prepared_call_s"])
            mad = float(r["raw_mad"])
            percentage = 100.0 if point == "A0" else 100 * median / baseline
            speedup = 1.0 if point == "A0" else baseline / median
            row = (case, point, f"{median:.3g}", f"{mad:.3g}", f"{percentage:.3g}", f"{speedup:.3g}×")
            out.append("  " + ", ".join(map(cell, row)) + ",")
    out += ["  table.hline(stroke: 0.6pt),", ")", "#v(3pt)",
            '#text("Configuration decoder (cumulative): A0 = D1/T1, serial_nodes_v1, unfused; A1 = D1/T8, serial_nodes_v1, unfused; A2 = D4/T8, serial_nodes_v1, unfused; A3 = D4/T8, serial_nodes_v1, complex launch/four-product fusion when admitted; A4 = D4/T8, static_dag_waves_v1, the same fusion. D is DPUs; T is tasklets per DPU. All use one rank, packed_wave_v1, panel_only_v1, split_complex_float32_v1 and greedy contraction paths. Fusion combines real products into launches; it is not quantum-gate fusion.")',
            "#text(" + json.dumps(
                f"Notes: All 35 canonical A rows are shown: six primary families (EDC17, others18) plus supplementary Stress16 with two layers, each at A0–A4. Each median and raw MAD summarizes seven measured blocks, excluding warmups. Prepared-call wall time includes session opening, execution/transfers, output materialization and session closing; it excludes circuit lowering, path search, DAG construction and physical mapping. Raw MAD is median absolute deviation in seconds, not a confidence interval. Baseline percentages self-normalize to 100% and speedup to 1×; the raw baseline MAD remains the measured dispersion and is not set to zero. Derived columns use unrounded canonical medians; uncertainty in their shared baseline is not propagated. The six-primary-family geometric mean of A0/A4 is {gm:.3g}×; supplementary Stress is excluded. Cumulative configurations do not estimate independent mechanism contributions.", ensure_ascii=False) + ")",
            '#text(" Source: ")#link("https://github.com/kazulak/masters-thesis/blob/c7c6cac0b55bdff2f4c24b70397b36f89bedc45f/thesis/implementation/thesis_results/unified_final_v4/readout/A.csv")[A.csv at c7c6cac], with configuration identities checked against the frozen calibration manifest.']
    TABLE_OUTPUT.mkdir(parents=True, exist_ok=True)
    path = TABLE_OUTPUT / "app_table06_ablation.typ"
    path.write_text("\n".join(out) + "\n")
    return path


if __name__ == "__main__":
    build()
