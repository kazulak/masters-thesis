"""AT2: every final search and the derived cost of reusing its selected path."""
import csv
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import TABLE_OUTPUT, V4_READOUT, V4_RESULTS  # noqa: E402


def cell(value):
    return f"text({json.dumps(str(value), ensure_ascii=False)})"


def number(value):
    return "—" if value is None else f"{float(value):.3g}"


def build():
    with (V4_READOUT / "cold_cost.csv").open(newline="") as source_file:
        rows = list(csv.DictReader(source_file))
    paths = {r["case_id"]: r for r in json.loads((V4_RESULTS / "path_records.json").read_text())}
    cached = {}
    for name in ("W.csv", "S.csv"):
        with (V4_READOUT / name).open(newline="") as source_file:
            for r in csv.DictReader(source_file):
                if r["role"] == "upmem_f32":
                    assert r["case_id"] not in cached
                    cached[r["case_id"]] = float(r["median_job_to_state_cached_path_s"])
    assert len(rows) == len(paths) == 52
    assert len({r["case_id"] for r in rows}) == 52 and len(cached) == 46
    table_rows = []
    for row in rows:
        key = row["case_id"]
        p = paths[key]
        planning = float(row["planning_once_s"])
        assert planning == p["planning_once_s"]
        assert row["path_status"] == p["status"]
        assert row["path_reason"] == (p["reason"] or "")
        if p["status"] == "selected":
            runtime = cached[key]
            assert runtime == float(row["median_cached_s"])
            averages = [runtime + planning / k for k in (1, 10, 100)]
            for k, value in zip((1, 10, 100), averages):
                assert math.isclose(value, float(row[f"amortized_k{k}"]), rel_tol=1e-12)
            assert math.isclose(averages[0], float(row["cold_estimate"]), rel_tol=1e-12)
            status = "Selected"
        else:
            assert p["status"] == "no_selected_R_path" and p["reason"] == "no_admitted_candidate"
            assert key not in cached and p["admitted_candidate_count"] == 0
            assert all(row[k] == "" for k in ("median_cached_s", "cold_estimate", "amortized_k1", "amortized_k10", "amortized_k100"))
            runtime, averages, status = None, [None] * 3, "No path"
        table_rows.append((key, status, number(planning), number(runtime), *map(number, averages)))
    out = ["#set text(size: 8pt)", "#table(",
           "  columns: (30mm, 22mm, 23mm, 23mm, 20mm, 21mm, 21mm),",
           "  align: (left, left, right, right, right, right, right),",
           "  inset: (x: 3pt, y: 2pt), stroke: none,",
           "  table.header(repeat: true, table.hline(stroke: 0.6pt),",
           "    " + ", ".join(cell(h) for h in ("Case", "R path", "Search once (s)", "Cached f32 (s)", "Mean k=1 (s)", "Mean k=10 (s)", "Mean k=100 (s)")) + ",",
           "    table.hline(stroke: 0.4pt)),"]
    out.extend("  " + ", ".join(map(cell, row)) + "," for row in table_rows)
    out += ["  table.hline(stroke: 0.6pt),", ")", "#v(3pt)",
            '#text("Notes: All 52 final cases are shown, including supplementary Stress. Search once is the measured one-time R-path search cost. Cached float32 is the median complete job-to-state time with the path available, over five non-warmup observations. Mean cost per run is derived as cached median + search cost/k; k=1 is a cold estimate, not a separately measured cold run. The six no-path searches retain their measured search costs. Their cached and amortized values are unavailable (—), never zero: no candidate was admitted by the frozen search/admission procedure. Canonical cold_cost.csv is checked against path_records.json and the float32 rows of W.csv/S.csv.")',
            '#text(" Source: ")#link("https://github.com/kazulak/masters-thesis/tree/c7c6cac0b55bdff2f4c24b70397b36f89bedc45f/thesis/implementation/thesis_results/unified_final_v4")[frozen final results at c7c6cac].']
    TABLE_OUTPUT.mkdir(parents=True, exist_ok=True)
    path = TABLE_OUTPUT / "app_table02_cold_cost.typ"
    path.write_text("\n".join(out) + "\n")
    return path


if __name__ == "__main__":
    build()
