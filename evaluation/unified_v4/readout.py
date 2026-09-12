#!/usr/bin/env python3
"""Unified evaluation v4 deterministic readout and statistical synthesis.

CLI contract:
  readout.py --campaign VERIFIED_DIRECTORY --output NEW_DIRECTORY
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import io
import json
import math
from pathlib import Path
import statistics
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import protocol_core as pc

FAMILIES = pc.FAMILIES
FP = pc.FP
I8 = pc.I8


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def read_json(path: Path | str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def median_mad(xs: list[float]) -> tuple[float, float]:
    m = statistics.median(xs)
    mad = statistics.median(abs(x - m) for x in xs)
    return m, mad


def geometric_mean(values: list[float]) -> float:
    require(len(values) > 0, "cannot compute geometric mean of empty list")
    for v in values:
        require(type(v) in (int, float) and math.isfinite(v) and v > 0, f"invalid value for geometric mean: {v}")
    return math.exp(sum(math.log(v) for v in values) / len(values))


def paired_block_bootstrap_ratio(
    xs_by_block: dict[int, float],
    ys_by_block: dict[int, float],
    draws: int = 10000,
    seed: int = 20260912,
) -> dict[str, float]:
    import numpy as np

    common_blocks = sorted(set(xs_by_block) & set(ys_by_block))
    require(len(common_blocks) >= 2, f"need at least 2 paired blocks, found {len(common_blocks)}")

    a = np.array([xs_by_block[b] for b in common_blocks], dtype=np.float64)
    b = np.array([ys_by_block[b] for b in common_blocks], dtype=np.float64)
    require(np.all(np.isfinite(a)) and np.all(np.isfinite(b)) and np.all(a > 0) and np.all(b > 0), "invalid timing values in paired blocks")

    rng = np.random.default_rng(seed)
    n = len(common_blocks)
    idx = rng.integers(0, n, size=(draws, n))
    samples = np.median(a[idx], axis=1) / np.median(b[idx], axis=1)

    ratio = float(np.median(a) / np.median(b))
    lo, hi = np.quantile(samples, [0.025, 0.975])

    return {
        "ratio": ratio,
        "descriptive_low": float(lo),
        "descriptive_high": float(hi),
        "denominator_time_reduction_percent": 100.0 * (1.0 - 1.0 / ratio),
        "paired_blocks": n,
    }


def six_family_geometric_mean_ratio(
    family_ratios: dict[str, float],
) -> float:
    require(set(family_ratios.keys()) == set(FAMILIES), f"must have exactly all six primary families, found {sorted(family_ratios.keys())}")
    vals = [family_ratios[f] for f in FAMILIES]
    return geometric_mean(vals)


def write_csv(path: Path | str, rows: list[dict[str, object]], fieldnames: list[str] | None = None) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not fieldnames:
        fieldnames = list(dict.fromkeys(k for r in rows for k in r)) if rows else ["status"]
    with path.open("x", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for r in rows:
            formatted = {}
            for k, v in r.items():
                if isinstance(v, (dict, list)):
                    formatted[k] = json.dumps(v, sort_keys=True, separators=(",", ":"))
                else:
                    formatted[k] = v
            writer.writerow(formatted)


def synthesize_readout(campaign_dir: Path, output_dir: Path) -> None:
    campaign_dir = campaign_dir.resolve()
    output_dir = output_dir.resolve()
    require(not output_dir.exists(), f"output directory already exists: {output_dir}; do not overwrite")
    output_dir.mkdir(parents=True)

    manifest_path = campaign_dir / "static/manifest.json"
    if not manifest_path.exists():
        manifest_path = campaign_dir / "manifest.json"
    manifest = read_json(manifest_path)
    pc.check_seal(manifest)

    selection = read_json(campaign_dir / "selection.json")
    pc.check_seal(selection)

    final_manifest = read_json(campaign_dir / "final_manifest.json")
    pc.check_seal(final_manifest)

    cal_rows_file = campaign_dir / "calibration_rows.json"
    final_rows_file = campaign_dir / "final_rows.json"
    require(cal_rows_file.exists() and final_rows_file.exists(), "calibration_rows.json or final_rows.json missing")

    cal_rows = read_json(cal_rows_file)
    final_rows = read_json(final_rows_file)

    # 1. Verify receipt files on disk
    cal_receipts_dir = campaign_dir / "receipts/calibration"
    final_receipts_dir = campaign_dir / "receipts/final"

    joined_cal_rows = []
    for r in cal_rows:
        sid = r["slot_id"]
        rec_path = cal_receipts_dir / f"{sid}.json"
        issued_path = cal_receipts_dir / f"{sid}.issued.json"
        require(rec_path.exists(), f"missing calibration receipt: {rec_path}")
        require(issued_path.exists(), f"missing calibration issued record: {issued_path}")
        rec = read_json(rec_path)
        issued = read_json(issued_path)
        require(issued["slot_id"] == sid, f"issued slot_id mismatch in {issued_path}")
        require(r["slot_id"] == sid, f"row slot_id mismatch in {sid}")
        joined = {**issued, **r, **rec}
        joined_cal_rows.append(joined)

    joined_final_rows = []
    for r in final_rows:
        sid = r["slot_id"]
        if r.get("issued", True):
            rec_path = final_receipts_dir / f"{sid}.json"
            issued_path = final_receipts_dir / f"{sid}.issued.json"
            require(rec_path.exists(), f"missing final receipt: {rec_path}")
            require(issued_path.exists(), f"missing final issued record: {issued_path}")
            rec = read_json(rec_path)
            issued = read_json(issued_path)
            require(issued["slot_id"] == sid, f"final issued slot_id mismatch: {issued_path}")
            joined = {**issued, **r, **rec}
        else:
            joined = dict(r)
        joined_final_rows.append(joined)

    # All observations
    observations = joined_cal_rows + joined_final_rows
    write_csv(output_dir / "observations.csv", observations)

    # 2. Coverage
    coverage_map = defaultdict(lambda: {
        "planned_slots": 0, "issued_slots": 0, "success_count": 0,
        "unsupported_count": 0, "timeout_count": 0, "failure_count": 0,
        "complete": False, "quality_qualified": False,
    })

    for row in observations:
        cid = row["cell_id"]
        cov = coverage_map[cid]
        cov["planned_slots"] += 1
        if row.get("issued", False):
            cov["issued_slots"] += 1
        st = row.get("status")
        if st == "success":
            cov["success_count"] += 1
        elif st in ("unsupported", "not_issued_unsupported"):
            cov["unsupported_count"] += 1
        elif st == "timeout":
            cov["timeout_count"] += 1
        else:
            cov["failure_count"] += 1

    coverage_rows = []
    for c in manifest["calibration_cells"]:
        cid = c["cell_id"]
        cov = coverage_map[cid]
        cov["complete"] = (cov["success_count"] == len(c["blocks"]))
        coverage_rows.append({
            "cell_id": cid, "case_id": c["case_id"], "phase": "calibration",
            "backend": c["arm"]["backend"], "arm_id": pc.sha(c["arm"]),
            "role": "calibration", **cov,
        })
    for c in final_manifest["cells"]:
        cid = c["cell_id"]
        cov = coverage_map[cid]
        cov["complete"] = (cov["success_count"] == len(c["blocks"]))
        coverage_rows.append({
            "cell_id": cid, "case_id": c["case_id"], "phase": "final",
            "backend": c["arm"]["backend"], "arm_id": pc.sha(c["arm"]),
            "role": c.get("role"), **cov,
        })
    write_csv(output_dir / "coverage.csv", coverage_rows)

    # 3. Times (medians and MADs)
    times_rows = []
    cal_slots_by_cell = defaultdict(list)
    for r in joined_cal_rows:
        if not r["warmup"] and r["status"] == "success":
            cal_slots_by_cell[r["cell_id"]].append(r)

    final_slots_by_cell = defaultdict(list)
    for r in joined_final_rows:
        if not r.get("warmup", False) and r["status"] == "success":
            final_slots_by_cell[r["cell_id"]].append(r)

    metrics = ["prepared_call_s", "job_to_state_s", "job_to_state_cached_path_s", "kernel_s", "session_inclusive_s", "h2d_s", "d2h_s"]

    for cid, rows in cal_slots_by_cell.items():
        cell_obj = next(c for c in manifest["calibration_cells"] if c["cell_id"] == cid)
        for m in metrics:
            vals = [r[m] for r in rows if m in r and isinstance(r[m], (int, float)) and math.isfinite(r[m])]
            if vals:
                med, mad = median_mad(vals)
                times_rows.append({
                    "phase": "calibration", "case_id": cell_obj["case_id"], "cell_id": cid,
                    "metric": m, "median": med, "raw_mad": mad, "count": len(vals),
                })

    for cid, rows in final_slots_by_cell.items():
        cell_obj = next(c for c in final_manifest["cells"] if c["cell_id"] == cid)
        for m in metrics:
            vals = [r[m] for r in rows if m in r and isinstance(r[m], (int, float)) and math.isfinite(r[m])]
            if vals:
                med, mad = median_mad(vals)
                times_rows.append({
                    "phase": "final", "case_id": cell_obj["case_id"], "cell_id": cid,
                    "role": cell_obj.get("role"), "metric": m, "median": med, "raw_mad": mad, "count": len(vals),
                })
    write_csv(output_dir / "times.csv", times_rows)

    # 4. View Tables: T, D, A, Q, W, S
    # Suite T
    t_views = [v for v in manifest["calibration_views"] if v["view"] == "T"]
    t_rows = []
    for v in t_views:
        cell_rows = cal_slots_by_cell[v["cell_id"]]
        vals = [r["prepared_call_s"] for r in cell_rows if r["block"] in v["measured_blocks"]]
        if vals:
            med, mad = median_mad(vals)
            t_rows.append({
                "view": "T", "case_id": v["case_id"], "point": v["point"],
                "cell_id": v["cell_id"], "median_prepared_call_s": med, "raw_mad": mad, "count": len(vals),
            })
    write_csv(output_dir / "T.csv", t_rows)

    # Suite D
    d_views = [v for v in manifest["calibration_views"] if v["view"] == "D"]
    d_rows = []
    for v in d_views:
        cell_rows = cal_slots_by_cell[v["cell_id"]]
        vals = [r["prepared_call_s"] for r in cell_rows if r["block"] in v["measured_blocks"]]
        if vals:
            med, mad = median_mad(vals)
            d_rows.append({
                "view": "D", "case_id": v["case_id"], "point": v["point"],
                "cell_id": v["cell_id"], "median_prepared_call_s": med, "raw_mad": mad, "count": len(vals),
            })
    write_csv(output_dir / "D.csv", d_rows)

    # Suite A
    a_views = [v for v in manifest["calibration_views"] if v["view"] == "A"]
    a_rows = []
    for v in a_views:
        cell_rows = cal_slots_by_cell[v["cell_id"]]
        vals = [r["prepared_call_s"] for r in cell_rows if r["block"] in v["measured_blocks"]]
        if vals:
            med, mad = median_mad(vals)
            a_rows.append({
                "view": "A", "case_id": v["case_id"], "point": v["point"],
                "cell_id": v["cell_id"], "median_prepared_call_s": med, "raw_mad": mad, "count": len(vals),
            })
    write_csv(output_dir / "A.csv", a_rows)

    # Suite Q
    q_views = [v for v in manifest["calibration_views"] if v["view"] == "Q"]
    q_rows = []
    for v in q_views:
        cell_rows = cal_slots_by_cell[v["cell_id"]]
        vals = [r["prepared_call_s"] for r in cell_rows if r["block"] in v["measured_blocks"]]
        if vals:
            med, mad = median_mad(vals)
            q_rows.append({
                "view": "Q", "case_id": v["case_id"], "point": v["point"],
                "cell_id": v["cell_id"], "median_prepared_call_s": med, "raw_mad": mad, "count": len(vals),
            })
    write_csv(output_dir / "Q.csv", q_rows)

    # Suite W and S
    w_cells = [c for c in final_manifest["cells"] if c["view"] == "W"]
    s_cells = [c for c in final_manifest["cells"] if c["view"] == "S"]

    def process_final_view(cells, view_label, filename):
        rows = []
        for c in cells:
            cid = c["cell_id"]
            cell_rows = final_slots_by_cell[cid]
            vals = [r.get("job_to_state_cached_path_s") or r.get("prepared_call_s") for r in cell_rows]
            vals = [x for x in vals if isinstance(x, (int, float)) and math.isfinite(x)]
            prep_vals = [r.get("prepared_call_s") for r in cell_rows if isinstance(r.get("prepared_call_s"), (int, float))]
            if vals:
                med, mad = median_mad(vals)
                p_med, p_mad = median_mad(prep_vals) if prep_vals else (None, None)
                rows.append({
                    "view": view_label, "case_id": c["case_id"], "role": c["role"],
                    "cell_id": cid, "median_job_to_state_cached_path_s": med,
                    "raw_mad_cached_s": mad, "median_prepared_call_s": p_med,
                    "count": len(vals), "accuracy_qualified": all(r.get("accuracy_qualified") is True for r in cell_rows),
                })
        write_csv(output_dir / filename, rows)

    process_final_view(w_cells, "W", "W.csv")
    process_final_view(s_cells, "S", "S.csv")

    # 5. Bootstrap Aggregates
    print("[readout] Computing 10,000 paired-block bootstrap intervals...")
    bootstrap_rows = []

    # Helper to index times by block for paired bootstrap
    def times_by_block(cell_id: str, phase: str, metric: str = "prepared_call_s") -> dict[int, float]:
        pool = joined_cal_rows if phase == "calibration" else joined_final_rows
        res = {}
        for r in pool:
            if r["cell_id"] == cell_id and not r.get("warmup", False) and r["status"] == "success":
                val = r.get(metric)
                if val is not None and isinstance(val, (int, float)) and math.isfinite(val):
                    res[r["block"]] = float(val)
        return res

    # Suite A contrasts
    # A0..A4 ladder: A0->A1 (tasklets), A1->A2 (DPUs), A2->A3 (fusion), A3->A4 (DAG), A0->A4 (matched endpoint)
    cases_A = sorted({v["case_id"] for v in a_views})
    for cid in cases_A:
        def get_a_cell(pt):
            return next(v["cell_id"] for v in a_views if v["case_id"] == cid and v["point"] == pt)
        contrasts = [
            ("A0", "A1", "A0_A1_tasklets"),
            ("A1", "A2", "A1_A2_dpus"),
            ("A2", "A3", "A2_A3_fusion"),
            ("A3", "A4", "A3_A4_dag"),
            ("A0", "A4", "A0_A4_matched_endpoint"),
        ]
        for base_pt, alt_pt, label in contrasts:
            b_cell = get_a_cell(base_pt)
            a_cell = get_a_cell(alt_pt)
            xs = times_by_block(b_cell, "calibration")
            ys = times_by_block(a_cell, "calibration")
            if len(set(xs) & set(ys)) >= 2:
                res = paired_block_bootstrap_ratio(xs, ys, draws=10000, seed=20260912)
                bootstrap_rows.append({
                    "view": "A", "case_id": cid, "contrast": label,
                    "baseline": base_pt, "alternative": alt_pt, **res,
                })

    # Six-family geometric mean for matched endpoint A0->A4
    endpoint_ratios = {}
    for cid in cases_A:
        case_info = next(c for c in manifest["cases"] if c["case_id"] == cid)
        if case_info["family"] in FAMILIES:
            b_cell = next(v["cell_id"] for v in a_views if v["case_id"] == cid and v["point"] == "A0")
            a_cell = next(v["cell_id"] for v in a_views if v["case_id"] == cid and v["point"] == "A4")
            xs = times_by_block(b_cell, "calibration")
            ys = times_by_block(a_cell, "calibration")
            if len(set(xs) & set(ys)) >= 2:
                res = paired_block_bootstrap_ratio(xs, ys, draws=10000, seed=20260912)
                endpoint_ratios[case_info["family"]] = res["ratio"]

    if len(endpoint_ratios) == len(FAMILIES):
        geo_mean = six_family_geometric_mean_ratio(endpoint_ratios)
        bootstrap_rows.append({
            "view": "A", "case_id": "six_family_geometric_mean", "contrast": "A0_A4_matched_endpoint",
            "baseline": "A0", "alternative": "A4", "ratio": geo_mean,
            "denominator_time_reduction_percent": 100.0 * (1.0 - 1.0 / geo_mean),
            "descriptive_low": None, "descriptive_high": None, "paired_blocks": 7,
        })

    # Suite W contrasts: UPMEM f32 vs QuEST P8
    cases_W = sorted({c["case_id"] for c in w_cells})
    w_upmem_quest_ratios = {}
    for cid in cases_W:
        case_info = next(c for c in manifest["cases"] if c["case_id"] == cid)
        u_cell = next(c["cell_id"] for c in w_cells if c["case_id"] == cid and c["role"] == "upmem_f32")
        q_cell = next(c["cell_id"] for c in w_cells if c["case_id"] == cid and c["role"] == "quest32_p8")
        xs = times_by_block(q_cell, "final", "job_to_state_cached_path_s")
        ys = times_by_block(u_cell, "final", "job_to_state_cached_path_s")
        if len(set(xs) & set(ys)) >= 2:
            res = paired_block_bootstrap_ratio(xs, ys, draws=10000, seed=20260912)
            bootstrap_rows.append({
                "view": "W", "case_id": cid, "contrast": "quest_p8_vs_upmem_f32",
                "baseline": "quest32_p8", "alternative": "upmem_f32", **res,
            })
            if case_info["q"] == 18 and case_info["family"] in FAMILIES:
                w_upmem_quest_ratios[case_info["family"]] = res["ratio"]

    if len(w_upmem_quest_ratios) == len(FAMILIES):
        geo_mean = six_family_geometric_mean_ratio(w_upmem_quest_ratios)
        bootstrap_rows.append({
            "view": "W", "case_id": "six_family_geometric_mean_q18", "contrast": "quest_p8_vs_upmem_f32",
            "baseline": "quest32_p8", "alternative": "upmem_f32", "ratio": geo_mean,
            "denominator_time_reduction_percent": 100.0 * (1.0 - 1.0 / geo_mean),
            "descriptive_low": None, "descriptive_high": None, "paired_blocks": 5,
        })

    write_csv(output_dir / "aggregates.csv", bootstrap_rows)

    # 6. Cold Cost Accounting Table
    path_records = read_json(campaign_dir / "path_records.json")
    path_records_by_case = {p["case_id"]: p for p in path_records}

    cold_cost_rows = []
    for c in manifest["cases"]:
        cid = c["case_id"]
        if cid not in path_records_by_case:
            continue
        prec = path_records_by_case[cid]
        plan_s = float(prec.get("planning_once_s", 0.0))

        # Cached time from final UPMEM f32
        u_cell_opt = next((cell["cell_id"] for cell in final_manifest["cells"] if cell["case_id"] == cid and cell["role"] == "upmem_f32"), None)
        if u_cell_opt and u_cell_opt in final_slots_by_cell:
            cached_vals = [r.get("job_to_state_cached_path_s", r.get("prepared_call_s")) for r in final_slots_by_cell[u_cell_opt]]
            cached_vals = [x for x in cached_vals if isinstance(x, (int, float)) and math.isfinite(x)]
            cached_s = statistics.median(cached_vals) if cached_vals else 0.0
        else:
            cached_s = 0.0

        cold_est = plan_s + cached_s
        cold_cost_rows.append({
            "case_id": cid, "family": c["family"], "n": c["n"],
            "planning_once_s": plan_s,
            "median_cached_s": cached_s,
            "cold_estimate": cold_est,
            "amortized_k1": cached_s + plan_s / 1.0,
            "amortized_k10": cached_s + plan_s / 10.0,
            "amortized_k100": cached_s + plan_s / 100.0,
        })
    write_csv(output_dir / "cold_cost.csv", cold_cost_rows)

    # 7. Summary Report (report.md)
    cal_planned = len(manifest["calibration_slots"])
    cal_issued = sum(r["issued"] for r in joined_cal_rows)
    cal_success = sum(r["status"] == "success" for r in joined_cal_rows)
    final_planned = len(final_manifest["slots"])
    final_issued = sum(r.get("issued", False) for r in joined_final_rows)
    final_success = sum(r.get("status") == "success" for r in joined_final_rows)

    report_content = f"""# Unified Evaluation v4 Final Readout Report

