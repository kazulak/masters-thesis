"""AT4: empirical search-admission frontiers at the tested final widths."""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import PRIMARY_FAMILIES, TABLE_OUTPUT, V4_READOUT, V4_RESULTS  # noqa: E402


def cell(value):
    return f"text({json.dumps(str(value), ensure_ascii=False)})"


def build():
    paths = {r["case_id"]: r for r in json.loads((V4_RESULTS / "path_records.json").read_text())}
    with (V4_READOUT / "cold_cost.csv").open(newline="") as source_file:
        cases = list(csv.DictReader(source_file))
    rows = []
    for family in PRIMARY_FAMILIES:
        tested = sorted((int(r["n"]), paths[r["case_id"]]) for r in cases if r["family"] == family)
        admitted = [(n, p) for n, p in tested if p["status"] == "selected"]
        rejected = [(n, p) for n, p in tested if p["status"] == "no_selected_R_path"]
        largest, selected = max(admitted, key=lambda pair: pair[0])
        first, missing = min(rejected, key=lambda pair: pair[0])
        assert first > largest and selected["admitted_candidate_count"] > 0
        assert missing["reason"] == "no_admitted_candidate" and missing["admitted_candidate_count"] == 0
        assert (largest, first) == ((23, 25) if family == "edc" else (24, 26))
        rows.append((family.upper(), largest, first, "no_selected_R_path", "no_admitted_candidate"))
    assert len(rows) == 6
    out = ["#set text(size: 8pt)", "#table(",
           "  columns: (20mm, 29mm, 31mm, 39mm, 41mm),",
           "  align: (left, right, right, left, left), inset: (x: 3pt, y: 4pt), stroke: none,",
           "  table.header(repeat: true, table.hline(stroke: 0.6pt),",
           "    " + ", ".join(cell(h) for h in ("Family", "Largest admitted width", "First tested no-path width", "Search status", "Recorded reason")) + ",",
           "    table.hline(stroke: 0.4pt)),"]
    out.extend("  " + ", ".join(map(cell, row)) + "," for row in rows)
    out += ["  table.hline(stroke: 0.6pt),", ")", "#v(3pt)",
            '#text("Notes: Width means qubits. The frontier is empirical: the largest tested width with a selected R path and the first tested width with none, under the frozen candidate search and admission procedure. All six no-path records have zero admitted candidates. Untested intermediate widths are not resolved by this table. The recorded reason does not identify an MRAM capacity limit or prove that no feasible contraction path exists. These are search/admission outcomes, not failed physical executions.")',
            '#text(" Source: ")#link("https://github.com/kazulak/masters-thesis/blob/c7c6cac0b55bdff2f4c24b70397b36f89bedc45f/thesis/implementation/thesis_results/unified_final_v4/path_records.json")[path_records.json at c7c6cac], checked against cold_cost.csv.']
    TABLE_OUTPUT.mkdir(parents=True, exist_ok=True)
    path = TABLE_OUTPUT / "app_table04_frontiers.typ"
    path.write_text("\n".join(out) + "\n")
    return path


if __name__ == "__main__":
    build()
