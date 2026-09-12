"""AT5: all issued non-warmup UPMEM validation observations, in 110 groups."""
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import TABLE_OUTPUT, V4_READOUT, V4_RESULTS  # noqa: E402


def cell(value):
    return f"text({json.dumps(str(value), ensure_ascii=False)})"


def build():
    with (V4_READOUT / "observations.csv").open(newline="") as source_file:
        observations = list(csv.DictReader(source_file))
    ledgers = json.loads((V4_RESULTS / "calibration_rows.json").read_text()) + json.loads(
        (V4_RESULTS / "final_rows.json").read_text())
    required_slots = {r["slot_id"] for r in ledgers if r["backend"] == "upmem" and r["issued"] and not r["warmup"]}
    selected = []
    for row in observations:
        assert row["issued"] in ("True", "False") and row["warmup"] in ("True", "False")
        if row["backend"] == "upmem" and row["issued"] == "True" and row["warmup"] == "False":
            selected.append(row)
    assert len(selected) == len(required_slots)
    assert {r["slot_id"] for r in selected} == required_slots
    groups = defaultdict(list)
    for row in selected:
        # Missing, malformed or nonfinite validation values stop generation;
        # no source error is silently removed from the aggregation.
        assert row["status"] == "success", row["slot_id"]
        arm = json.loads(row["arm"])
        assert arm["backend"] == "upmem"
        assert row["phase"] in ("calibration", "final")
        assert arm["policy"] in ("split_complex_float32_v1", "complex_int8_shared_scale_v1")
        validation = json.loads(row["validation"])
        for key in ("max_abs", "relative_l2", "norm_drift", "fidelity_normalized"):
            assert isinstance(validation[key], (int, float)) and math.isfinite(validation[key]), (row["slot_id"], key)
        assert type(validation["elementwise_allclose"]) is bool and type(validation["finite"]) is bool
        assert row["same_policy_passed"] in ("True", "False") and row["finite"] in ("True", "False")
        assert validation["finite"] == (row["finite"] == "True")
        groups[(row["phase"], arm["policy"], row["case_id"])].append((row, arm, validation))
    assert len(groups) == 110
    sections = (
        ("calibration", "split_complex_float32_v1", "Calibration · float32", 9),
        ("calibration", "complex_int8_shared_scale_v1", "Calibration · shared-scale int8 (approximate)", 9),
        ("final", "split_complex_float32_v1", "Final · float32", 46),
        ("final", "complex_int8_shared_scale_v1", "Final · shared-scale int8 (approximate)", 46),
    )
    out = ["#set text(size: 8pt)"]
    for phase, policy, label, expected_count in sections:
        keys = sorted(k for k in groups if k[:2] == (phase, policy))
        assert len(keys) == expected_count
        out += ["#table(",
                "  columns: (26mm, 12mm, 13mm, 27mm, 19mm, 19mm, 20mm, 24mm),",
                "  align: (left, right, right, center, right, right, right, right),",
                "  inset: (x: 2pt, y: 3pt), stroke: none,",
                "  table.header(repeat: true,",
                f"    table.cell(colspan: 8, align: left, text(weight: \"bold\", {json.dumps(label, ensure_ascii=False)})),",
                "    table.hline(stroke: 0.6pt),",
                "    " + ", ".join(cell(h) for h in ("Case", "Configs", "Samples", "FP / replay passes", "Max abs.", "Max rel. L2", "Max norm drift", "Min fidelity")) + ",",
                "    table.hline(stroke: 0.4pt)),"]
        for key in keys:
            records = groups[key]
            configurations = {json.dumps(arm, sort_keys=True) for _, arm, _ in records}
            assert len(configurations) == len({row["cell_id"] for row, _, _ in records})
            n = len(records)
            fp = sum(v["elementwise_allclose"] for _, _, v in records)
            replay = sum(row["same_policy_passed"] == "True" for row, _, _ in records)
            values = [max(v[k] for _, _, v in records) for k in ("max_abs", "relative_l2", "norm_drift")]
            fidelity = min(v["fidelity_normalized"] for _, _, v in records)
            row = (key[2], len(configurations), n, f"{fp}/{n}; {replay}/{n}",
                   *(f"{value:.3g}" for value in values), f"{fidelity:.8f}")
            out.append("  " + ", ".join(map(cell, row)) + ",")
        out += ["  table.hline(stroke: 0.6pt),", ")", "#v(6pt)"]
    finite_count = sum(row["finite"] == "True" for row in selected)
    out += ["#text(" + json.dumps(
        f"Notes: All 110 UPMEM case/policy/phase groups are included: 9 float32 + 9 int8 calibration groups and 46 + 46 final groups, including supplementary Stress and calibration GHZ. Each row aggregates ALL issued non-warmup observations across configurations and measured blocks; extrema need not come from one configuration or observation. Configs counts distinct execution arms; Samples counts observations. FP is the elementwise full-precision-reference validation count and replay is the same-policy validation count, each shown as passes/samples. All {finite_count}/{len(selected)} included outputs are finite. Shared-scale int8 is approximate: its finite/accuracy_qualified flag is not a full-precision quality pass, and this table uses elementwise_allclose for FP. Errors and normalized fidelity are reported against the independent reference. Maximum norm drift uses norm_drift (not probability_norm_drift). Fidelity uses eight decimal places; other measurements use three significant figures only at display. Source values are neither clamped nor rounded before aggregation. Unsupported unissued routes have no validation observations. Warmups and CPU observations are outside this table. Missing or malformed validation fields fail generation instead of being dropped.", ensure_ascii=False) + ")",
            '#text(" Source: ")#link("https://github.com/kazulak/masters-thesis/blob/c7c6cac0b55bdff2f4c24b70397b36f89bedc45f/thesis/implementation/thesis_results/unified_final_v4/readout/observations.csv")[observations.csv at c7c6cac], with coverage checked against the calibration/final ledgers.']
    TABLE_OUTPUT.mkdir(parents=True, exist_ok=True)
    path = TABLE_OUTPUT / "app_table05_validation.typ"
    path.write_text("\n".join(out) + "\n")
    return path


if __name__ == "__main__":
    build()
