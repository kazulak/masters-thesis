#!/usr/bin/env python3
"""Unified evaluation v4 deterministic readout and statistical synthesis.

CLI contract:
  readout.py --campaign VERIFIED_DIRECTORY --output NEW_DIRECTORY
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import protocol_core as pc  # noqa: E402 - standalone script import

FAMILIES = pc.FAMILIES
FP = pc.FP
I8 = pc.I8
FROZEN_IMPLEMENTATION = "f6b570a98a610d41b5b16401a42ce12a94042d38"
PUBLISHED_RESULT = "d886e3b7e04a4c3be4a6d4d463206b66f5c0c2a0"
R_ROLES = ("upmem_f32", "upmem_int8", "numpy_f32_p1")
FINAL_ROLES = (*R_ROLES, "quest32_p8", "quest32_p1")


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


def derive_accounting(manifest, final_manifest, cal_rows, final_rows, path_records, retention):
    """Reconcile planned identities and observed outcomes; never infer issues from allocations."""
    pc.check_seal(manifest)
    pc.check_seal(final_manifest)
    for key, expected in {
        "run_id": final_manifest["run_id"], "implementation_commit": FROZEN_IMPLEMENTATION,
        "evaluator_commit": final_manifest["evaluation_commit"], "protocol_sha256": manifest["protocol_sha256"],
        "static_manifest_sha256": manifest["content_sha256"], "selection_sha256": final_manifest["selection_sha256"],
        "final_manifest_sha256": final_manifest["content_sha256"],
    }.items():
        require(retention.get(key) == expected, f"retention identity mismatch: {key}")
    paths = {p["case_id"]: p for p in path_records}
    cases = {c["case_id"] for c in final_manifest["cells"]}
    require(len(paths) == len(path_records) and set(paths) == cases, "missing/duplicate/wrong path cases")
    for p in path_records:
        pc.check_seal(p)
        require(p["selection_sha256"] == final_manifest["selection_sha256"], "path selection mismatch")
        if p["status"] == "selected":
            require(p["admitted_candidate_count"] > 0 and p["reason"] is None, "invalid selected path")
            require(p["path_sha256"] == pc.sha(p["path"]), "selected path bytes mismatch")
        else:
            require(p["status"] == "no_selected_R_path" and p["reason"] == "no_admitted_candidate"
                    and p["admitted_candidate_count"] == 0 and p["path_id"] is None
                    and p["path_sha256"] is None, "unrecognized path frontier")
    require(pc.sha(sorted(path_records, key=lambda p: p["case_id"])) == final_manifest["path_records_sha256"],
            "path records binding mismatch")

    def reconcile(slots, cells, rows, final):
        wanted = {s["slot_id"]: s for s in slots}
        cell_map = {c["cell_id"]: c for c in cells}
        require(len(wanted) == len(slots) and len(cell_map) == len(cells), "duplicate planned identity")
        require(len(rows) == len(wanted), "incomplete slot ledger")
        seen = set()
        counts = defaultdict(Counter)
        outcomes = Counter()
        for r in rows:
            sid = r["slot_id"]
            require(sid in wanted and sid not in seen, "unexpected/duplicate slot")
            seen.add(sid)
            s = wanted[sid]
            for key in ("cell_id", "case_id", "block", "warmup", "phase", "backend", "protocol_sha256"):
                require(type(r.get(key)) is type(s[key]) and r[key] == s[key], f"slot identity mismatch: {key}")
            for key in ("run_id", "evaluation_commit"):
                require(r.get(key) == final_manifest[key], f"row provenance mismatch: {key}")
            require(r.get("implementation_commit") == FROZEN_IMPLEMENTATION, "wrong implementation")
            require(type(r.get("issued")) is bool, "issued must be explicit boolean")
            cell = cell_map[r["cell_id"]]
            role = cell["role"] if final else "upmem"
            if final:
                require(role in FINAL_ROLES, "unknown final route")
                path = paths[r["case_id"]]
                available = role not in R_ROLES or path["status"] == "selected"
                require(cell["eligible_for_runtime_admission"] is available, "path/cell eligibility mismatch")
                if role in R_ROLES:
                    require(cell["selected_path_sha256"] == path["path_sha256"], "route path mismatch")
            else:
                available = True
            expected = (True, "success", None) if available else (False, "not_issued_unsupported", "no_selected_R_path")
            require((r["issued"], r["status"], r.get("reason")) == expected,
                    f"inconsistent issued/status/reason for {sid}")
            if not available:
                require(all(r.get(k) is None for k in ("prepared_call_s", "job_to_state_cached_path_s", "job_to_state_s")),
                        "unsupported slot has runtime")
            elif final:
                pc.positive(r.get("job_to_state_cached_path_s"), "missing cached job-to-state timing")
            c = counts[role]
            c["planned"] += 1
            c["issued"] += int(r["issued"])
            c["success"] += int(r["status"] == "success")
            c["not_issued"] += int(not r["issued"])
            outcomes[(role, r["issued"], r["status"], r.get("reason"))] += 1
        require(seen == set(wanted), "missing slot")
        return dict(counts), [{"route": role, "issued": issued, "status": status, "reason": reason, "count": n}
                              for (role, issued, status, reason), n in sorted(outcomes.items())]

    calibration, _ = reconcile(manifest["calibration_slots"], manifest["calibration_cells"], cal_rows, False)
    routes, outcomes = reconcile(final_manifest["slots"], final_manifest["cells"], final_rows, True)
    require(set(routes) == set(FINAL_ROLES), "missing final route")
    total = {k: sum(c[k] for c in routes.values()) for k in ("planned", "issued", "success", "not_issued")}
    counts = manifest["counts"]
    attempts = retention["attempt_counts"]
    for prefix, actual in (("calibration", calibration["upmem"]), ("final", total)):
        for key in ("planned", "issued", "success"):
            require(attempts[f"{prefix}_{key}_slots"] == actual[key], "retention slot count mismatch")
    require(attempts["final_not_issued_unsupported"] == total["not_issued"], "retention unsupported mismatch")
    require(attempts["r_path_searches"] == len(paths) == counts["final_searches"], "search count mismatch")
    require(attempts["r_path_proposals"] == counts["final_search_proposals"], "proposal count mismatch")
    configurations = len({q["configuration_id"] for q in manifest["qualification"]})
    require(configurations == counts["upmem_execution_configurations"], "qualification configuration mismatch")
    for observed, planned in (("qualification_upmem_phy", "physical_qualification_attempts"),
                              ("qualification_upmem_sim", "simulator_qualification_attempts"),
                              ("qualification_quest", "quest_qualification_calls"),
                              ("qualification_tiny_r_searches", "small_R_qualification_searches")):
        require(attempts[observed] == counts[planned], "qualification count mismatch")
    physical_final = {k: sum(routes[role][k] for role in ("upmem_f32", "upmem_int8")) for k in total}
    physical_issued = attempts["qualification_upmem_phy"] + calibration["upmem"]["issued"] + physical_final["issued"]
    ceiling = counts["physical_attempt_ceiling_including_qualification"]
    require(physical_issued <= ceiling, "physical issue ceiling exceeded")
    return {
        "schema": "unified_v4_reporting_accounting_v1", "published_result_commit": PUBLISHED_RESULT,
        "run_id": final_manifest["run_id"], "calibration": dict(calibration["upmem"]),
        "calibration_cells": len(manifest["calibration_cells"]), "final_cells": len(final_manifest["cells"]),
        "final": total, "routes": {r: dict(routes[r]) for r in FINAL_ROLES}, "route_outcomes": outcomes,
        "paths": {"searches": len(paths), "proposals": attempts["r_path_proposals"],
                  "selected": sum(p["status"] == "selected" for p in paths.values()),
                  "no_selected": sum(p["status"] == "no_selected_R_path" for p in paths.values()),
                  "frontiers": [{k: p[k] for k in ("case_id", "status", "reason", "admitted_candidate_count")}
                                for p in sorted(paths.values(), key=lambda p: p["case_id"]) if p["status"] != "selected"]},
        "qualification": {"configurations": configurations, "physical": attempts["qualification_upmem_phy"],
                          "simulator": attempts["qualification_upmem_sim"], "quest": attempts["qualification_quest"],
                          "tiny_r_searches": attempts["qualification_tiny_r_searches"]},
        "physical": {"final": physical_final, "issued": physical_issued, "ceiling": ceiling},
        "deduplicated_slots": counts["duplicate_slots_avoided_within_calibration"],
        "archive_files_count": retention["archive_files_count"],
        "archive_verification_source": "frozen retention.json; equality must be checked separately",
    }


def cold_cost_row(case, path, measured_rows):
    plan_s = path["planning_once_s"]
    pc.positive(plan_s, "missing R-path preparation/search time")
    out = {"case_id": case["case_id"], "family": case["family"], "n": case["n"],
           "path_status": path["status"], "path_reason": path["reason"], "planning_once_s": plan_s,
           "median_cached_s": None, "cold_estimate": None,
           "amortized_k1": None, "amortized_k10": None, "amortized_k100": None}
    if path["status"] != "selected":
        require(path["status"] == "no_selected_R_path" and not measured_rows, "unexpected unavailable-path measurements")
        return out
    require(measured_rows, "selected path has no cached execution measurements")
    values = [r.get("job_to_state_cached_path_s") for r in measured_rows]
    for v in values:
        pc.positive(v, "missing/nonpositive cached job-to-state timing")
    cached = statistics.median(values)
    out.update(median_cached_s=cached, cold_estimate=plan_s + cached,
               amortized_k1=cached + plan_s, amortized_k10=cached + plan_s / 10,
               amortized_k100=cached + plan_s / 100)
    return out


def join_receipts(row, issued, receipt):
    """A native receipt may enrich a ledger row but may not silently override it."""
    for source in (issued, receipt):
        require(source.get("slot_id") == row["slot_id"], "disk receipt slot mismatch")
    for left, right in ((row, issued), (row, receipt), (issued, receipt)):
        for key in left.keys() & right.keys():
            require(type(left[key]) is type(right[key]) and left[key] == right[key],
                    f"conflicting disk receipt field: {key} ({row['slot_id']})")
    return {**issued, **row, **receipt}


def synthesize_readout(campaign_dir: Path, output_dir: Path, retention_path: Path | None = None) -> None:
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
    path_records = read_json(campaign_dir / "path_records.json")
    spec = read_json(HERE / "protocol.json")
    pc.validate_calibration_rows(spec, manifest, cal_rows)
    require(pc.materialize_final(spec, manifest, selection, path_records) == final_manifest,
            "final manifest differs from frozen inputs")
    if retention_path is None:
        retention_path = HERE.parents[1] / "thesis/implementation/thesis_results/unified_final_v4/retention.json"
    retention = read_json(retention_path)
    require(retention["run_id"] == final_manifest["run_id"], "retention run mismatch")
    require(retention["base_commit"] == spec["base_commit"], "retention base commit mismatch")
    for filename in ("calibration_rows", "final_rows", "path_records"):
        require(hashlib.sha256((campaign_dir / f"{filename}.json").read_bytes()).hexdigest() == retention[f"{filename}_sha256"],
                f"retention digest mismatch: {filename}")
    accounting = derive_accounting(manifest, final_manifest, cal_rows, final_rows, path_records, retention)
    pc.write_new_json(output_dir / "accounting.json", accounting)

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
        joined = join_receipts(r, issued, rec)
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
            joined = join_receipts(r, issued, rec)
        else:
            joined = dict(r)
        joined_final_rows.append(joined)

    # All observations
    observations = joined_cal_rows + joined_final_rows

    def strip_large_facts(obj: object) -> object:
        if isinstance(obj, dict):
            return {
                k: strip_large_facts(v)
                for k, v in obj.items()
                if k not in ("backend_facts", "numeric_facts", "terminal_facts", "native_stdout", "stdout")
            }
        elif isinstance(obj, list):
            return [strip_large_facts(x) for x in obj]
        return obj

    write_csv(output_dir / "observations.csv", [strip_large_facts(r) for r in observations])

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

    # 6. Search costs and derived simulation-call estimates.
    path_records_by_case = {p["case_id"]: p for p in path_records}
    cells_by_case = {c["case_id"]: c["cell_id"] for c in final_manifest["cells"] if c["role"] == "upmem_f32"}
    cold_cost_rows = [cold_cost_row(c, path_records_by_case[c["case_id"]],
                                  final_slots_by_cell.get(cells_by_case[c["case_id"]], []))
                      for c in manifest["cases"] if c["case_id"] in path_records_by_case]
    write_csv(output_dir / "cold_cost.csv", cold_cost_rows)

    # 7. The report and publication table consume the same reconciled counts.
    a = accounting
    report = [
        "# Unified Evaluation v4 Corrected Readout Receipt", "",
        f"Original published result commit: `{a['published_result_commit']}`",
        f"Base commit: `{retention['base_commit']}`",
        f"Implementation commit: `{retention['implementation_commit']}`",
        f"Evaluator commit: `{final_manifest['evaluation_commit']}`",
        f"Run ID: `{final_manifest['run_id']}`", "",
        f"Protocol SHA-256: `{manifest['protocol_sha256']}`",
        f"Manifest SHA-256: `{manifest['content_sha256']}`",
        f"Selection SHA-256: `{selection['content_sha256']}`",
        f"Final Manifest SHA-256: `{final_manifest['content_sha256']}`", "",
        "## Slot accounting", "",
        f"Calibration: {a['calibration']['planned']} planned, {a['calibration']['issued']} issued, "
        f"{a['calibration']['success']} successful; {a['deduplicated_slots']} duplicate slots avoided.", "",
        "| Final route | Planned | Issued | Successful | Not issued |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for role, c in [*a['routes'].items(), ('Total', a['final'])]:
        report.append(f"| {role} | {c['planned']} | {c['issued']} | {c['success']} | {c['not_issued']} |")
    p = a['paths']
    report += ["", "## R-path admission outcomes", "",
               f"{p['searches']} searches, {p['proposals']} proposals, {p['selected']} selected R paths, "
               f"{p['no_selected']} no-selected-R-path outcomes.", "",
               "The following cases have `no_selected_R_path` / `no_admitted_candidate`: "
               + ", ".join(f"`{r['case_id']}`" for r in p['frontiers']) + ".", "",
               "The two UPMEM routes and NumPy same-DAG require the shared R path. "
               "Their unsupported slots were never issued. QuEST remains executable. "
               "These are planning/admission frontiers, not physical execution failures.", "",
               "## Physical campaign and retention", "",
               f"{a['qualification']['physical']} qualification + {a['calibration']['issued']} calibration + "
               f"{a['physical']['final']['issued']} final = **{a['physical']['issued']} physical issues**, "
               f"within the {a['physical']['ceiling']} ceiling. "
               f"{a['physical']['final']['not_issued']} allocated physical final slots were not issued.", "",
               f"Qualification used {a['qualification']['configurations']} configurations, each replayed twice. "
               f"The frozen retention receipt records two verified copies of {a['archive_files_count']} files. "
               "This readout joins raw disk receipts; it does not itself assert a new dual-archive byte comparison.", "",
               "## Selection and timing definitions", "",
               f"Topology winners: {len(selection['selections'])}. Rule: {selection['rule']}.", "",
               "R-path preparation/search is a one-time offline cost. Cached-path job-to-state runs from "
               "the preloaded circuit specification to an owned contiguous complete statevector with the path available. "
               "Estimated per-call cost is search/k + cached job-to-state for k=1,10,100. "
               "These are derived estimates, not separately measured cold executions. "
               "No-path cases retain search time and have no executable cached-path cost.", "",
               "One-rank DPU scaling saturated after D16, with lower aggregate speedup at D32 and D64. "
               "This observation alone does not attribute dominance to a communication mechanism.", ""]
    (output_dir / "report.md").write_text("\n".join(report), encoding="utf-8")
    print(f"[readout] PASSED. Generated canonical tables and report at {output_dir}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Unified evaluation v4 readout")
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--retention", type=Path, help="Frozen retention receipt (defaults to published v4 receipt)")
    args = parser.parse_args()
    synthesize_readout(args.campaign, args.output, args.retention)


if __name__ == "__main__":
    main()
