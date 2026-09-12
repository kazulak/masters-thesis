"""Report exact/reference errors over all issued measured primary UPMEM slots."""
import csv
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import PRIMARY_FAMILIES, ROOT, TABLE_OUTPUT, V4_READOUT, V4_RESULTS  # noqa: E402


SOURCE_BASE = "https://github.com/kazulak/masters-thesis/blob/c7c6cac0b55bdff2f4c24b70397b36f89bedc45f/"
FLOAT = "split_complex_float32_v1"
INT8 = "complex_int8_shared_scale_v1"


def measured_observations():
    with (V4_READOUT / "observations.csv").open(newline="") as stream:
        observations = list(csv.DictReader(stream))
    unique = {}
    for row in observations:
        slot = row["slot_id"]
        if not slot or (slot in unique and unique[slot] != row):
            raise ValueError(f"Missing or conflicting observation slot: {slot}")
        unique[slot] = row
    result = []
    for row in unique.values():
        if row["backend"] != "upmem" or row["issued"] != "True" or row["warmup"] != "False":
            continue
        if row["phase"] not in {"calibration", "final"} or int(row["block"]) <= 0:
            raise ValueError(f"Unexpected measured phase/block: {row['slot_id']}")
        if row["status"] != "success" or row["finite"] != "True":
            raise ValueError(f"Issued measured UPMEM slot failed or was nonfinite: {row['slot_id']}")
        row = dict(row, arm=json.loads(row["arm"]), validation=json.loads(row["validation"]))
        validation = row["validation"]
        if validation["finite"] is not True:
            raise ValueError("Nonfinite numerical validation")
        for key in ("relative_l2", "max_abs", "norm_drift", "reference_peak", "fidelity_normalized"):
            if not math.isfinite(validation[key]) or validation[key] < 0:
                raise ValueError(f"Invalid numerical metric {key}: {row['slot_id']}")
        result.append(row)
    return result


def build_rows():
    tolerances = json.loads((ROOT / "evaluation/unified_v4/protocol.json").read_text())["validation"]
    for key, expected in {"atol": 1e-5, "rtol": 1e-5, "relative_l2_max": 1e-5, "norm_drift_max": 2e-5}.items():
        if tolerances[key] != expected:
            raise ValueError(f"Unexpected frozen tolerance {key}")
    if tolerances["int8_approximation_threshold"] is not None:
        raise ValueError("Int8 approximation status needs reassessment")
    cases = {c["case_id"]: c for c in json.loads((V4_RESULTS / "manifest/manifest.json").read_text())["cases"]}
    observations = measured_observations()
    rows = []
    for family in PRIMARY_FAMILIES:
        family_rows = [r for r in observations if cases[r["case_id"]]["family"] == family]
        f32 = [r for r in family_rows if r["arm"]["policy"] == FLOAT]
        int8 = [r for r in family_rows if r["arm"]["policy"] == INT8]
        if len(f32) != 245 or len(int8) != 105 or len(family_rows) != 350:
            raise ValueError(f"Incomplete measured primary coverage for {family}: {len(f32)}, {len(int8)}")
        for samples, calibration_count in ((f32, 210), (int8, 70)):
            if sum(r["phase"] == "calibration" for r in samples) != calibration_count or sum(r["phase"] == "final" for r in samples) != 35:
                raise ValueError(f"Unexpected calibration/final coverage for {family}")
        passes = 0
        for row in f32:
            v = row["validation"]
            passed = (v["elementwise_allclose"] is True and v["relative_l2"] <= tolerances["relative_l2_max"]
                      and v["norm_drift"] <= tolerances["norm_drift_max"]
                      and v["max_abs"] <= tolerances["atol"] + tolerances["rtol"] * v["reference_peak"])
            if (row["accuracy_qualified"] == "True") != passed:
                raise ValueError(f"Float32 qualification disagrees with numerical validation: {row['slot_id']}")
            passes += passed
        rows.append(dict(family=family, f32_count=len(f32), f32_passes=passes,
                         f32_max_relative_l2=max(r["validation"]["relative_l2"] for r in f32),
                         int8_count=len(int8), int8_max_relative_l2=max(r["validation"]["relative_l2"] for r in int8),
                         int8_min_fidelity=min(r["validation"]["fidelity_normalized"] for r in int8),
                         int8_replay_passes=sum(r["same_policy_passed"] == "True" for r in int8),
                         int8_status="Approximate"))
    return rows


