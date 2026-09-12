"""AT1: bounded historical mechanisms and current adjacent ablation contrasts."""
import csv
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import PRIMARY_FAMILIES, ROOT, TABLE_OUTPUT, V4_READOUT  # noqa: E402


def cell(value):
    return f"text({json.dumps(str(value), ensure_ascii=False)})"


def build():
    with (ROOT / "evaluation/final_v1/historical_results.csv").open(newline="") as source_file:
        historical = {r["module"]: r for r in csv.DictReader(source_file)}
    sources = {r["id"]: r for r in json.loads(
        (ROOT / "evaluation/final_v1/historical_sources.json").read_text())}
    source = sources["composition"]
    for key in ("scalar_panel", "outer_k1", "residency", "slicing"):
        assert historical[key]["source_id"] == source["id"]
        assert historical[key]["provenance_class"] == "recorded_summary_not_recomputed"
    panel = [float(n) for n in re.findall(r"([0-9.]+)x", historical["scalar_panel"]["recorded_finding"])]
    outer = float(re.search(r"([0-9.]+)x", historical["outer_k1"]["recorded_finding"])[1])
    resident = float(re.search(r"([0-9.]+)x", historical["residency"]["recorded_finding"])[1])
    slices = [float(n) for n in re.findall(r"([0-9.]+)x", historical["slicing"]["recorded_finding"])]
    assert len(panel) == 2 and len(slices) == 3
    rows = [
        ("WRAM panel", "M=N=K=32; D1/T8 microcase", f"{panel[0]:.3g}× kernel; {panel[1]:.3g}× session-inclusive", "Microcase; whole-circuit benefit unmeasured"),
        ("Outer-K1", historical["outer_k1"]["scope"], f"{outer:.3g}× inclusive; interval spans 1", historical["outer_k1"]["disposition"]),
        ("Residency", "Stress16 D1; bounded resident pair", f"{resident:.3g}× inclusive", historical["residency"]["disposition"] + "; bounded pair only"),
        ("Slicing", "Stress16 D2; plus static scheduling", f"{slices[0]:.3g}× inclusive", "Mixed evidence; this case slower"),
        ("Slicing", "Stress16 D4; plus static scheduling", f"{slices[1]:.3g}× inclusive", "Mixed evidence; this case slower"),
        ("Slicing", "EDC14 D4; plus static scheduling", f"{slices[2]:.3g}× inclusive", "Mixed evidence; selected development confirmation"),
    ]
    with (V4_READOUT / "A.csv").open(newline="") as source_file:
        ablation = list(csv.DictReader(source_file))
    by_case = {}
    for r in ablation:
        if r["case_id"].split("_")[0] in PRIMARY_FAMILIES:
            by_case.setdefault(r["case_id"], {})[r["point"]] = float(r["median_prepared_call_s"])
    assert len(by_case) == 6
    for name, before, after, disposition in (
        ("Complex launch fusion", "A2", "A3", "Retained when admitted; four real products remain"),
        ("Static DAG", "A3", "A4", "Retained scheduling role; measured effect is mixed"),
    ):
        ratios = [r[before] / r[after] for r in by_case.values()]
        gm = math.exp(sum(map(math.log, ratios)) / len(ratios))
        finding = f"GM {gm:.3g}×; range {min(ratios):.3g}–{max(ratios):.3g}×; {sum(r > 1 for r in ratios)}/6 faster"
        rows.append((name, f"Current six families; {before}/{after} prepared-call medians", finding, disposition))
    assert len(rows) == 8
    out = ["#set text(size: 8pt)", "#table(",
           "  columns: (27mm, 45mm, 43mm, 45mm),", "  inset: (x: 3pt, y: 4pt), stroke: none,",
           "  table.header(repeat: true, table.hline(stroke: 0.6pt),",
           "    " + ", ".join(cell(h) for h in ("Mechanism", "Scope", "Measured effect", "Disposition / limit")) + ",",
           "    table.hline(stroke: 0.4pt)),"]
    out.extend("  " + ", ".join(map(cell, row)) + "," for row in rows)
    out += ["  table.hline(stroke: 0.6pt),", ")", "#v(3pt)",
            '#text("Notes: Ratios above 1 favor the mechanism. The first six rows are historical-reported summaries, not raw-recomputed observations. Their timing boundaries differ; residency uses the bounded pair’s subprocess wall boundary and slicing uses session-inclusive execution. Slicing also changes static scheduling, so its contribution is not isolated. The WRAM result is a scalar-versus-panel microcase, not a full-job speedup. Current adjacent contrasts use ratios of medians across six primary families (EDC17, others18), seven measured blocks per configuration, float32 and greedy paths. These heterogeneous effects must not be multiplied into a combined speedup.")',
            '#text(" Historical source: ")#link(' + json.dumps(f"https://github.com/kazulak/masters-thesis/blob/{source['ref']}/{source['path']}") + ')[composition record at 504e614].',
            '#text(" Current source: ")#link("https://github.com/kazulak/masters-thesis/blob/c7c6cac0b55bdff2f4c24b70397b36f89bedc45f/thesis/implementation/thesis_results/unified_final_v4/readout/A.csv")[A.csv at c7c6cac].']
    TABLE_OUTPUT.mkdir(parents=True, exist_ok=True)
    path = TABLE_OUTPUT / "app_table01_mechanisms.typ"
    path.write_text("\n".join(out) + "\n")
    return path


if __name__ == "__main__":
    build()
