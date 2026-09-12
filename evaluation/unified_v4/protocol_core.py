#!/usr/bin/env python3
"""Pure manifest/selection contract for unified v4. No hardware or network calls.

Cell IDs are logical schedule identities. The runner must additionally bind actual
QASM/path/plan/binary hashes before issue; this module does not attest native output.
Worker receipts are inputs, not generated measurements. All output creation is
exclusive: an existing directory/file is a stop, not permission to replace it.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
import math
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
FAMILIES = ("bb84", "bv", "edc", "hs", "qrng", "xor")
FP = "split_complex_float32_v1"
I8 = "complex_int8_shared_scale_v1"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("utf-8")


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sealed(value):
    require("content_sha256" not in value, "already sealed")
    return {**value, "content_sha256": sha(value)}


def check_seal(value):
    body = {k: v for k, v in value.items() if k != "content_sha256"}
    require(value.get("content_sha256") == sha(body), "content seal mismatch")
    return body


def positive(value, label):
    require(type(value) in (int, float) and math.isfinite(value) and value > 0, label)
    return float(value)


def validate_spec(s):
    require(s["schema"] == "unified_final_evaluation_protocol_v4", "wrong schema")
    for key in ("tasklets", "dpus", "topology_tasklets", "width_slots"):
        require(all(type(x) is int and x > 0 for x in s[key]), "noninteger grid")
    require(tuple(s["primary_families"]) == FAMILIES, "six-family membership drift")
    require(s["tasklets"] == list(range(1, 25)), "tasklet grid drift")
    require(s["dpus"] == [1, 2, 4, 8, 16, 32, 64], "DPU grid drift")
    require(s["topology_tasklets"] == [8, 24], "topology tasklets drift")
    require(s["calibration_total_qubit_ceiling"] == 18, "calibration cohort drift")
    require(s["width_slots"] == [8,12,16,18,20,22,24,26], "width grid drift")
    require(s["rank_count"] == 1 and s["rank_capacity"] == 64, "rank scope drift")
    require(s["warmup_blocks"] == [0], "warmup convention drift")
    require(s["float_policy"] == FP and s["int8_policy"] == I8, "numeric policy drift")
    for view in ("T", "D", "Q", "W", "S"):
        require(s["measured_blocks"][view] == [1,2,3,4,5], "measurement grid drift")
    require(s["measured_blocks"]["A"] == [1,2,3,4,5,6,7], "A blocks drift")
    require(s["r_policy"]["integer_weights"] == [1,2,1,1,5], "P6 weights drift")
    require(s["r_policy"]["proposals"] == 128 and not s["r_policy"]["fit_or_renormalize"],
            "path policy drift")
    require(s["r_policy"]["shared_path_consumers"] == ["upmem_f32","upmem_int8","numpy_f32_p1"],
            "shared path consumers drift")


def case(family, q):
    n = q - 1 if family == "edc" else q
    if family in ("bb84", "qrng"):
        builder, params = "build_family_qasm", {"n_qubits": n}
    elif family in ("bv", "xor"):
        builder, params = "build_family_qasm", {"data_qubits": n - 1}
    elif family == "edc":
        require(n >= 3 and n % 2 == 1, "invalid EDC width")
        builder, params = "build_family_qasm", {"data_qubits": (n + 1) // 2}
    elif family == "hs":
        require(n >= 2 and n % 2 == 0, "invalid HS width")
        builder, params = "build_family_qasm", {"allocated_qubits": n}
    elif family == "stress":
        builder, params = "quantization_stress", {"n_qubits": n, "repeat_layers": 2}
    elif family == "ghz":
        builder, params = "ghz_chain", {"n_qubits": n}
    else:
        raise ValueError("unknown family")
    return {"case_id": f"{family}_n{n:02d}" + ("_l2" if family == "stress" else ""),
            "family": family, "q": q, "n": n, "builder": builder,
            "parameters": params, "cohort": "primary" if family in FAMILIES else "supplementary"}


def cases(s):
    result = [case(f, q) for f in FAMILIES for q in s["width_slots"]]
    result += [case("stress", n) for n in s["supplementary_widths"]]
    result += [case("ghz", 18)]
    require(len({c["case_id"] for c in result}) == len(result), "duplicate circuit")
    return sorted(result, key=lambda c: c["case_id"])


def arm(d, t, schedule="static_dag_waves_v1", fuse=True, policy=FP):
    return {"backend": "upmem", "dpus": d, "tasklets": t, "rank_count": 1,
            "schedule": schedule, "fuse": fuse, "policy": policy,
            "geometry": "panel_only_v1", "transport": "packed_wave_v1", "threads": 1}


def core_identity(s, phase, cid, a, path_role):
    return {"implementation_commit": s["implementation_commit"], "phase": phase,
            "case_id": cid, "arm": a, "path_role": path_role,
            "timer_contract": "unified_final_v4_timing_v1"}


def cell_id(identity):
    return "cell-" + sha(identity)


def slots(s, phase, cs):
    records = []
    for c in cs:
        for b in c["blocks"]:
            key = {"protocol_sha256": sha(s), "phase": phase, "cell_id": c["cell_id"], "block": b}
            records.append({**key, "slot_id": "slot-" + sha(key), "case_id": c["case_id"],
                            "warmup": b == 0, "backend": c["arm"]["backend"]})
    # Complete randomized blocks: result-independent order fixed by content hash.
    return sorted(records, key=lambda r: (r["block"], sha({"seed": s["seed"], "slot_id": r["slot_id"]})))


def compile_manifest(s):
    validate_spec(s)
    all_cases = cases(s)
    by_id = {c["case_id"]: c for c in all_cases}
    resource_cases = [case(f, 18)["case_id"] for f in FAMILIES] + [s["supplementary_resource_case"]]
    q_cases = list(dict.fromkeys(resource_cases + s["supplementary_quantization_cases"]))
    unique, views = {}, []

    def add(view, cid, a, label):
        identity = core_identity(s, "calibration", cid, a, "greedy")
        identifier = cell_id(identity)
        c = unique.setdefault(identifier, {**identity, "cell_id": identifier, "blocks": set()})
        c["blocks"].update(s["warmup_blocks"] + s["measured_blocks"][view])
        views.append({"view": view, "case_id": cid, "cohort": by_id[cid]["cohort"],
                      "point": label, "cell_id": identifier, "measured_blocks": s["measured_blocks"][view]})

    for cid in resource_cases:
        for t in s["tasklets"]:
            add("T", cid, arm(1,t,"serial_nodes_v1",False), f"T{t}")
        for t in s["topology_tasklets"]:
            for d in s["dpus"]:
                add("D", cid, arm(d,t), f"D{d}/T{t}")
        ladder = [arm(1,1,"serial_nodes_v1",False), arm(1,8,"serial_nodes_v1",False),
                  arm(4,8,"serial_nodes_v1",False), arm(4,8,"serial_nodes_v1",True), arm(4,8)]
        for i, a in enumerate(ladder):
            add("A", cid, a, f"A{i}")
    for cid in q_cases:
        for p in (FP,I8):
            for t in s["topology_tasklets"]:
                for d in s["dpus"]:
                    add("Q", cid, arm(d,t,policy=p), f"D{d}/T{t}/{p}")

    cs = sorted(({**c, "blocks": sorted(c["blocks"])} for c in unique.values()), key=lambda c: c["cell_id"])
    cal_slots = slots(s, "calibration", cs)
    templates = []
    for c in all_cases:
        if c["family"] == "ghz":
            continue
        for role in s["final_arms"]:
            templates.append({"case_id": c["case_id"], "family": c["family"], "cohort": c["cohort"],
                              "role": role, "view": "W" if c["cohort"] == "primary" else "S",
                              "blocks": [0,1,2,3,4,5],
                              "selection_family": c["family"],
                              "binding": "after_selection_and_R_seal"})
    configurations = {sha(c["arm"]): c["arm"] for c in cs}
    qualification = [{"configuration_id": k, "arm": a, "fixture_id": fixture}
                     for k,a in sorted(configurations.items()) for fixture in s["qualification_fixtures"]]
    vcount = dict(Counter(v["view"] for v in views))
    naive_cal = sum(1+len(s["measured_blocks"][v["view"]]) for v in views)
    final_slots = len(templates)*6
    final_up = sum(t["role"].startswith("upmem_") for t in templates)*6
    observed_counts = {
        "distinct_performance_circuits":len(all_cases), "calibration_analysis_memberships":len(views),
        "calibration_unique_cells":len(cs), "calibration_slots":len(cal_slots),
        "calibration_warmups":len(cs), "calibration_measured":len(cal_slots)-len(cs),
        "duplicate_slots_avoided_within_calibration":naive_cal-len(cal_slots),
        "final_case_templates":len(templates)//5, "final_cell_templates":len(templates),
        "final_slots":final_slots, "final_warmups":len(templates),
        "final_measured":final_slots-len(templates), "final_physical_slots":final_up,
        "final_cpu_slots":final_slots-final_up, "benchmark_slots":len(cal_slots)+final_slots,
        "benchmark_warmups":len(cs)+len(templates),
        "benchmark_measured":len(cal_slots)+final_slots-len(cs)-len(templates),
        "benchmark_physical_slots":len(cal_slots)+final_up,
        "upmem_execution_configurations":len(configurations),
        "physical_qualification_attempts":len(qualification), "simulator_qualification_attempts":len(qualification),
        "quest_qualification_calls":len(s["quest_semantic_fixtures"])*4,
        "physical_attempt_ceiling_including_qualification":len(cal_slots)+final_up+len(qualification),
        "final_searches":len(templates)//5, "final_search_proposals":(len(templates)//5)*128,
        "small_R_qualification_searches":4, "total_search_proposal_ceiling":(len(templates)//5+4)*128}
    require(observed_counts == s["expected"], f"count contract mismatch: {observed_counts}")
    return sealed({"schema":"unified_v4_manifest_v1", "protocol_sha256":sha(s), "cases":all_cases,
                   "calibration_cells":cs, "calibration_views":views, "calibration_slots":cal_slots,
                   "final_templates":templates, "qualification":qualification,
                   "view_membership_counts":vcount, "counts":observed_counts})


def validate_calibration_rows(s, manifest, rows):
    check_seal(manifest)
    require(manifest["protocol_sha256"] == sha(s), "manifest/spec mismatch")
    wanted = {r["slot_id"]:r for r in manifest["calibration_slots"]}
    cells = {c["cell_id"]:c for c in manifest["calibration_cells"]}
    found = {}
    run_ids, evaluator_ids = set(), set()
    execution_bindings = {}
    for r in rows:
        identifier = r.get("slot_id")
        require(identifier in wanted and identifier not in found, "unexpected or duplicate slot")
        e = wanted[identifier]
        for key in ("phase", "case_id", "cell_id", "block", "warmup", "protocol_sha256", "backend"):
            require(type(r.get(key)) is type(e[key]) and r[key] == e[key], f"receipt identity mismatch: {key}")
        require(isinstance(r.get("run_id"), str) and r["run_id"], "run identity required")
        run_ids.add(r["run_id"])
        require(r.get("implementation_commit") == s["implementation_commit"], "wrong measured source")
        evaluator = r.get("evaluation_commit")
        require(isinstance(evaluator,str) and len(evaluator)==40 and all(x in "0123456789abcdef" for x in evaluator), "invalid evaluator source")
        evaluator_ids.add(evaluator)
        binding = r.get("execution_binding_sha256")
        require(isinstance(binding,str) and len(binding)==64 and all(x in "0123456789abcdef" for x in binding), "execution binding required")
        old_binding = execution_bindings.setdefault(r["cell_id"],binding)
        require(old_binding == binding, "cell execution binding changed across blocks")
        require(type(r.get("issued")) is bool, "issued flag required")
        status = r.get("status")
        require(status in ("success", "unsupported", "not_issued_unsupported"), "unresolved failure stops selection")
        if status == "success":
            require(r["issued"] and r.get("same_policy_passed") is True and r.get("finite") is True,
                    "execution correctness not verified")
            positive(r.get("prepared_call_s"), "missing/nonpositive prepared-call time")
            if cells[r["cell_id"]]["arm"]["policy"] == FP:
                require(r.get("accuracy_qualified") is True, "float32 accuracy failure")
            require(type(r.get("accuracy_qualified")) is bool, "accuracy flag required")
        else:
            require(isinstance(r.get("reason"), str) and r["reason"], "unsupported reason required")
            require(r.get("prepared_call_s") is None, "unsupported slot must not contain a time")
            require(r["issued"] == (status == "unsupported"), "unsupported issued state mismatch")
        found[identifier] = r
    require(set(found) == set(wanted), "incomplete calibration slot ledger")
    require(len(run_ids)==1 and len(evaluator_ids)==1, "mixed campaign or evaluator receipts")
    return found


def select_topologies(s, manifest, rows):
    indexed = validate_calibration_rows(s, manifest, rows)
    per_cell = defaultdict(dict)
    for r in indexed.values():
        per_cell[r["cell_id"]][r["block"]] = r
    targets = [(f, case(f,18)["case_id"]) for f in FAMILIES] + [("stress", "stress_n16_l2")]
    choices = []
    for family,cid in targets:
        for policy in (FP,I8):
            candidates = [c for c in manifest["calibration_cells"] if c["case_id"] == cid
                          and c["arm"]["schedule"] == "static_dag_waves_v1"
                          and c["arm"]["fuse"] and c["arm"]["policy"] == policy
                          and c["arm"]["tasklets"] in (8,24)]
            require(len(candidates) == 14, "selection grid must have 14 candidates")
            table = []
            for c in candidates:
                rr = [per_cell[c["cell_id"]][b] for b in s["topology_selection"]["blocks"]]
                valid = all(r["status"] == "success" for r in rr)
                table.append({"cell_id":c["cell_id"], "dpus":c["arm"]["dpus"],
                              "tasklets":c["arm"]["tasklets"], "eligible":valid,
                              "median_prepared_call_s":median([r["prepared_call_s"] for r in rr]) if valid else None,
                              "all_accuracy_qualified":all(r.get("accuracy_qualified") is True for r in rr),
                              "source_slots":[r["slot_id"] for r in rr]})
            valid = [t for t in table if t["eligible"]]
            require(valid, f"no complete candidate: {family}/{policy}")
            best = min(valid, key=lambda t:(t["median_prepared_call_s"],t["dpus"],t["tasklets"],t["cell_id"]))
            choices.append({"family":family, "policy":policy, "calibration_case_id":cid,
                            "selected":best, "candidates":sorted(table,key=lambda t:(t["dpus"],t["tasklets"]))})
    return sealed({"schema":"unified_v4_selection_v1", "protocol_sha256":sha(s),
                   "manifest_sha256":manifest["content_sha256"],
                   "calibration_rows_sha256":sha(sorted(rows,key=lambda r:r["slot_id"])),
                   "run_id":rows[0]["run_id"], "evaluation_commit":rows[0]["evaluation_commit"],
                   "rule":"greedy calibration, blocks 1..5, min median then D then T; no quality tuning for int8",
                   "selections":choices})


def pairwise_path(path, tensor_count):
    require(type(tensor_count) is int and tensor_count >= 2, "invalid tensor count")
    require(isinstance(path,list) and len(path) == tensor_count-1, "incomplete pairwise path")
    active = tensor_count
    for pair in path:
        require(isinstance(pair,list) and len(pair) == 2 and all(type(v) is int for v in pair), "invalid pair")
        require(pair[0] != pair[1] and all(0 <= v < active for v in pair), "pair references invalid live tensors")
        active -= 1
    return path


def choose_R(candidates):
    """Only validated, complete, f32-admitted G + F-trace candidates may enter here."""
    seen = {}
    for c in candidates:
        require(c.get("origin") in ("G", "F_trace"), "unexpected search population")
        if c.get("eligible") is not True:
            continue
        require(isinstance(c.get("path_id"),str) and c["path_id"], "missing path identity")
        score = c.get("score")
        require(type(score) in (int,float) and math.isfinite(score) and score >= 0, "invalid score")
        pairwise_path(c["path"], c["tensor_count"])
        old = seen.get(c["path_id"])
        if old is not None:
            require(old["path"] == c["path"] and old["score"] == score, "inconsistent duplicate path")
        else:
            seen[c["path_id"]] = c
    return min(seen.values(), key=lambda c:(c["score"],c["path_id"]), default=None)


def materialize_final(s, manifest, selection, path_records):
    check_seal(manifest); check_seal(selection)
    require(selection["protocol_sha256"] == sha(s) and selection["manifest_sha256"] == manifest["content_sha256"],
            "selection source mismatch")
    route = {(r["family"],r["policy"]):r["selected"] for r in selection["selections"]}
    expected_cases = {t["case_id"] for t in manifest["final_templates"]}
    require(len(path_records) == len(expected_cases), "missing/duplicate final path records")
    paths = {r["case_id"]:r for r in path_records}
    require(set(paths) == expected_cases, "wrong final path case set")
    for r in path_records:
        check_seal(r)
        require(r.get("selection_sha256") == selection["content_sha256"], "path predates/does not match selection")
        require(r.get("status") in ("selected","no_selected_R_path","planning_limit"), "invalid final path status")
        if r["status"] == "selected":
            pairwise_path(r["path"],r["tensor_count"])
            require(r.get("path_sha256") == sha(r["path"]), "path bytes changed")
            require(isinstance(r.get("path_id"),str) and r["path_id"], "missing source path id")
    out = []
    for t in manifest["final_templates"]:
        role, family, cid = t["role"],t["family"],t["case_id"]
        p = paths[cid]
        selected = p["status"] == "selected"
        if role.startswith("upmem_"):
            policy = FP if role == "upmem_f32" else I8
            winner = route[(family,policy)]
            a = arm(winner["dpus"],winner["tasklets"],policy=policy)
        else:
            a = {"backend":"numpy" if role == "numpy_f32_p1" else "quest32",
                 "threads":8 if role == "quest32_p8" else 1, "policy":FP}
        use_path = a["backend"] != "quest32"
        identity = core_identity(s,"final",cid,a,"R_f32_shared" if use_path else "direct_statevector")
        identity.update(selection_sha256=selection["content_sha256"],
                        selected_path_id=p["path_id"] if use_path and selected else None,
                        selected_path_sha256=p["path_sha256"] if use_path and selected else None)
        out.append({**identity,"cell_id":cell_id(identity),"role":role,"view":t["view"],
                    "blocks":t["blocks"],"eligible_for_runtime_admission":selected or not use_path,
                    "not_runnable_reason":None if selected or not use_path else p["status"]})
    require(len({c["cell_id"] for c in out}) == len(out), "duplicate final cell")
    return sealed({"schema":"unified_v4_final_manifest_v1","protocol_sha256":sha(s),
                   "run_id":selection["run_id"], "evaluation_commit":selection["evaluation_commit"],
                   "selection_sha256":selection["content_sha256"], "path_records_sha256":sha(sorted(path_records,key=lambda r:r["case_id"])),
                   "cells":out,"slots":slots(s,"final",out)})


def write_new_json(path, value):
    with Path(path).open("xb") as f:
        f.write(canonical(value)+b"\n")


def csv_bytes(rows):
    fields = list(rows[0]) if rows else []
    output = io.StringIO(newline="")
    w = csv.DictWriter(output,fieldnames=fields,lineterminator="\n"); w.writeheader()
    for r in rows:
        w.writerow({k: canonical(v).decode() if isinstance(v,(dict,list)) else v for k,v in r.items()})
    return output.getvalue().encode()


def write_manifest(out, manifest):
    out = Path(out); require(not out.exists(), "output exists; do not overwrite")
    out.mkdir(parents=True)
    write_new_json(out/"manifest.json",manifest)
    write_new_json(out/"counts.json",manifest["counts"])
    for key in ("cases","calibration_cells","calibration_views","calibration_slots","final_templates","qualification"):
        (out/(key+".csv")).write_bytes(csv_bytes(manifest[key]))
    entries = sorted(p for p in out.iterdir() if p.is_file())
    (out/"SHA256SUMS").write_text("".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in entries),encoding="ascii")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--spec",type=Path,default=HERE/"protocol.json")
    sub = ap.add_subparsers(dest="command",required=True)
    p=sub.add_parser("compile"); p.add_argument("--out",type=Path,required=True)
    p=sub.add_parser("select"); p.add_argument("--manifest",type=Path,required=True); p.add_argument("--rows",type=Path,required=True); p.add_argument("--out",type=Path,required=True)
    p=sub.add_parser("bind-final"); p.add_argument("--manifest",type=Path,required=True); p.add_argument("--selection",type=Path,required=True); p.add_argument("--paths",type=Path,required=True); p.add_argument("--out",type=Path,required=True)
    args=ap.parse_args(); s=read(args.spec)
    if args.command=="compile":
        m=compile_manifest(s); write_manifest(args.out,m); print(json.dumps(m["counts"],indent=2))
    elif args.command=="select":
        write_new_json(args.out,select_topologies(s,read(args.manifest),read(args.rows)))
    else:
        write_new_json(args.out,materialize_final(s,read(args.manifest),read(args.selection),read(args.paths)))


if __name__ == "__main__":
    main()