def stress18_max_error():
    samples = [r for r in measured_observations() if r["case_id"] == "stress_n18_l2" and r["phase"] == "final" and r["arm"]["policy"] == INT8]
    if len(samples) != 5:
        raise ValueError("Missing final Stress18 int8 quality evidence")
    return max(r["validation"]["relative_l2"] for r in samples)


def cell(value):
    return "[" + " #linebreak() ".join("#text(" + json.dumps(str(line), ensure_ascii=False) + ")" for line in str(value).split("\n")) + "]"


def main():
    rows = build_rows()
    header = ["Family", "f32 validation\npassed / total", "f32 maximum\nrelative L2", "int8 maximum\nrelative L2", "int8 minimum\nnormalized fidelity", "int8 replay\npassed / total", "int8 status"]
    lines = ["// Generated by table02_correctness.py; canonical evidence is read directly.", "#[", "#set text(size: 8pt)",
             "#set par(leading: 0.5em)", "#table(", "  columns: (14mm, 22mm, 23mm, 23mm, 30mm, 25mm, 23mm),",
             "  align: (left, right, right, right, right, right, left),", "  stroke: none, inset: (x: 2pt, y: 4pt),",
             "  table.hline(stroke: 0.6pt),", "  table.header(repeat: true, " + ", ".join(cell(v) for v in header) + "),", "  table.hline(stroke: 0.4pt),"]
    for row in rows:
        values = [row["family"].upper(), f"{row['f32_passes']} / {row['f32_count']}", f"{row['f32_max_relative_l2']:.3g}",
                  f"{row['int8_max_relative_l2']:.3g}", f"{row['int8_min_fidelity']:.8f}",
                  f"{row['int8_replay_passes']} / {row['int8_count']}", row["int8_status"]]
        lines.append("  " + ", ".join(cell(v) for v in values) + ",")
    notes = [
        "Notes: All issued, successful, finite, non-warmup UPMEM observations from calibration and final evaluation are included once per slot_id. Each family contributes 210 calibration + 35 final float32 samples and 70 calibration + 35 final int8 samples. Extrema cover every measured block, configuration and supported width, rather than only selected resources.",
        "Float32 validation checks the recorded exact/reference comparison: elementwise absolute and relative tolerances 1e−5, relative L2 ≤ 1e−5 and norm drift ≤ 2e−5. Errors and normalized fidelity come from validation JSON; same_policy_passed is a separate execution-replay check. Int8 accuracy_qualified records execution eligibility, not an approximation-error threshold; no int8 approximation threshold was declared.",
        f"The primary-family result does not generalize to every workload: final Stress18 int8 reaches {100 * stress18_max_error():.3g}% relative L2 error. See the supplementary workload-quality table for Stress and GHZ. Fidelity is shown to eight decimal places; rounded 1.00000000 does not imply exact identity.",
    ]
    lines += ["  table.hline(stroke: 0.6pt),", ")", "#v(3pt)"]
    for note in notes:
        lines += ["#text(" + json.dumps(note, ensure_ascii=False) + ")", "#parbreak()"]
    for label, path in [("Observation readout", "thesis/implementation/thesis_results/unified_final_v4/readout/observations.csv"),
                        ("Validation protocol", "evaluation/unified_v4/protocol.json")]:
        lines.append("#link(" + json.dumps(SOURCE_BASE + path) + ", " + json.dumps(label) + ") ")
    lines.append("]\n")
    TABLE_OUTPUT.mkdir(parents=True, exist_ok=True)
    (TABLE_OUTPUT / "table02_correctness.typ").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
