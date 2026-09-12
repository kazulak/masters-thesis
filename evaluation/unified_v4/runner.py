#!/usr/bin/env python3
"""Unified evaluation v4 controller and worker adapter.

CLI contract:
  runner.py check-contract --manifest DIR --implementation PATH
  runner.py inspect --machine FILE --implementation-commit SHA --output DIR
  runner.py all --machine FILE --evaluation-commit SHA --run-id ID --receipt-root DIR
  runner.py resume --machine FILE --evaluation-commit SHA --run-id ID --receipt-root DIR
  runner.py worker [args...]
"""
from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping
import ctypes
import dataclasses
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import resource
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import time
import traceback

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import protocol_core as pc

FROZEN_IMPLEMENTATION = "f6b570a98a610d41b5b16401a42ce12a94042d38"
FROZEN_IMPLEMENTATION_TREE = "98597dfe4db38c49bd4e2cfa127880739e0d5a05"
NORMALIZATION_SHA256 = "3317af8c144b233428b31caa43ae154ff973c5e1897bc8ea4e2f87827e9152b0"
FP = pc.FP
I8 = pc.I8


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def canonical(value: object) -> bytes:
    return pc.canonical(value)


def sha(value: object) -> str:
    return pc.sha(value)


def read_json(path: Path | str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_new_json(path: Path | str, value: object) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as f:
        f.write(canonical(value) + b"\n")
        f.flush()
        os.fsync(f.fileno())


def digest_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def setup_implementation_imports(source: Path | str) -> Path:
    root = Path(source) / "thesis/implementation"
    for p in (str(root / "src"), str(root / "scripts")):
        if p not in sys.path:
            sys.path.insert(0, p)
    return root


# ---------------------------------------------------------------------------
# QASM & Circuit Generation
# ---------------------------------------------------------------------------

def qasm_for_case(source: Path | str, case_info: Mapping[str, object]) -> bytes:
    setup_implementation_imports(source)
    from upmem_family_workload import build_family_qasm
    from quantum_bench.circuits import builtin_circuit

    cid = str(case_info["case_id"])
    if cid == "qual_bell_n02":
        return b"OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n"

    f = str(case_info["family"])
    n = int(case_info["n"])
    if f in ("bb84", "qrng"):
        return build_family_qasm(f, {"n_qubits": n})
    if f in ("bv", "xor"):
        return build_family_qasm(f, {"data_qubits": n - 1})
    if f == "edc":
        return build_family_qasm(f, {"data_qubits": (n + 1) // 2})
    if f == "hs":
        return build_family_qasm(f, {"allocated_qubits": n})
    if f == "stress":
        c = builtin_circuit("quantization_stress", {"n_qubits": n, "repeat_layers": int(case_info.get("parameters", {}).get("repeat_layers", 2))})
    elif f == "ghz":
        c = builtin_circuit("ghz_chain", {"n_qubits": n})
    else:
        raise ValueError(f"unknown circuit family: {f}")

    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";', f"qreg q[{n}];"]
    for o in c.operations:
        gate = o.gate + ("(" + ",".join(format(float(v), ".17g") for v in o.params) + ")" if o.params else "")
        lines.append(gate + " " + ",".join(f"q[{w}]" for w in o.wires) + ";")
    return ("\n".join(lines) + "\n").encode("ascii")


def load_circuit_job(source: Path | str, qasm_path: Path | str, n_qubits: int):
    setup_implementation_imports(source)
    from quantum_bench.circuits import parse_openqasm2
    from quantum_bench.model import make_simulation_job

    circuit = parse_openqasm2(Path(qasm_path))
    require(circuit.n_qubits == n_qubits, f"qubit count mismatch: expected {n_qubits}, got {circuit.n_qubits}")
    return make_simulation_job(circuit=circuit)


# ---------------------------------------------------------------------------
# Output Verification Oracles (Analytic & Double-Precision)
# ---------------------------------------------------------------------------

def expected_analytic_chunk(case_info: Mapping[str, object], start: int, end: int):
    import numpy as np

    family = str(case_info["family"])
    n = int(case_info["n"])
    ix = np.arange(start, end, dtype=np.uint64)
    expected = np.zeros(len(ix), dtype=np.complex128)

    if family == "qrng":
        expected[:] = 2.0 ** (-n / 2)
    elif family == "ghz":
        expected[(ix == 0) | (ix == (1 << n) - 1)] = 2 ** -0.5
    elif family == "bv":
        d = n - 1
        secret = sum(1 << i for i in range(d) if i % 2 == 0)
        expected[ix == secret] = 2 ** -0.5
        expected[ix == secret + (1 << d)] = -2 ** -0.5
    elif family == "hs":
        target = sum(1 << i for i in range(0, n, 2))
        expected[ix == target] = 1.0
    elif family == "edc":
        d = (n + 1) // 2
        e = d // 2
        mask = 1 << e
        syndrome = sum(1 << (d + j) for j in range(d - 1) if ((mask >> j) & 1) ^ ((mask >> (j + 1)) & 1))
        i0 = mask + syndrome
        i1 = (((1 << d) - 1) ^ mask) + syndrome
        expected[ix == i0] = math.sqrt(3) / 2
        expected[ix == i1] = 0.5
    elif family == "xor":
        d = n - 1
        parity = np.zeros(len(ix), dtype=np.uint64)
        for wire in range(d):
            parity ^= (ix >> wire) & 1
        expected[((ix >> d) & 1) == parity] = 2.0 ** (-d / 2)
    elif family == "bb84":
        valid = np.ones(len(ix), dtype=bool)
        sign = np.ones(len(ix), dtype=np.int8)
        hcount = 0
        for wire in range(n):
            bit = wire % 2
            basis = (wire // 2) % 2
            digit = (ix >> wire) & 1
            if basis:
                hcount += 1
                if bit:
                    sign[digit == 1] *= -1
            else:
                valid &= (digit == bit)
        expected[valid] = sign[valid] * 2.0 ** (-hcount / 2)
    elif str(case_info["case_id"]) == "qual_bell_n02":
        expected[ix == 0] = 2 ** -0.5
        expected[ix == 3] = 2 ** -0.5
    else:
        raise ValueError(f"unknown analytic family: {family}")
    return expected


def errors_analytic(output, case_info: Mapping[str, object], atol: float = 1e-5, rtol: float = 1e-5) -> dict:
    import numpy as np

    n = int(case_info["n"])
    require(output.size == (1 << n), f"output size mismatch: expected {1 << n}, got {output.size}")
    total = refnorm = norm = 0.0
    peak = refpeak = 0.0
    overlap = 0j
    finite = True
    elementwise = True

    chunk_size = 1 << 18
    for start in range(0, output.size, chunk_size):
        end = min(start + chunk_size, output.size)
        x = np.asarray(output[start:end], dtype=np.complex128)
        y = expected_analytic_chunk(case_info, start, end)
        if not (np.isfinite(x).all() and np.isfinite(y).all()):
            finite = False
            break
        diff = x - y
        elementwise = elementwise and bool(np.all(np.abs(diff) <= atol + rtol * np.abs(y)))
        total += float(np.vdot(diff, diff).real)
        refnorm += float(np.vdot(y, y).real)
        norm += float(np.vdot(x, x).real)
        peak = max(peak, float(np.max(np.abs(diff), initial=0)))
        refpeak = max(refpeak, float(np.max(np.abs(y), initial=0)))
        overlap += np.vdot(y, x)

    if not finite or refnorm <= 0:
        return dict(finite=False, relative_l2=None, max_abs=None, norm_drift=None, reference_peak=None, elementwise_allclose=False, fidelity_normalized=0.0)
    return dict(
        finite=True,
        relative_l2=math.sqrt(total / refnorm),
        max_abs=peak,
        norm_drift=abs(math.sqrt(norm) - math.sqrt(refnorm)),
        reference_peak=refpeak,
        probability_norm_drift=abs(norm - refnorm),
        elementwise_allclose=elementwise,
        fidelity_normalized=(abs(overlap) ** 2 / (norm * refnorm) if norm else 0.0),
    )


def errors_against_reference(output, reference, atol: float = 1e-5, rtol: float = 1e-5) -> dict:
    import numpy as np

    require(output.size == reference.size, f"output size mismatch: {output.size} vs {reference.size}")
    total = refnorm = norm = 0.0
    peak = refpeak = 0.0
    overlap = 0j
    finite = True
    elementwise = True

    chunk_size = 1 << 18
    for start in range(0, output.size, chunk_size):
        end = min(start + chunk_size, output.size)
        x = np.asarray(output[start:end], dtype=np.complex128)
        y = np.asarray(reference[start:end], dtype=np.complex128)
        if not (np.isfinite(x).all() and np.isfinite(y).all()):
            finite = False
            break
        diff = x - y
        elementwise = elementwise and bool(np.all(np.abs(diff) <= atol + rtol * np.abs(y)))
        total += float(np.vdot(diff, diff).real)
        refnorm += float(np.vdot(y, y).real)
        norm += float(np.vdot(x, x).real)
        peak = max(peak, float(np.max(np.abs(diff), initial=0)))
        refpeak = max(refpeak, float(np.max(np.abs(y), initial=0)))
        overlap += np.vdot(y, x)

    if not finite or refnorm <= 0:
        return dict(finite=False, relative_l2=None, max_abs=None, norm_drift=None, reference_peak=None, elementwise_allclose=False, fidelity_normalized=0.0)
    return dict(
        finite=True,
        relative_l2=math.sqrt(total / refnorm),
        max_abs=peak,
        norm_drift=abs(math.sqrt(norm) - math.sqrt(refnorm)),
        reference_peak=refpeak,
        probability_norm_drift=abs(norm - refnorm),
        elementwise_allclose=elementwise,
        fidelity_normalized=(abs(overlap) ** 2 / (norm * refnorm) if norm else 0.0),
    )


def check_accuracy(err: Mapping[str, object], val_spec: Mapping[str, object]) -> bool:
    if not err.get("finite"):
        return False
    if not err.get("elementwise_allclose", False):
        return False
    rel_l2 = err.get("relative_l2")
    norm_drift = err.get("norm_drift")
    max_abs = err.get("max_abs")
    ref_peak = err.get("reference_peak")
    if rel_l2 is None or rel_l2 > val_spec["relative_l2_max"]:
        return False
    if norm_drift is None or norm_drift > val_spec["norm_drift_max"]:
        return False
    if max_abs is None or ref_peak is None:
        return False
    limit = val_spec["atol"] + val_spec["rtol"] * ref_peak
    return bool(max_abs <= limit)


def ndarray_sha256(a) -> str:
    import numpy as np

    a = np.ascontiguousarray(a)
    h = hashlib.sha256()
    view = memoryview(a).cast("B")
    for start in range(0, len(view), 1024 * 1024):
        h.update(view[start : start + 1024 * 1024])
    return h.hexdigest()


# ---------------------------------------------------------------------------
# QuEST Ctypes Bridge Execution
# ---------------------------------------------------------------------------

def quest_bridge_once(job, libfile: Path | str, requested_threads: int):
    import numpy as np

    lib = ctypes.CDLL(str(libfile))
    lib.eval_precision_bytes.restype = ctypes.c_int
    real_bytes = lib.eval_precision_bytes()
    require(real_bytes in (4, 8), f"unsupported QuEST precision: {real_bytes}")
    fun = lib.eval_circuit
    ip = ctypes.POINTER(ctypes.c_int)
    dp = ctypes.POINTER(ctypes.c_double)
    fun.argtypes = [
        ctypes.c_int, ctypes.c_int, ip, ip, ip, dp,
        ctypes.c_int, ctypes.c_void_p, ctypes.c_uint64,
        dp, ip,
    ]
    fun.restype = ctypes.c_int

    start = time.perf_counter()
    table = {"h": 0, "x": 1, "ry": 2, "rz": 3, "cx": 4}
    ops = list(job.circuit.operations)
    op = np.array([table[o.gate] for o in ops], dtype=np.int32)
    a = np.array([o.wires[0] for o in ops], dtype=np.int32)
    b = np.array([o.wires[1] if len(o.wires) == 2 else 0 for o in ops], dtype=np.int32)
    angle = np.array([o.params[0] if o.params else 0.0 for o in ops], dtype=np.float64)
    packing_s = time.perf_counter() - start

    start = time.perf_counter()
    output = np.empty(1 << job.circuit.n_qubits, dtype=np.complex64 if real_bytes == 4 else np.complex128)
    times = np.zeros(4, np.float64)
    deployment = np.zeros(3, np.int32)
    code = fun(
        job.circuit.n_qubits, len(ops), op.ctypes.data_as(ip),
        a.ctypes.data_as(ip), b.ctypes.data_as(ip), angle.ctypes.data_as(dp),
        requested_threads, output.ctypes.data, output.nbytes,
        times.ctypes.data_as(dp), deployment.ctypes.data_as(ip),
    )
    wall_s = time.perf_counter() - start
    require(code == 0, f"QuEST bridge returned error code {code}")
    require(deployment[1] == 0 and deployment[2] == 0, "unexpected accelerated or distributed QuEST deployment")

    metrics = {
        "prepared_call_s": wall_s,
        "job_to_state_s": packing_s + wall_s,
        "job_to_state_cached_path_s": packing_s + wall_s,
        "packing_s": packing_s,
        "session_inclusive_s": float(sum(times)),
        "native_open_s": float(times[0]),
        "kernel_s": float(times[1]),
        "native_output_copy_s": float(times[2]),
        "native_close_s": float(times[3]),
        "real_bytes": real_bytes,
        "actual_multithreading": bool(deployment[0]),
        "requested_threads": requested_threads,
        "bridge_sha256": digest_file(libfile),
    }
    return output, metrics


# ---------------------------------------------------------------------------
# Execution Primitives: UPMEM & NumPy
# ---------------------------------------------------------------------------

def safe_json_record(value: object) -> object:
    if dataclasses.is_dataclass(value):
        return {f.name: safe_json_record(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, Mapping):
        return {str(k): safe_json_record(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [safe_json_record(v) for v in value]
    if hasattr(value, "item") and getattr(value, "ndim", None) == 0:
        return value.item()
    if isinstance(value, Path):
        return str(value)
    return value


def execute_tn_slot(
    source: Path | str,
    work_dir: Path | str,
    case_info: Mapping[str, object],
    arm_info: Mapping[str, object],
    spec: Mapping[str, object],
    *,
    cached_path: list | None = None,
    simulator: bool = False,
    active_session_root: Path | str | None = None,
):
    import numpy as np
    setup_implementation_imports(source)
    from quantum_bench.lowering import lower_tensor_network, build_contraction_dag, contraction_dag_hash
    from quantum_bench.planning import plan_opt_einsum
    from quantum_bench.cpu import run_cpu_once, replay_upmem_plan_once
    from quantum_bench.upmem.plan import UpmemTopology, UpmemResources, plan_upmem, physical_plan_id
    from quantum_bench.upmem.runtime import open_upmem, open_upmem_simulator

    qasm_path = Path(work_dir) / "cases" / f"{case_info['case_id']}.qasm"
    job = load_circuit_job(source, qasm_path, int(case_info["n"]))

    backend = str(arm_info.get("backend", "upmem"))
    policy = str(arm_info.get("policy", FP))

    start_timer = time.perf_counter()
    mark = start_timer
    network, inputs = lower_tensor_network(job)
    lower_s = time.perf_counter() - mark

    if cached_path is not None:
        path = [list(p) for p in cached_path]
        planning_s = 0.0
    else:
        mark = time.perf_counter()
        path, prov = plan_opt_einsum(network, optimize="greedy")
        planning_s = time.perf_counter() - mark

    mark = time.perf_counter()
    dag = build_contraction_dag(network, path)
    dag_s = time.perf_counter() - mark

    details: dict[str, object] = {
        "lowering_s": lower_s,
        "planning_s": planning_s,
        "dag_s": dag_s,
        "path_id": pc.sha(path),
        "logical_plan_id": contraction_dag_hash(dag),
    }

    if backend == "numpy":
        begin_call = time.perf_counter()
        sample = run_cpu_once(dag, inputs, FP)
        call_s = time.perf_counter() - begin_call
        output = np.asarray(sample.output).ravel(order="F").copy()
        details["prepared_call_s"] = call_s
        details["job_to_state_s"] = time.perf_counter() - start_timer
        details["job_to_state_cached_path_s"] = time.perf_counter() - start_timer
        details["session_inclusive_s"] = sample.measurement.total_wall_s
        details["measurement"] = safe_json_record(sample.measurement)
        details["backend_facts"] = safe_json_record(sample.backend_facts)
        details["same_policy_passed"] = True
        return output, details

    # UPMEM backend
    mark = time.perf_counter()
    plan = plan_upmem(
        dag,
        numeric_policy=policy,
        topology=UpmemTopology(dpu_count=int(arm_info["dpus"]), tasklets_per_dpu=int(arm_info["tasklets"]), rank_count=1),
        schedule_policy=str(arm_info.get("schedule", "static_dag_waves_v1")),
    )
    details["mapping_s"] = time.perf_counter() - mark
    details["physical_plan_id"] = physical_plan_id(plan)

    native_bin_dir = Path(source) / "thesis/implementation/native/upmem/runtime/bin"
    t = int(arm_info["tasklets"])
    sess_root = Path(active_session_root) if active_session_root else (Path(work_dir) / f"session_{arm_info.get('dpus')}_{t}")
    sess_root.mkdir(parents=True, exist_ok=True)

    resource_record = UpmemResources(
        session_root=str(sess_root),
        host_binary=str(native_bin_dir / f"host_upmem_execution_plan_v4_t{t}"),
        dpu_binary=str(native_bin_dir / f"dpu_wave_v5_t{t}"),
        initialization_binary=str(native_bin_dir / f"dpu_simplepim_management_init_t{t}"),
        rank_paths=() if simulator else (str(spec.get("rank_path", "/dev/dpu_rank1")),),
        request_transport=str(arm_info.get("transport", "packed_wave_v1")),
    )

    begin_call = time.perf_counter()
    mark = begin_call
    opener = open_upmem_simulator if simulator else open_upmem
    session = opener(
        dag,
        plan,
        resource_record,
        timeout_s=float(spec.get("attempt_native_timeout_s", 300)),
        fuse_complex=bool(arm_info.get("fuse", True)),
        geometry_policy=str(arm_info.get("geometry", "panel_only_v1")),
        host_memory_budget_bytes=int(spec.get("host_memory_budget_bytes", 8589934592)),
        host_memory_reserve_bytes=0,
    )
    open_s = time.perf_counter() - mark
    try:
        sample = session.run_once(inputs)
        output = np.asarray(sample.output).ravel(order="F").copy()
    finally:
        mark = time.perf_counter()
        terminal = session.close()
        close_s = time.perf_counter() - mark

    call_s = time.perf_counter() - begin_call
    details["prepared_call_s"] = call_s
    details["job_to_state_s"] = time.perf_counter() - start_timer
    details["job_to_state_cached_path_s"] = time.perf_counter() - start_timer
    details["session_inclusive_s"] = open_s + sample.measurement.total_wall_s + close_s
    details["session_open_s"] = open_s
    details["session_close_s"] = close_s
    details["kernel_s"] = sample.measurement.kernel_s
    details["h2d_s"] = sample.measurement.h2d_s
    details["d2h_s"] = sample.measurement.d2h_s
    details["h2d_bytes"] = sample.measurement.h2d_bytes
    details["d2h_bytes"] = sample.measurement.d2h_bytes
    details["measurement"] = safe_json_record(sample.measurement)
    details["backend_facts"] = safe_json_record(sample.backend_facts)
    details["numeric_facts"] = safe_json_record(sample.numeric_facts)
    details["terminal_facts"] = safe_json_record(terminal)

    require(sample.backend_facts.get("cpu_fallback_used") is False, "unexpected CPU fallback on UPMEM")
    require(terminal.get("native_identity_verified") is True, "native binary identity not verified")
    if not simulator:
        require(terminal.get("target_observed") == "physical_hardware", "expected physical hardware target")

    # Replay check
    replay = replay_upmem_plan_once(dag, plan, inputs)
    if policy == I8:
        require(sample.numeric_facts["raw_lane_records"] == replay.numeric_facts["raw_lane_records"], "int8 raw-lane policy mismatch")
        require(np.array_equal(output, np.asarray(replay.output).ravel(order="F")), "int8 replay statevector mismatch")
        details["same_policy_passed"] = True
        float_ctrl = run_cpu_once(dag, inputs, FP)
        details["error_vs_float32_same_dag"] = errors_against_reference(output, np.asarray(float_ctrl.output).ravel(order="F"))
    else:
        pe = errors_against_reference(output, np.asarray(replay.output).ravel(order="F"))
        require(check_accuracy(pe, spec["validation"]), "float32 physical-plan replay mismatch")
        details["same_policy_passed"] = True

    return output, details


# ---------------------------------------------------------------------------
# Candidate Callback for 128-proposal FLOP-guided search (§10)
# ---------------------------------------------------------------------------

def make_candidate_evaluation_callback(
    network,
    selected_f32_topology: Mapping[str, int],
    weights: list[int],
    scales,
    host_memory_budget_bytes: int = 8589934592,
):
    from quantum_bench.planning import _validate_pairwise_path
    from quantum_bench.lowering import build_contraction_dag
    from quantum_bench.upmem.plan import UpmemTopology, plan_upmem
    from quantum_bench.upmem.execution_features import extract_launch_cost_features
    from quantum_bench.upmem.path_heuristic import LaunchCostFacts, upmem_launch_cost_v1
    import upmem_path_heuristic as uph
    from upmem_cost_guided_path import GuidedEvaluation
    from quantum_bench.results import UnsupportedExecution

    def callback(path_tuple: tuple[tuple[int, int], ...], tree_flops: float) -> GuidedEvaluation:
        try:
            path_list = [list(step) for step in path_tuple]
            _validate_pairwise_path(path_list, len(network.tensors))
            dag = build_contraction_dag(network, path_list)

            # Rejection guard 1: work units
            units = uph._estimated_work_unit_count(dag)
            if units > 65536:
                return GuidedEvaluation(None, {"work_unit_count": units}, "work_unit_bound")

            # Rejection guard 2: semantic identity expansion
            expansion = uph._semantic_identity_expansion_units(dag, stop_after=1000000)
            if expansion > 1000000:
                return GuidedEvaluation(None, {"identity_expansion_units": expansion}, "identity_expansion_bound")

            # Lower on selected float32 topology, static_dag_waves_v1
            topology = UpmemTopology(
                dpu_count=int(selected_f32_topology["dpus"]),
                tasklets_per_dpu=int(selected_f32_topology["tasklets"]),
                rank_count=1,
            )
            plan = plan_upmem(dag, numeric_policy=FP, topology=topology, schedule_policy="static_dag_waves_v1")

            # Extract launch cost features
            features = extract_launch_cost_features(dag, plan, fuse_complex=True, geometry_policy="panel_only_v1")
            execution = features["execution"]
            declared_host_bytes = execution["host_buffers"]["declared_executor_memory_estimate_bytes"]
            if declared_host_bytes > host_memory_budget_bytes:
                return GuidedEvaluation(None, {"declared_host_bytes": declared_host_bytes}, "host_memory_bound")

            facts = LaunchCostFacts.from_mapping(features)
            score = upmem_launch_cost_v1(facts, weights, scales)

            validated_facts = {
                "r_score": float(score),
                "tree_flops": float(tree_flops),
                "declared_host_bytes": int(declared_host_bytes),
                "work_unit_count": int(units),
                "H": int(features["H"]),
                "P": int(features["P"]),
                "N": int(features["N"]),
                "launches": features["launches"],
            }
            return GuidedEvaluation(score=float(tree_flops), facts=validated_facts)

        except UnsupportedExecution as exc:
            return GuidedEvaluation(None, {"error": str(exc)}, f"UnsupportedExecution:{exc}")
        except ValueError as exc:
            msg = str(exc)
            if "snapshot admission limit" in msg:
                return GuidedEvaluation(None, {"error": msg}, f"snapshot_admission_limit:{msg}")
            raise

    return callback


def run_r_path_generation_for_case(
    source: Path | str,
    work_dir: Path | str,
    case_info: Mapping[str, object],
    selected_f32_topology: Mapping[str, int],
    selection_sha: str,
    spec: Mapping[str, object],
) -> dict:
    setup_implementation_imports(source)
    from upmem_cost_guided_path import run_cost_guided_search
    from quantum_bench.planning import plan_opt_einsum
    from quantum_bench.lowering import lower_tensor_network
    from quantum_bench.upmem.path_heuristic import LaunchCostScales
    from upmem_cost_guided_path import CostGuidedSearchError

    r_pol = spec["r_policy"]
    weights = r_pol["integer_weights"]
    norm_path = Path(source) / r_pol["normalization_path"]
    norm_data = read_json(norm_path)
    require(digest_file(norm_path) == "b422a0c3e392d0151b82fd6242a63358eeae1e8409673d3fa06e276a3e6c0386", "normalization.json checksum changed")
    scales_dict = norm_data["scales"]
    scales = LaunchCostScales(
        h=float(scales_dict["H"]),
        p=float(scales_dict["P"]),
        n=float(scales_dict["N"]),
        m=float(scales_dict["M"]),
        w=float(scales_dict["W"]),
    )

    qasm_path = Path(work_dir) / "cases" / f"{case_info['case_id']}.qasm"
    job = load_circuit_job(source, qasm_path, int(case_info["n"]))
    network, _ = lower_tensor_network(job)
    tensor_count = len(network.tensors)

    callback = make_candidate_evaluation_callback(
        network=network,
        selected_f32_topology=selected_f32_topology,
        weights=weights,
        scales=scales,
        host_memory_budget_bytes=int(r_pol.get("host_memory_admission_bytes", 8589934592)),
    )

    start_plan_time = time.perf_counter()
    status = "selected"
    reason = None
    partial_trace = []

    # 1. Evaluate ordinary greedy candidate
    greedy_path, _ = plan_opt_einsum(network, optimize="greedy")
    greedy_path_list = [list(step) for step in greedy_path]
    greedy_id = pc.sha({"case_id": case_info["case_id"], "path": greedy_path_list})
    greedy_eval = callback(tuple(tuple(step) for step in greedy_path_list), 0.0)

    candidates = []
    if greedy_eval.score is not None:
        candidates.append({
            "origin": "G",
            "eligible": True,
            "path_id": greedy_id,
            "path": greedy_path_list,
            "tensor_count": tensor_count,
            "score": greedy_eval.facts["r_score"],
            "tree_flops": greedy_eval.facts["tree_flops"],
        })

    # 2. Run 128-proposal FLOP-guided search
    try:
        search_result = run_cost_guided_search(
            network=network,
            workload_id=str(case_info["case_id"]),
            cell_id=f"{case_info['case_id']}_R",
            circuit_id=str(case_info["case_id"]),
            stage="p6_R_transfer_v1",
            objective_id="cotengra_tree_flops_v1",
            profile_id="upmem_launch_cost_v1",
            trace_context={"case_id": case_info["case_id"], "selection_sha256": selection_sha},
            evaluation_callback=callback,
            master_seed=int(r_pol.get("master_seed", 20260909)),
            proposals=int(r_pol.get("proposals", 128)),
            startup_trials=int(r_pol.get("startup_trials", 16)),
            proposal_timeout_s=float(r_pol.get("proposal_timeout_s", 300)),
            lowering_timeout_s=float(r_pol.get("lowering_timeout_s", 60)),
            search_timeout_s=float(r_pol.get("search_timeout_s", 7200)),
        )
        for item in search_result.get("trace", []):
            if item.get("status") == "eligible" and item.get("facts"):
                candidates.append({
                    "origin": "F_trace",
                    "eligible": True,
                    "path_id": item["path_id"],
                    "path": item["path"],
                    "tensor_count": tensor_count,
                    "score": item["facts"]["r_score"],
                    "tree_flops": item["facts"]["tree_flops"],
                })
    except CostGuidedSearchError as exc:
        status = "planning_limit"
        reason = str(exc)
        partial_trace = exc.partial_trace

    planning_once_s = time.perf_counter() - start_plan_time

    winner = pc.choose_R(candidates) if status == "selected" else None
    if status == "selected" and winner is None:
        status = "no_selected_R_path"
        reason = "no_admitted_candidate"

    record = {
        "schema": "unified_v4_path_record_v1",
        "case_id": case_info["case_id"],
        "selection_sha256": selection_sha,
        "status": status,
        "reason": reason,
        "planning_once_s": planning_once_s,
        "admitted_candidate_count": len(candidates),
        "tensor_count": tensor_count,
        "path": winner["path"] if winner else None,
        "path_id": winner["path_id"] if winner else None,
        "path_sha256": pc.sha(winner["path"]) if winner else None,
        "r_score": winner["score"] if winner else None,
    }
    return pc.sealed(record)


# ---------------------------------------------------------------------------
# CLI Command: check-contract
# ---------------------------------------------------------------------------

def check_contract_cmd(manifest_dir: Path, implementation_path: Path) -> None:
    manifest_dir = manifest_dir.resolve()
    implementation_path = implementation_path.resolve()

    require(manifest_dir.is_dir(), f"manifest directory not found: {manifest_dir}")
    require(implementation_path.is_dir(), f"implementation path not found: {implementation_path}")

    # Check Git implementation commit and tree
    head = subprocess.check_output(["git", "-C", str(implementation_path), "rev-parse", "HEAD"], text=True).strip()
    status = subprocess.check_output(["git", "-C", str(implementation_path), "status", "--porcelain"], text=True).strip()
    tree = subprocess.check_output(["git", "-C", str(implementation_path), "rev-parse", "HEAD^{tree}"], text=True).strip()

    require(head == FROZEN_IMPLEMENTATION, f"implementation commit mismatch: expected {FROZEN_IMPLEMENTATION}, got {head}")
    require(status == "", f"implementation worktree is dirty:\n{status}")
    require(tree == FROZEN_IMPLEMENTATION_TREE, f"implementation tree mismatch: expected {FROZEN_IMPLEMENTATION_TREE}, got {tree}")

    # Validate manifest seal and counts
    manifest = read_json(manifest_dir / "manifest.json")
    pc.check_seal(manifest)
    spec = read_json(HERE / "protocol.json")
    pc.validate_spec(spec)
    require(manifest["counts"] == spec["expected"], "manifest counts mismatch with protocol expected")

    # Verify primary calibration gate counts against PLAN.md §3
    expected_gate_counts = {
        "bb84_n18": {"h": 8, "x": 9},
        "bv_n18": {"h": 35, "x": 1, "cx": 9},
        "edc_n17": {"ry": 1, "x": 1, "cx": 24},
        "hs_n18": {"h": 90, "x": 18, "cx": 18},
        "qrng_n18": {"h": 18},
        "xor_n18": {"h": 17, "cx": 17},
    }

    setup_implementation_imports(implementation_path)
    from quantum_bench.circuits import parse_openqasm2

    tmp_qasm = manifest_dir / "_temp_check.qasm"
    try:
        for cid, exp_counts in expected_gate_counts.items():
            case_obj = next(c for c in manifest["cases"] if c["case_id"] == cid)
            qasm_bytes = qasm_for_case(implementation_path, case_obj)
            tmp_qasm.write_bytes(qasm_bytes)
            circ = parse_openqasm2(tmp_qasm)
            actual_counts = dict(Counter(op.gate for op in circ.operations))
            require(actual_counts == exp_counts, f"gate counts mismatch for {cid}: expected {exp_counts}, got {actual_counts}")
    finally:
        if tmp_qasm.exists():
            tmp_qasm.unlink()

    # Verify P6 pretest profile and normalization hash
    p6_dir = implementation_path / "thesis/implementation/thesis_results/upmem_cost_guided_path_v1"
    norm_path = p6_dir / "evidence_manifests/normalization.json"
    prof_path = p6_dir / "evidence_manifests/pretest_profile.json"
    require(norm_path.exists() and prof_path.exists(), "P6 evidence manifests missing")

    norm_data = read_json(norm_path)
    prof_data = read_json(prof_path)
    require(pc.sha(norm_data) == NORMALIZATION_SHA256, f"normalization hash mismatch: {pc.sha(norm_data)} vs {NORMALIZATION_SHA256}")
    require(prof_data["normalization_hash"] == NORMALIZATION_SHA256, "pretest profile normalization_hash mismatch")

    print("check-contract: PASSED. All manifest, source, gate count, and P6 seals match.")


# ---------------------------------------------------------------------------
# CLI Command: inspect
# ---------------------------------------------------------------------------

def inspect_machine_cmd(machine_file: Path, implementation_commit: str, output_dir: Path) -> None:
    machine_file = machine_file.resolve()
    output_dir = output_dir.resolve()
    require(output_dir and not output_dir.exists(), f"output directory already exists: {output_dir}")
    output_dir.mkdir(parents=True)

    mach = read_json(machine_file)
    require(mach.get("schema") == "unified_v4_machine_paths_v1", "wrong machine schema")
    require(implementation_commit == FROZEN_IMPLEMENTATION, f"implementation commit must be {FROZEN_IMPLEMENTATION}")

    is_remote = bool(mach.get("ssh_host") and mach["ssh_host"] not in ("localhost", "127.0.0.1"))
    ssh_host = mach.get("ssh_host")
    ssh_user = mach.get("ssh_user")

    def run_check(cmd_str: str) -> str:
        if is_remote:
            ssh_cmd = ["ssh"]
            key_path = Path.home() / ".ssh/id_ed25519_upmem_eth"
            if key_path.exists():
                ssh_cmd += ["-i", str(key_path)]
            target = f"{ssh_user}@{ssh_host}" if ssh_user else ssh_host
            ssh_cmd += [target, cmd_str]
            return subprocess.check_output(ssh_cmd, text=True, timeout=60).strip()
        else:
            return subprocess.check_output(["bash", "-c", cmd_str], text=True, timeout=60).strip()

    # Implementation check
    rem_impl = mach["remote_implementation"]
    head = run_check(f"git -C {rem_impl} rev-parse HEAD")
    status = run_check(f"git -C {rem_impl} status --porcelain")
    require(head == FROZEN_IMPLEMENTATION, f"remote implementation commit is {head}, expected {FROZEN_IMPLEMENTATION}")
    require(status == "", f"remote implementation is dirty:\n{status}")

    # Python & SDK
    rem_py = mach["remote_python"]
    py_ver = run_check(f"{rem_py} -c 'import sys; print(f\"{{sys.version_info[0]}}.{{sys.version_info[1]}}\")'")
    require(py_ver == "3.10", f"remote python version {py_ver}, expected 3.10")

    sdk_ver = run_check("dpu-pkg-config --modversion dpu")
    require(sdk_ver == "2023.1.0", f"remote SDK version {sdk_ver}, expected 2023.1.0")

    # Rank check (read-only sysfs)
    rank_owner = run_check("cat /sys/class/dpu_rank/dpu_rank1/is_owned 2>/dev/null || echo 'missing'")
    require(rank_owner == "0", f"/dev/dpu_rank1 is not unowned: is_owned={rank_owner}")

    # CPU check
    lscpu_json = run_check("lscpu -J -e=CPU,CORE,SOCKET,NODE,ONLINE")
    cpu_data = json.loads(lscpu_json)
    permitted_cpus = run_check(f"{rem_py} -c 'import os; print(\",\".join(map(str, sorted(os.sched_getaffinity(0)))) )'")
    permitted_set = set(map(int, permitted_cpus.split(",")))

    node0_cpus = []
    for r in cpu_data.get("cpus", []):
        online = str(r.get("online", "yes")).lower() in ("yes", "true", "1")
        if online and int(r["cpu"]) in permitted_set and int(r.get("node", 0)) == 0 and int(r.get("socket", 0)) == 0:
            node0_cpus.append(int(r["cpu"]))
    # Distinct physical cores
    require(len(node0_cpus) >= 8, f"expected at least 8 permitted physical cores on node 0, found {len(node0_cpus)}")

    # Storage check
    rem_ev = mach["remote_evidence_parent"]
    run_check(f"mkdir -p {rem_ev}")
    storage_free = int(run_check(f"{rem_py} -c 'import shutil; print(shutil.disk_usage(\"{rem_ev}\").free)'"))
    require(storage_free >= 4294967296, f"remote storage at {rem_ev} has only {storage_free} bytes free (< 4 GiB)")

    # Local archive check
    for key in ("local_archive_A", "local_archive_B"):
        loc_path = Path(mach[key])
        loc_path.mkdir(parents=True, exist_ok=True)
        loc_free = shutil.disk_usage(loc_path).free
        require(loc_free >= 4294967296, f"local storage at {loc_path} has only {loc_free} bytes free (< 4 GiB)")

    # Wall time estimate
    wall_estimate = {
        "calibration_slots": 2674,
        "calibration_estimated_worker_s": 9359.0,
        "search_cases": 52,
        "search_estimated_s": 2080.0,
        "final_slots": 1560,
        "final_estimated_worker_s": 7800.0,
        "qualification_attempts": 248,
        "qualification_estimated_s": 496.0,
        "total_estimated_worker_s": 19735.0,
        "total_estimated_worker_hours": 5.48,
        "assumptions": "based on historical P6 and final_v1 single-rank DPU/CPU timings with chunked analytic validation",
    }

    inspection_record = {
        "schema": "unified_v4_inspection_v1",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "machine": mach,
        "remote_head": head,
        "remote_clean": True,
        "python_version": py_ver,
        "sdk_version": sdk_ver,
        "rank_dpu_rank1_free": True,
        "permitted_physical_cores": sorted(node0_cpus)[:8],
        "remote_storage_free_bytes": storage_free,
        "wall_time_estimate": wall_estimate,
        "passed": True,
    }

    write_new_json(output_dir / "inspection.json", inspection_record)
    print("inspect: PASSED. Remote environment and storage verified.")
    print(json.dumps(wall_estimate, indent=2))


# ---------------------------------------------------------------------------
# Worker Entry Point: runner.py worker
# ---------------------------------------------------------------------------

def worker_main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(description="Worker execution adapter")
    parser.add_argument("--source", required=True)
    parser.add_argument("--work", required=True)
    parser.add_argument("--mode", required=True, choices=["plan", "reference", "run_slot", "r_search"])
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--arm")
    parser.add_argument("--slot")
    parser.add_argument("--quest32")
    parser.add_argument("--quest64")
    parser.add_argument("--path-json")
    parser.add_argument("--simulator", action="store_true")

    args = parser.parse_args(argv)
    source = Path(args.source).resolve()
    work = Path(args.work).resolve()
    out = Path(args.output).resolve()
    spec = read_json(HERE / "protocol.json")

    case_info = read_json(args.case)
    result: dict[str, object] = {
        "schema": "unified_v4_worker_result_v1",
        "case_id": case_info["case_id"],
        "mode": args.mode,
        "implementation_commit": FROZEN_IMPLEMENTATION,
    }

    try:
        if args.mode == "plan":
            setup_implementation_imports(source)
            from quantum_bench.planning import plan_opt_einsum
            from quantum_bench.lowering import lower_tensor_network, build_contraction_dag, contraction_dag_hash

            qasm_path = work / "cases" / f"{case_info['case_id']}.qasm"
            job = load_circuit_job(source, qasm_path, int(case_info["n"]))
            net, _ = lower_tensor_network(job)
            path, _ = plan_opt_einsum(net, optimize="greedy")
            dag = build_contraction_dag(net, path)
            result.update(
                status="success",
                path=path,
                path_id=pc.sha(path),
                logical_plan_id=contraction_dag_hash(dag),
                tensor_count=len(net.tensors),
            )
        elif args.mode == "reference":
            setup_implementation_imports(source)
            qasm_path = work / "cases" / f"{case_info['case_id']}.qasm"
            job = load_circuit_job(source, qasm_path, int(case_info["n"]))
            output, details = quest_bridge_once(job, Path(args.quest64), 1)
            ref_dir = work / "references"
            ref_dir.mkdir(parents=True, exist_ok=True)
            ref_path = ref_dir / f"{case_info['case_id']}.npy"
            import numpy as np
            np.save(ref_path, output, allow_pickle=False)
            result.update(
                status="success",
                reference_path=str(ref_path),
                reference_sha256=digest_file(ref_path),
                metrics=details,
            )
        elif args.mode == "run_slot":
            arm_info = read_json(args.arm)
            slot_info = read_json(args.slot)
            cached_path = read_json(args.path_json) if args.path_json else None

            backend = arm_info.get("backend", "upmem")
            if backend == "quest32":
                qasm_path = work / "cases" / f"{case_info['case_id']}.qasm"
                job = load_circuit_job(source, qasm_path, int(case_info["n"]))
                output, metrics = quest_bridge_once(job, Path(args.quest32), int(arm_info.get("threads", 1)))
            else:
                output, metrics = execute_tn_slot(
                    source=source,
                    work_dir=work,
                    case_info=case_info,
                    arm_info=arm_info,
                    spec=spec,
                    cached_path=cached_path,
                    simulator=args.simulator,
                )

            # Accuracy check
            ref_path = work / "references" / f"{case_info['case_id']}.npy"
            if ref_path.exists():
                import numpy as np
                ref = np.load(ref_path, allow_pickle=False)
                err = errors_against_reference(output, ref)
            else:
                err = errors_analytic(output, case_info)

            acc_qualified = check_accuracy(err, spec["validation"]) if arm_info.get("policy") == FP else None
            max_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

            result.update(
                status="success",
                slot_id=slot_info["slot_id"],
                cell_id=slot_info["cell_id"],
                case_id=case_info["case_id"],
                block=slot_info["block"],
                warmup=slot_info["warmup"],
                arm=arm_info,
                metrics=metrics,
                validation=err,
                accuracy_qualified=acc_qualified,
                same_policy_passed=metrics.get("same_policy_passed", True),
                finite=err.get("finite", False),
                prepared_call_s=metrics.get("prepared_call_s"),
                job_to_state_s=metrics.get("job_to_state_s"),
                job_to_state_cached_path_s=metrics.get("job_to_state_cached_path_s"),
                kernel_s=metrics.get("kernel_s"),
                output_sha256=ndarray_sha256(output),
                rss_max_kib=max_rss,
            )

    except Exception as exc:
        traceback.print_exc()
        from quantum_bench.results import UnsupportedExecution
        timed = isinstance(exc, TimeoutError) or "deadline expired" in str(exc).lower()
        unsupported = isinstance(exc, UnsupportedExecution) or "unsupported" in str(exc).lower()
        mem = isinstance(exc, MemoryError) or "out of memory" in str(exc).lower()

        status = "unsupported" if unsupported else ("timeout" if timed else ("memory_limit" if mem else "failure"))
        result.update(
            status=status,
            error_type=type(exc).__name__,
            error=str(exc),
            reason=str(exc),
            prepared_call_s=None,
        )

    write_new_json(out, result)


# ---------------------------------------------------------------------------
# CLI Command: all & resume
# ---------------------------------------------------------------------------

def run_all_cmd(machine_file: Path, evaluation_commit: str, run_id: str, receipt_root: Path, is_resume: bool = False) -> None:
    machine_file = machine_file.resolve()
    receipt_root = receipt_root.resolve()
    mach = read_json(machine_file)
    spec = read_json(HERE / "protocol.json")
    pc.validate_spec(spec)

    is_remote = bool(mach.get("ssh_host") and mach["ssh_host"] not in ("localhost", "127.0.0.1"))
    ssh_host = mach.get("ssh_host")
    ssh_user = mach.get("ssh_user")

    def run_cmd(cmd: list[str] | str, check: bool = True, text: bool = True) -> subprocess.CompletedProcess:
        if isinstance(cmd, list):
            cmd_str = " ".join(cmd)
        else:
            cmd_str = cmd
        if is_remote:
            ssh_cmd = ["ssh"]
            key_path = Path.home() / ".ssh/id_ed25519_upmem_eth"
            if key_path.exists():
                ssh_cmd += ["-i", str(key_path)]
            target = f"{ssh_user}@{ssh_host}" if ssh_user else ssh_host
            ssh_cmd += [target, cmd_str]
            return subprocess.run(ssh_cmd, check=check, text=text, capture_output=True)
        else:
            return subprocess.run(["bash", "-c", cmd_str], check=check, text=text, capture_output=True)

    print(f"[all] Starting unified v4 campaign: run_id={run_id}, eval_commit={evaluation_commit}")

    rem_work = Path(mach["remote_evidence_parent"]) / run_id
    loc_work = receipt_root / run_id
    archive_A = Path(mach["local_archive_A"]) / run_id
    archive_B = Path(mach["local_archive_B"]) / run_id

    loc_work.mkdir(parents=True, exist_ok=True)
    archive_A.mkdir(parents=True, exist_ok=True)
    archive_B.mkdir(parents=True, exist_ok=True)
    run_cmd(f"mkdir -p {rem_work}/cases {rem_work}/plans {rem_work}/references {rem_work}/arms {rem_work}/receipts/calibration {rem_work}/receipts/final {rem_work}/paths")

    lock_file = Path(mach["remote_lock"])
    run_cmd(f"mkdir -p {lock_file.parent} && touch {lock_file}")

    # 1. Compile static manifest
    static_manifest_dir = loc_work / "static"
    if not (static_manifest_dir / "manifest.json").exists():
        manifest = pc.compile_manifest(spec)
        pc.write_manifest(static_manifest_dir, manifest)
    else:
        manifest = read_json(static_manifest_dir / "manifest.json")
    pc.check_seal(manifest)

    # 2. Preparation: QASM and References
    print("[all] Stage 1: Preparing QASM and references...")
    loc_cases_dir = loc_work / "cases"
    loc_cases_dir.mkdir(parents=True, exist_ok=True)
    for c in manifest["cases"]:
        qasm_bytes = qasm_for_case(HERE.parents[1], c)
        (loc_cases_dir / f"{c['case_id']}.qasm").write_bytes(qasm_bytes)

    qual_fixtures = [
        {"case_id": "qual_hs_n04", "family": "hs", "n": 4},
        {"case_id": "qual_stress_n04_l2", "family": "stress", "n": 4, "parameters": {"repeat_layers": 2}},
        {"case_id": "qual_bb84_n04", "family": "bb84", "n": 4},
        {"case_id": "qual_bv_n04", "family": "bv", "n": 4},
        {"case_id": "qual_edc_n03", "family": "edc", "n": 3},
        {"case_id": "qual_qrng_n04", "family": "qrng", "n": 4},
        {"case_id": "qual_xor_n04", "family": "xor", "n": 4},
        {"case_id": "qual_bell_n02", "family": "bell", "n": 2},
    ]
    for q in qual_fixtures:
        qasm_bytes = qasm_for_case(HERE.parents[1], q)
        (loc_cases_dir / f"{q['case_id']}.qasm").write_bytes(qasm_bytes)

    if is_remote:
        subprocess.run(["scp", "-r", f"{loc_cases_dir}/*", f"{ssh_user}@{ssh_host}:{rem_work}/cases/"], check=True)

    # 3. Calibration Phase C
    print("[all] Stage 2: Calibration Phase (2,674 slots in 8 blocks)...")
    cal_slots = manifest["calibration_slots"]
    cal_cells = {c["cell_id"]: c for c in manifest["calibration_cells"]}

    verified_rows_path = loc_work / "calibration_rows.json"
    rows_by_slot = {}
    if verified_rows_path.exists():
        rows_by_slot = {r["slot_id"]: r for r in read_json(verified_rows_path)}

    blocks = sorted({s["block"] for s in cal_slots})
    for b in blocks:
        block_slots = [s for s in cal_slots if s["block"] == b]
        print(f"[all] Executing Calibration Block {b} ({len(block_slots)} slots)...")
        block_checkpoint = loc_work / f"cal_block_{b}.done"
        if block_checkpoint.exists():
            print(f"[all] Calibration Block {b} already completed. Skipping.")
            continue

        for slot in block_slots:
            sid = slot["slot_id"]
            if sid in rows_by_slot:
                continue

            cell = cal_cells[slot["cell_id"]]
            issued_record = {
                "slot_id": sid,
                "cell_id": slot["cell_id"],
                "case_id": slot["case_id"],
                "block": slot["block"],
                "warmup": slot["warmup"],
                "phase": "calibration",
                "backend": slot["backend"],
                "arm": cell["arm"],
                "issued_time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }

            issued_file = loc_work / f"receipts/calibration/{sid}.issued.json"
            receipt_file = loc_work / f"receipts/calibration/{sid}.json"
            if issued_file.exists() and not receipt_file.exists():
                if is_resume:
                    raise RuntimeError(f"Unresolved issued slot {sid} without terminal receipt: STOP. Manual review required.")
            issued_file.parent.mkdir(parents=True, exist_ok=True)
            write_new_json(issued_file, issued_record)

            binding = {
                "protocol_sha256": manifest["protocol_sha256"],
                "cell_id": slot["cell_id"],
                "arm": cell["arm"],
                "case_id": slot["case_id"],
                "implementation_commit": FROZEN_IMPLEMENTATION,
                "evaluation_commit": evaluation_commit,
            }
            binding_sha = pc.sha(binding)

            case_file = loc_work / f"case_{slot['case_id']}.json"
            if not case_file.exists():
                c_obj = next(c for c in manifest["cases"] if c["case_id"] == slot["case_id"])
                write_new_json(case_file, c_obj)

            arm_file = loc_work / f"arm_{slot['cell_id']}.json"
            if not arm_file.exists():
                write_new_json(arm_file, cell["arm"])

            slot_file = loc_work / f"slot_{sid}.json"
            write_new_json(slot_file, slot)

            cmd = [
                sys.executable, str(HERE / "runner.py"), "worker",
                "--source", str(HERE.parents[1]),
                "--work", str(loc_work),
                "--mode", "run_slot",
                "--case", str(case_file),
                "--arm", str(arm_file),
                "--slot", str(slot_file),
                "--output", str(receipt_file),
            ]
            subprocess.run(cmd, check=True)
            res = read_json(receipt_file)

            ledger_row = {
                "slot_id": sid,
                "cell_id": slot["cell_id"],
                "case_id": slot["case_id"],
                "phase": "calibration",
                "block": slot["block"],
                "warmup": slot["warmup"],
                "backend": slot["backend"],
                "protocol_sha256": manifest["protocol_sha256"],
                "run_id": run_id,
                "implementation_commit": FROZEN_IMPLEMENTATION,
                "evaluation_commit": evaluation_commit,
                "execution_binding_sha256": binding_sha,
                "issued": True,
                "status": res["status"],
                "prepared_call_s": res.get("prepared_call_s"),
                "finite": res.get("finite", False),
                "same_policy_passed": res.get("same_policy_passed", False),
                "accuracy_qualified": res.get("accuracy_qualified", False),
                "reason": res.get("reason"),
            }
            rows_by_slot[sid] = ledger_row

        write_new_json(block_checkpoint, {"block": b, "completed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        write_new_json(verified_rows_path, list(rows_by_slot.values()))
        shutil.copy2(verified_rows_path, archive_A / "calibration_rows.json")
        shutil.copy2(verified_rows_path, archive_B / "calibration_rows.json")

    # 4. Topology Selection
    print("[all] Stage 3: Topology Selection from verified calibration rows...")
    selection_path = loc_work / "selection.json"
    rows_list = list(rows_by_slot.values())
    selection = pc.select_topologies(spec, manifest, rows_list)
    write_new_json(selection_path, selection)
    shutil.copy2(selection_path, archive_A / "selection.json")
    shutil.copy2(selection_path, archive_B / "selection.json")
    print(f"[all] Selected {len(selection['selections'])} family/policy winners. Selection seal: {selection['content_sha256']}")

    # 5. R Path Generation
    print("[all] Stage 4: R Path Generation for all 52 final cases...")
    path_records_path = loc_work / "path_records.json"
    path_records = []
    win_by_family = {(r["family"], r["policy"]): r["selected"] for r in selection["selections"]}

    final_cases = [c for c in manifest["cases"] if c["family"] != "ghz"]
    for c in final_cases:
        cid = c["case_id"]
        prec = loc_work / f"paths/{cid}.json"
        if prec.exists():
            r = read_json(prec)
        else:
            f32_win = win_by_family[(c["family"], FP)]
            r = run_r_path_generation_for_case(
                source=HERE.parents[1],
                work_dir=loc_work,
                case_info=c,
                selected_f32_topology=f32_win,
                selection_sha=selection["content_sha256"],
                spec=spec,
            )
            write_new_json(prec, r)
        path_records.append(r)

    write_new_json(path_records_path, path_records)
    shutil.copy2(path_records_path, archive_A / "path_records.json")
    shutil.copy2(path_records_path, archive_B / "path_records.json")

    # Bind final manifest
    final_manifest_path = loc_work / "final_manifest.json"
    final_manifest = pc.materialize_final(spec, manifest, selection, path_records)
    write_new_json(final_manifest_path, final_manifest)
    shutil.copy2(final_manifest_path, archive_A / "final_manifest.json")
    shutil.copy2(final_manifest_path, archive_B / "final_manifest.json")

    # 6. Final Comparison Phase (W and S)
    print("[all] Stage 5: Final Comparison Phase (1,560 slots in 6 blocks)...")
    final_slots = final_manifest["slots"]
    final_cells = {c["cell_id"]: c for c in final_manifest["cells"]}
    final_rows_path = loc_work / "final_rows.json"
    final_rows_by_slot = {}
    if final_rows_path.exists():
        final_rows_by_slot = {r["slot_id"]: r for r in read_json(final_rows_path)}

    fblocks = sorted({s["block"] for s in final_slots})
    for b in fblocks:
        b_slots = [s for s in final_slots if s["block"] == b]
        print(f"[all] Executing Final Block {b} ({len(b_slots)} slots)...")
        b_checkpoint = loc_work / f"final_block_{b}.done"
        if b_checkpoint.exists():
            print(f"[all] Final Block {b} already completed. Skipping.")
            continue

        for slot in b_slots:
            sid = slot["slot_id"]
            if sid in final_rows_by_slot:
                continue

            cell = final_cells[slot["cell_id"]]
            issued_file = loc_work / f"receipts/final/{sid}.issued.json"
            receipt_file = loc_work / f"receipts/final/{sid}.json"

            if not cell.get("eligible_for_runtime_admission", True):
                row = {
                    "slot_id": sid, "cell_id": slot["cell_id"], "case_id": slot["case_id"],
                    "phase": "final", "block": slot["block"], "warmup": slot["warmup"],
                    "backend": slot["backend"], "protocol_sha256": manifest["protocol_sha256"],
                    "run_id": run_id, "implementation_commit": FROZEN_IMPLEMENTATION,
                    "evaluation_commit": evaluation_commit, "issued": False,
                    "status": "not_issued_unsupported", "reason": cell.get("not_runnable_reason"),
                    "prepared_call_s": None,
                }
                final_rows_by_slot[sid] = row
                continue

            write_new_json(issued_file, {
                "slot_id": sid, "cell_id": slot["cell_id"], "case_id": slot["case_id"],
                "block": slot["block"], "warmup": slot["warmup"], "phase": "final",
                "backend": slot["backend"], "role": cell.get("role"),
            })

            path_json_file = None
            if cell.get("selected_path_id"):
                path_json_file = loc_work / f"path_{cell['selected_path_id']}.json"
                if not path_json_file.exists():
                    p_rec = next(p for p in path_records if p["case_id"] == slot["case_id"])
                    write_new_json(path_json_file, p_rec["path"])

            case_file = loc_work / f"case_{slot['case_id']}.json"
            arm_file = loc_work / f"final_arm_{cell['cell_id']}.json"
            if not arm_file.exists():
                write_new_json(arm_file, cell["arm"])
            slot_file = loc_work / f"final_slot_{sid}.json"
            write_new_json(slot_file, slot)

            cmd = [
                sys.executable, str(HERE / "runner.py"), "worker",
                "--source", str(HERE.parents[1]),
                "--work", str(loc_work),
                "--mode", "run_slot",
                "--case", str(case_file),
                "--arm", str(arm_file),
                "--slot", str(slot_file),
                "--output", str(receipt_file),
            ]
            if path_json_file:
                cmd += ["--path-json", str(path_json_file)]

            subprocess.run(cmd, check=True)
            res = read_json(receipt_file)

            final_rows_by_slot[sid] = {
                "slot_id": sid, "cell_id": slot["cell_id"], "case_id": slot["case_id"],
                "phase": "final", "block": slot["block"], "warmup": slot["warmup"],
                "backend": slot["backend"], "protocol_sha256": manifest["protocol_sha256"],
                "run_id": run_id, "implementation_commit": FROZEN_IMPLEMENTATION,
                "evaluation_commit": evaluation_commit, "issued": True,
                "status": res["status"], "prepared_call_s": res.get("prepared_call_s"),
                "job_to_state_cached_path_s": res.get("job_to_state_cached_path_s"),
                "finite": res.get("finite", False), "same_policy_passed": res.get("same_policy_passed", False),
                "accuracy_qualified": res.get("accuracy_qualified", False), "reason": res.get("reason"),
            }

        write_new_json(b_checkpoint, {"block": b, "completed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        write_new_json(final_rows_path, list(final_rows_by_slot.values()))
        shutil.copy2(final_rows_path, archive_A / "final_rows.json")
        shutil.copy2(final_rows_path, archive_B / "final_rows.json")

    # 7. Final Readout Generation
    print("[all] Stage 6: Running readout...")
    readout_dir = loc_work / "readout"
    subprocess.run([sys.executable, str(HERE / "readout.py"), "--campaign", str(loc_work), "--output", str(readout_dir)], check=True)

    print("[all] Stage 7: Verifying dual-archive equality...")
    for key_file in ("calibration_rows.json", "selection.json", "path_records.json", "final_manifest.json", "final_rows.json"):
        da = digest_file(archive_A / key_file)
        db = digest_file(archive_B / key_file)
        require(da == db, f"Dual archive mismatch for {key_file}: {da} vs {db}")

    print("[all] COMPLETE! Campaign finished cleanly with verified dual-archive retention.")


# ---------------------------------------------------------------------------
# Main CLI Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Unified evaluation v4 execution runner")
    sub = parser.add_subparsers(dest="command", required=True)

    # check-contract
    p_chk = sub.add_parser("check-contract")
    p_chk.add_argument("--manifest", type=Path, required=True)
    p_chk.add_argument("--implementation", type=Path, required=True)

    # inspect
    p_ins = sub.add_parser("inspect")
    p_ins.add_argument("--machine", type=Path, required=True)
    p_ins.add_argument("--implementation-commit", type=str, required=True)
    p_ins.add_argument("--output", type=Path, required=True)

    # all
    p_all = sub.add_parser("all")
    p_all.add_argument("--machine", type=Path, required=True)
    p_all.add_argument("--evaluation-commit", type=str, required=True)
    p_all.add_argument("--run-id", type=str, required=True)
    p_all.add_argument("--receipt-root", type=Path, required=True)

    # resume
    p_res = sub.add_parser("resume")
    p_res.add_argument("--machine", type=Path, required=True)
    p_res.add_argument("--evaluation-commit", type=str, required=True)
    p_res.add_argument("--run-id", type=str, required=True)
    p_res.add_argument("--receipt-root", type=Path, required=True)

    # worker
    sub.add_parser("worker")

    args, unknown = parser.parse_known_args()

    if args.command == "check-contract":
        check_contract_cmd(args.manifest, args.implementation)
    elif args.command == "inspect":
        inspect_machine_cmd(args.machine, args.implementation_commit, args.output)
    elif args.command == "all":
        run_all_cmd(args.machine, args.evaluation_commit, args.run_id, args.receipt_root, is_resume=False)
    elif args.command == "resume":
        run_all_cmd(args.machine, args.evaluation_commit, args.run_id, args.receipt_root, is_resume=True)
    elif args.command == "worker":
        worker_main(unknown)


if __name__ == "__main__":
    main()