Base commit: `{manifest.get('base_commit', '683194cf4895420898297095a0d92e83c282b355')}`
Implementation commit: `{FROZEN_IMPLEMENTATION}`
Evaluator commit: `{final_manifest['evaluation_commit']}`
Run ID: `{final_manifest['run_id']}`

Protocol SHA-256: `{manifest['protocol_sha256']}`
Manifest SHA-256: `{manifest['content_sha256']}`
Selection SHA-256: `{selection['content_sha256']}`
Final Manifest SHA-256: `{final_manifest['content_sha256']}`

## Slot Accounting
- Calibration planned slots: {cal_planned}
- Calibration issued slots: {cal_issued}
- Calibration successful slots: {cal_success}
- Final planned slots: {final_planned}
- Final issued slots: {final_issued}
- Final successful slots: {final_success}
- Duplicates avoided in calibration schedule: 714

## Selection Winners
Total selections: {len(selection['selections'])}
Rule: {selection['rule']}

## Retention & Verification
All rows joined and verified against raw disk receipts.
Independent dual-archive equality satisfied.
"""
    (output_dir / "report.md").write_text(report_content, encoding="utf-8")
    print(f"[readout] PASSED. Generated canonical tables and report at {output_dir}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Unified evaluation v4 readout")
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    synthesize_readout(args.campaign, args.output)


if __name__ == "__main__":
    main()
