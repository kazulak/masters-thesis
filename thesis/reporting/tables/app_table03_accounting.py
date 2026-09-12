"""AT3: reconcile qualification, issued slots, search outcomes and retention."""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import TABLE_OUTPUT, V4_READOUT, V4_RESULTS  # noqa: E402


def cell(value):
    if isinstance(value, int):
        value = f"{value:,}"
    return f"text({json.dumps(str(value), ensure_ascii=False)})"


def build():
    accounting = json.loads((V4_READOUT / "accounting.json").read_text())
    retention = json.loads((V4_RESULTS / "retention.json").read_text())
    manifest = json.loads((V4_RESULTS / "manifest/manifest.json").read_text())
    final_manifest = json.loads((V4_RESULTS / "final_manifest.json").read_text())
    counts = json.loads((V4_RESULTS / "manifest/counts.json").read_text())
    with (V4_RESULTS / "manifest/qualification.csv").open(newline="") as source_file:
        qualification = list(csv.DictReader(source_file))
    calibration = json.loads((V4_RESULTS / "calibration_rows.json").read_text())
    final = json.loads((V4_RESULTS / "final_rows.json").read_text())
    paths = json.loads((V4_RESULTS / "path_records.json").read_text())
    attempts = retention["attempt_counts"]
    assert accounting["run_id"] == retention["run_id"]
    assert len(qualification) == len(manifest["qualification"]) == accounting["qualification"]["physical"] == 108
    assert len({r["configuration_id"] for r in qualification}) == accounting["qualification"]["configurations"] == 54
    assert {(r["configuration_id"], r["fixture_id"]) for r in qualification} == {
        (r["configuration_id"], r["fixture_id"]) for r in manifest["qualification"]}
    for key, count_key, receipt_key in (
        ("physical", "physical_qualification_attempts", "qualification_upmem_phy"),
        ("simulator", "simulator_qualification_attempts", "qualification_upmem_sim"),
        ("quest", "quest_qualification_calls", "qualification_quest"),
    ):
        assert accounting["qualification"][key] == counts[count_key] == attempts[receipt_key]
    for phase, ledger, slots in (("calibration", calibration, manifest["calibration_slots"]),
                                 ("final", final, final_manifest["slots"])):
        assert len(ledger) == len(slots)
        assert {r["slot_id"] for r in ledger} == {r["slot_id"] for r in slots}
        for key, value in (("planned", len(ledger)), ("issued", sum(r["issued"] for r in ledger)),
                           ("success", sum(r["status"] == "success" for r in ledger)),
                           ("not_issued", sum(not r["issued"] for r in ledger))):
            assert accounting[phase][key] == value
        for key in ("planned", "issued", "success"):
            assert accounting[phase][key] == attempts[f"{phase}_{key}_slots"]
    assert accounting["final"]["not_issued"] == attempts["final_not_issued_unsupported"] == 108
    cells = {c["cell_id"]: c for c in final_manifest["cells"]}
    routes = ("upmem_f32", "upmem_int8", "numpy_f32_p1", "quest32_p1", "quest32_p8")
    route_labels = {"upmem_f32": "UPMEM float32", "upmem_int8": "UPMEM int8",
                    "numpy_f32_p1": "NumPy same-DAG", "quest32_p1": "QuEST P1", "quest32_p8": "QuEST P8"}
    attempt_rows = [
        ("Qualification: physical UPMEM", 108, 108, 0),
        ("Qualification: QuEST CPU", 32, 32, 0),
        ("Qualification: UPMEM simulator", 108, 108, 0),
        ("Calibration: physical UPMEM", accounting["calibration"]["planned"], accounting["calibration"]["issued"], accounting["calibration"]["not_issued"]),
    ]
    for route in routes:
        ledger = [r for r in final if cells[r["cell_id"]]["role"] == route]
        calculated = {"planned": len(ledger), "issued": sum(r["issued"] for r in ledger),
                      "not_issued": sum(not r["issued"] for r in ledger),
                      "success": sum(r["status"] == "success" for r in ledger)}
        assert accounting["routes"][route] == calculated
        assert calculated["planned"] == 312
        assert calculated["issued"] == calculated["success"]
        attempt_rows.append(("Final: " + route_labels[route], calculated["planned"], calculated["issued"], calculated["not_issued"]))
    a = accounting["final"]
    attempt_rows.append(("Final: all five routes", a["planned"], a["issued"], a["not_issued"]))
    physical = accounting["qualification"]["physical"] + sum(r["issued"] and r["backend"] == "upmem" for r in calibration + final)
    unissued_physical = sum(not r["issued"] and r["backend"] == "upmem" for r in final)
    assert physical == accounting["physical"]["issued"] == 3334
    assert unissued_physical == accounting["physical"]["final"]["not_issued"] == 72
    assert physical + unissued_physical == accounting["physical"]["ceiling"] == counts["physical_attempt_ceiling_including_qualification"] == 3406
    attempt_rows.append(("Physical total / allocated ceiling", 3406, physical, unissued_physical))
    selected = sum(p["status"] == "selected" for p in paths)
    no_path = sum(p["status"] == "no_selected_R_path" for p in paths)
    assert selected == accounting["paths"]["selected"] == 46
    assert no_path == accounting["paths"]["no_selected"] == 6
    assert len(paths) == accounting["paths"]["searches"] == attempts["r_path_searches"] == 52
    assert accounting["paths"]["proposals"] == attempts["r_path_proposals"] == counts["final_search_proposals"] == 6656
    assert accounting["archive_files_count"] == retention["archive_files_count"] == 8288
    assert retention["archive_A_path"] != retention["archive_B_path"]
    assert accounting["calibration_cells"] == len(manifest["calibration_cells"]) == 434
    assert accounting["final_cells"] == len(final_manifest["cells"]) == 260
    assert accounting["deduplicated_slots"] == counts["duplicate_slots_avoided_within_calibration"] == 714
    outcome_counts = Counter((cells[r["cell_id"]]["role"], r["issued"], r["status"], r["reason"]) for r in final)
    assert outcome_counts == Counter({(r["route"], r["issued"], r["status"], r["reason"]): r["count"] for r in accounting["route_outcomes"]})
    inventory_rows = [
        ("Calibration / final configurations", "434 / 260", "Case/resource/route combinations; includes unsupported final routes"),
        ("Avoided duplicate calibration slots", "714", "Shared analysis memberships reuse the same observations"),
        ("Final R-path searches", "52", "46 selected + 6 no selected path"),
        ("Final search proposals", "6,656", "Separate from physical execution attempts"),
        ("Tiny R qualification searches", "4", "Separate qualification searches"),
        ("Retained archive copies", "2", "Receipt records distinct archive-A and archive-B locations"),
        ("Files per archive copy", "8,288", "Frozen retention receipt; each copy has this count"),
    ]
    assert accounting["qualification"]["tiny_r_searches"] == attempts["qualification_tiny_r_searches"] == 4
    out = ["#set text(size: 8pt)", "#table(",
           "  columns: (88mm, 24mm, 24mm, 24mm), align: (left, right, right, right),",
           "  inset: (x: 3pt, y: 4pt), stroke: none,",
           "  table.header(repeat: true, table.hline(stroke: 0.6pt),",
           "    " + ", ".join(cell(h) for h in ("Attempt scope", "Planned", "Issued / successful", "Not issued")) + ",",
           "    table.hline(stroke: 0.4pt)),"]
    out.extend("  " + ", ".join(map(cell, row)) + "," for row in attempt_rows)
    out += ["  table.hline(stroke: 0.6pt),", ")", "#v(6pt)", "#table(",
            "  columns: (63mm, 25mm, 72mm), inset: (x: 3pt, y: 4pt), stroke: none,",
            "  table.header(repeat: true, table.hline(stroke: 0.6pt),",
            "    " + ", ".join(cell(h) for h in ("Other accounting", "Count", "Scope")) + ",",
            "    table.hline(stroke: 0.4pt)),"]
    out.extend("  " + ", ".join(map(cell, row)) + "," for row in inventory_rows)
    out += ["  table.hline(stroke: 0.6pt),", ")", "#v(3pt)",
            '#text("Notes: Issued counts include warmups; published measurement medians exclude them. All issued calibration and final slots succeeded. The three R-dependent routes each have 36 unsupported, unissued slots (six cases × six blocks); both QuEST routes issued all 312 slots. Physical issues are 108 qualification + 2,674 calibration + 552 final = 3,334 ≤ 3,406; the 72 remaining physical final slots were not issued. CPU and simulator qualification are separate from the physical ceiling. Final-route rows sum to the final total; subtotal rows are not additional attempts. Counts are reconciled with frozen manifests, qualification.csv, calibration/final ledgers and retention.json. Archive file counts are receipt statements; this table does not claim a fresh byte-for-byte re-verification of both retained copies.")',
            '#text(" Source: ")#link("https://github.com/kazulak/masters-thesis/tree/c7c6cac0b55bdff2f4c24b70397b36f89bedc45f/thesis/implementation/thesis_results/unified_final_v4")[accounting, manifests, ledgers and retention at c7c6cac].']
    TABLE_OUTPUT.mkdir(parents=True, exist_ok=True)
    path = TABLE_OUTPUT / "app_table03_accounting.typ"
    path.write_text("\n".join(out) + "\n")
    return path


if __name__ == "__main__":
    build()
