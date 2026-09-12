"""Show frozen calibration winners, checking their recorded candidate medians."""
import csv
import json
import math
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import PRIMARY_FAMILIES, ROOT, TABLE_OUTPUT, V4_READOUT, V4_RESULTS  # noqa: E402


SOURCE_BASE = "https://github.com/kazulak/masters-thesis/blob/c7c6cac0b55bdff2f4c24b70397b36f89bedc45f/"
FLOAT = "split_complex_float32_v1"
INT8 = "complex_int8_shared_scale_v1"


def build_rows():
    selection = json.loads((V4_RESULTS / "selection.json").read_text())
    protocol = json.loads((ROOT / "evaluation/unified_v4/protocol.json").read_text())
    if protocol["topology_selection"]["blocks"] != [1, 2, 3, 4, 5] or protocol["topology_selection"]["no_final_feedback"] is not True:
        raise ValueError("Unexpected topology-selection contract")
    with (V4_READOUT / "observations.csv").open(newline="") as stream:
        observations = {}
        for row in csv.DictReader(stream):
            if row["slot_id"] in observations and observations[row["slot_id"]] != row:
                raise ValueError("Conflicting duplicate observation slot")
            observations[row["slot_id"]] = row
    winners = {}
    for record in selection["selections"]:
        family, policy = record["family"], record["policy"]
        if family not in PRIMARY_FAMILIES:
            continue
        key = (family, policy)
        if key in winners or policy not in {FLOAT, INT8}:
            raise ValueError(f"Unexpected selection key: {key}")
        candidates = record["candidates"]
        expected_resources = {(d, t) for d in (1, 2, 4, 8, 16, 32, 64) for t in (8, 24)}
        if len(candidates) != 14 or {(c["dpus"], c["tasklets"]) for c in candidates} != expected_resources:
            raise ValueError(f"Incomplete frozen candidate set: {key}")
        for candidate in candidates:
            if len(candidate["source_slots"]) != 5 or len(set(candidate["source_slots"])) != 5:
                raise ValueError(f"Incomplete candidate source slots: {key}")
            samples = [observations[slot] for slot in candidate["source_slots"]]
            if {int(r["block"]) for r in samples} != {1, 2, 3, 4, 5}:
                raise ValueError(f"Unexpected calibration blocks: {key}")
            for sample in samples:
                arm = json.loads(sample["arm"])
                if (sample["phase"] != "calibration" or sample["case_id"] != record["calibration_case_id"]
                        or sample["cell_id"] != candidate["cell_id"] or sample["issued"] != "True"
                        or sample["warmup"] != "False" or sample["status"] != "success"
                        or sample["finite"] != "True" or sample["same_policy_passed"] != "True"
                        or arm["policy"] != policy or arm["dpus"] != candidate["dpus"]
                        or arm["tasklets"] != candidate["tasklets"]):
                    raise ValueError(f"Inconsistent candidate observation: {sample['slot_id']}")
            times = [float(r["prepared_call_s"]) for r in samples]
            if not all(math.isfinite(t) and t > 0 for t in times):
                raise ValueError(f"Invalid calibration time: {key}")
            median = statistics.median(times)
            if not math.isclose(median, candidate["median_prepared_call_s"], rel_tol=1e-12, abs_tol=0):
                raise ValueError(f"Candidate median disagrees with canonical observations: {key}")
            qualified = all(r["accuracy_qualified"] == "True" for r in samples)
            if candidate["all_accuracy_qualified"] != qualified or candidate["eligible"] != (qualified if policy == FLOAT else True):
                raise ValueError(f"Candidate eligibility disagrees with execution checks: {key}")
        winner = min((c for c in candidates if c["eligible"]),
                     key=lambda c: (c["median_prepared_call_s"], c["dpus"], c["tasklets"], c["cell_id"]))
        if winner != record["selected"]:
            raise ValueError(f"Recorded winner disagrees with frozen selection rule: {key}")
        winners[key] = dict(winner, calibration_case=record["calibration_case_id"])
    if set(winners) != {(f, p) for f in PRIMARY_FAMILIES for p in (FLOAT, INT8)}:
        raise ValueError("Missing primary policy/family selection")
    rows = []
    for family in PRIMARY_FAMILIES:
        f32, int8 = winners[(family, FLOAT)], winners[(family, INT8)]
        expected_case = f"{family}_n{17 if family == 'edc' else 18}"
        if f32["calibration_case"] != expected_case or int8["calibration_case"] != expected_case:
            raise ValueError(f"Unexpected calibration case: {family}")
        rows.append(dict(family=family, calibration_case=expected_case,
                         f32_dpus=f32["dpus"], f32_tasklets=f32["tasklets"],
                         int8_dpus=int8["dpus"], int8_tasklets=int8["tasklets"]))
    return rows


def cell(value):
    return "[" + " #linebreak() ".join("#text(" + json.dumps(str(line), ensure_ascii=False) + ")" for line in str(value).split("\n")) + "]"


def main():
    rows = build_rows()
    header = ["Family", "Calibration case", "Float32\nDPUs", "Float32\ntasklets / DPU", "Int8\nDPUs", "Int8\ntasklets / DPU"]
    lines = ["// Generated by table03_resources.py; canonical evidence is read directly.", "#[", "#set text(size: 8pt)",
             "#set par(leading: 0.5em)", "#table(", "  columns: (20mm, 36mm, 26mm, 26mm, 26mm, 26mm),",
             "  align: (left, left, right, right, right, right),", "  stroke: none, inset: (x: 2pt, y: 4pt),",
             "  table.hline(stroke: 0.6pt),", "  table.header(repeat: true, " + ", ".join(cell(v) for v in header) + "),", "  table.hline(stroke: 0.4pt),"]
    for row in rows:
        values = [row["family"].upper(), row["calibration_case"], row["f32_dpus"], row["f32_tasklets"], row["int8_dpus"], row["int8_tasklets"]]
        lines.append("  " + ", ".join(cell(v) for v in values) + ",")
    note = ("Notes: Resources were selected once from greedy-path calibration, independently for each family and numerical policy, "
            "by minimum median prepared-call time over blocks 1–5. The 14 candidates per policy cross DPUs {1, 2, 4, 8, 16, 32, 64} "
            "with 8 or 24 tasklets per DPU. Exact ties prefer fewer DPUs, then fewer tasklets, then cell_id. "
            "Float32 candidates require full numerical qualification; int8 requires finite output and exact same-policy execution, "
            "with approximation quality reported independently and no quality tuning. The decision was frozen before final path generation "
            "and width measurements; final results did not feed back into resource selection. Resources may therefore differ between policies.")
    lines += ["  table.hline(stroke: 0.6pt),", ")", "#v(3pt)", "#text(" + json.dumps(note, ensure_ascii=False) + ")", "#parbreak()"]
    for label, path in [("Frozen selections", "thesis/implementation/thesis_results/unified_final_v4/selection.json"),
                        ("Calibration observations", "thesis/implementation/thesis_results/unified_final_v4/readout/observations.csv"),
                        ("Selection protocol", "evaluation/unified_v4/protocol.json")]:
        lines.append("#link(" + json.dumps(SOURCE_BASE + path) + ", " + json.dumps(label) + ") ")
    lines.append("]\n")
    TABLE_OUTPUT.mkdir(parents=True, exist_ok=True)
    (TABLE_OUTPUT / "table03_resources.typ").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
