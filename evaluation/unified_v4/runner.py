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
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import tempfile
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


def write_atomic_json(path: Path | str, value: object) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("wb") as f:
        f.write(canonical(value) + b"\n")
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)


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


def apply_thread_environment(spec: Mapping[str, object], threads: int = 1) -> None:
    for k, v in spec.get("thread_environment", {}).items():
        if k == "OMP_NUM_THREADS":
            os.environ[k] = str(threads)
        else:
            os.environ[k] = str(v)


def quest_in_subprocess(
    source: Path | str,
    qasm_path: Path | str,
    n_qubits: int,
    libfile: Path | str,
    threads: int,
    output_npy: Path | str | None = None,
) -> tuple[object, dict]:
    import numpy as np

    source = Path(source).resolve()
    qasm_path = Path(qasm_path).resolve()
    libfile = Path(libfile).resolve()
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        out_npy = Path(output_npy).resolve() if output_npy else (tdp / "output.npy")
        out_npy.parent.mkdir(parents=True, exist_ok=True)
        metrics_json = tdp / "metrics.json"

        script = f"""
import os, sys
from pathlib import Path

os.environ["OMP_NUM_THREADS"] = "{threads}"
os.environ["OMP_DYNAMIC"] = "FALSE"
os.environ["OMP_PROC_BIND"] = "TRUE"
os.environ["OMP_PLACES"] = "cores"
avail = sorted(os.sched_getaffinity(0))
cores = set(avail[:min(len(avail), {threads})])
os.sched_setaffinity(0, cores)

sys.path.insert(0, "{HERE}")
import runner
source = Path("{source}")
libfile = Path("{libfile}")
qasm_path = Path("{qasm_path}")
job = runner.load_circuit_job(source, qasm_path, {n_qubits})
output, metrics = runner.quest_bridge_once(job, libfile, {threads})

import numpy as np
np.save("{out_npy}", output, allow_pickle=False)
runner.write_new_json("{metrics_json}", metrics)
"""
        res = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
        require(res.returncode == 0, f"QuEST subprocess failed (exit {res.returncode}):\n{res.stderr}\n{res.stdout}")
        metrics = read_json(metrics_json)
        output = np.load(out_npy, allow_pickle=False)
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
            qasm_path = work / "cases" / f"{case_info['case_id']}.qasm"
            ref_dir = work / "references"
            ref_dir.mkdir(parents=True, exist_ok=True)
            ref_path = ref_dir / f"{case_info['case_id']}.npy"
            output, details = quest_in_subprocess(source, qasm_path, int(case_info["n"]), Path(args.quest64), 1, output_npy=ref_path)
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
                output, metrics = quest_in_subprocess(source, qasm_path, int(case_info["n"]), Path(args.quest32), int(arm_info.get("threads", 1)))
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
# CLI Commands: qualify, generate-r-paths, run-block
# ---------------------------------------------------------------------------

def qualify_cmd(
    work: Path,
    source: Path,
    build: Path,
    lock: Path,
    spec_path: Path | None = None,
) -> None:
    work = work.resolve()
    source = source.resolve()
    build = build.resolve()
    lock = lock.resolve()
    spec = read_json(spec_path or (HERE / "protocol.json"))
    pc.validate_spec(spec)

    apply_thread_environment(spec, 1)

    qual_dir = work / "qualification"
    qual_dir.mkdir(parents=True, exist_ok=True)
    cases_dir = work / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    ref_dir = work / "references"
    ref_dir.mkdir(parents=True, exist_ok=True)

    # 1. Preflight rank inventory
    print("[qualify] 1/4: Running preflight rank inventory...")
    lock_fd = os.open(str(lock), os.O_RDWR | os.O_CREAT, 0o666)
    t0 = time.time()
    while True:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except (BlockingIOError, OSError):
            if time.time() - t0 > 900:
                raise TimeoutError(f"flock timeout on {lock}")
            time.sleep(1)

    try:
        inv_bin = build / "rank_inventory"
        require(inv_bin.exists(), f"rank_inventory binary not found at {inv_bin}")
        res = subprocess.check_output([str(inv_bin), "--allow-physical"], text=True).strip()
        inv = json.loads(res)
        require(inv.get("released") is True, f"rank_inventory failed to release rank: {res}")
        require(inv.get("rank_count") == 1, f"rank_inventory unexpected rank_count: {res}")
        require(inv.get("dpu_capacity") == 64, f"rank_inventory unexpected dpu_capacity: {res}")
        inv["binary_sha256"] = digest_file(inv_bin)
        inv["timestamp_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        write_new_json(qual_dir / "preflight_rank_inventory.json", inv)
        print("[qualify] Preflight rank inventory PASSED: /dev/dpu_rank1 verified and released.")
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)

    # 2. QuEST qualification: 8 semantic fixtures × f32/f64 × P1/P8 = 32 calls
    print("[qualify] 2/4: Running QuEST qualification (32 calls)...")
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
    p1_lib = build / "quest-p1/lib/libquest_bridge.so"
    p2_lib = build / "quest-p2/lib/libquest_bridge.so"
    require(p1_lib.exists(), f"quest-p1 lib missing: {p1_lib}")
    require(p2_lib.exists(), f"quest-p2 lib missing: {p2_lib}")

    for q in qual_fixtures:
        qasm_p = cases_dir / f"{q['case_id']}.qasm"
        if not qasm_p.exists():
            qasm_p.write_bytes(qasm_for_case(source, q))

    stress4_ref_path = ref_dir / "qual_stress_n04_l2.npy"
    if not stress4_ref_path.exists():
        quest_in_subprocess(source, cases_dir / "qual_stress_n04_l2.qasm", 4, p2_lib, 1, output_npy=stress4_ref_path)

    quest_results = []
    for q in qual_fixtures:
        cid = q["case_id"]
        qasm_path = cases_dir / f"{cid}.qasm"
        for prec, libfile in ((1, p1_lib), (2, p2_lib)):
            for threads in (1, 8):
                output, metrics = quest_in_subprocess(source, qasm_path, int(q["n"]), libfile, threads)
                ref_p = ref_dir / f"{cid}.npy"
                if ref_p.exists():
                    import numpy as np
                    ref = np.load(ref_p, allow_pickle=False)
                    err = errors_against_reference(output, ref)
                else:
                    err = errors_analytic(output, q)
                acc_ok = check_accuracy(err, spec["validation"])
                require(acc_ok, f"QuEST accuracy check failed for {cid} prec={prec} threads={threads}")
                quest_results.append({
                    "case_id": cid,
                    "precision": prec,
                    "threads": threads,
                    "metrics": metrics,
                    "validation": err,
                    "accuracy_qualified": acc_ok,
                })
    require(len(quest_results) == 32, f"expected 32 QuEST qualification calls, got {len(quest_results)}")
    write_new_json(qual_dir / "quest_qualification.json", quest_results)
    print(f"[qualify] QuEST qualification PASSED (all {len(quest_results)} calls verified).")

    # 3. Tiny UPMEM qualification: 54 configs × 2 tiny fixtures = 108 calls each
    manifest_p = work / "static/manifest.json"
    manifest = read_json(manifest_p)
    upmem_arms = {}
    for c in manifest["calibration_cells"]:
        if c["arm"]["backend"] == "upmem":
            upmem_arms[pc.sha(c["arm"])] = c["arm"]
    unique_configs = [upmem_arms[k] for k in sorted(upmem_arms)]
    require(len(unique_configs) == 54, f"expected 54 unique configs, got {len(unique_configs)}")

    tiny_fixtures = [
        {"case_id": "qual_hs_n04", "family": "hs", "n": 4},
        {"case_id": "qual_stress_n04_l2", "family": "stress", "n": 4, "parameters": {"repeat_layers": 2}},
    ]

    # a. Simulator qualification (108 calls)
    print("[qualify] 3a/4: Running UPMEM SDK simulator qualification (108 calls)...")
    sim_results = []
    for cfg in unique_configs:
        for fix in tiny_fixtures:
            cid = fix["case_id"]
            out, metrics = execute_tn_slot(
                source=source,
                work_dir=work,
                case_info=fix,
                arm_info=cfg,
                spec=spec,
                simulator=True,
            )
            ref_p = ref_dir / f"{cid}.npy"
            if ref_p.exists():
                import numpy as np
                ref = np.load(ref_p, allow_pickle=False)
                err = errors_against_reference(out, ref)
            else:
                err = errors_analytic(out, fix)
            if cfg.get("policy") == FP:
                require(check_accuracy(err, spec["validation"]), f"sim accuracy failed for {cid}")
            require(metrics.get("same_policy_passed") is True, f"sim replay failed for {cid}")
            sim_results.append({
                "case_id": cid,
                "arm": cfg,
                "metrics": metrics,
                "validation": err,
            })
    require(len(sim_results) == 108, f"expected 108 sim results, got {len(sim_results)}")
    write_new_json(qual_dir / "upmem_sim_qualification.json", sim_results)
    print(f"[qualify] UPMEM simulator qualification PASSED (all {len(sim_results)} calls verified).")

    # b. Physical qualification (108 calls)
    print("[qualify] 3b/4: Running UPMEM physical hardware qualification (108 calls)...")
    lock_fd = os.open(str(lock), os.O_RDWR | os.O_CREAT, 0o666)
    t0 = time.time()
    while True:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except (BlockingIOError, OSError):
            if time.time() - t0 > 900:
                raise TimeoutError(f"flock timeout on {lock}")
            time.sleep(1)

    try:
        os.environ["UPMEM_ALLOW_PHYSICAL_HARDWARE"] = "1"
        phy_results = []
        for cfg in unique_configs:
            for fix in tiny_fixtures:
                cid = fix["case_id"]
                out, metrics = execute_tn_slot(
                    source=source,
                    work_dir=work,
                    case_info=fix,
                    arm_info=cfg,
                    spec=spec,
                    simulator=False,
                )
                ref_p = ref_dir / f"{cid}.npy"
                if ref_p.exists():
                    import numpy as np
                    ref = np.load(ref_p, allow_pickle=False)
                    err = errors_against_reference(out, ref)
                else:
                    err = errors_analytic(out, fix)
                if cfg.get("policy") == FP:
                    require(check_accuracy(err, spec["validation"]), f"phy accuracy failed for {cid}")
                require(metrics.get("same_policy_passed") is True, f"phy replay failed for {cid}")
                phy_results.append({
                    "case_id": cid,
                    "arm": cfg,
                    "metrics": metrics,
                    "validation": err,
                })
        require(len(phy_results) == 108, f"expected 108 physical results, got {len(phy_results)}")
        write_new_json(qual_dir / "upmem_phy_qualification.json", phy_results)
        print(f"[qualify] UPMEM physical qualification PASSED (all {len(phy_results)} calls verified).")
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)

    # 4. Tiny R determinism qualification: 4 searches
    print("[qualify] 4/4: Running tiny R determinism qualification (4 searches)...")
    r_det_results = []
    dummy_sha = "0" * 64
    topo_d1_t8 = {"dpus": 1, "tasklets": 8}
    for fix in tiny_fixtures:
        cid = fix["case_id"]
        run1 = run_r_path_generation_for_case(source, work, fix, topo_d1_t8, dummy_sha, spec)
        run2 = run_r_path_generation_for_case(source, work, fix, topo_d1_t8, dummy_sha, spec)
        require(run1["status"] == run2["status"], f"R determinism status mismatch for {cid}")
        require(run1["path"] == run2["path"], f"R determinism path mismatch for {cid}")
        require(run1["r_score"] == run2["r_score"], f"R determinism score mismatch for {cid}")
        r_det_results.append({"case_id": cid, "run1": run1, "run2": run2})
    require(len(r_det_results) == 2, "expected 2 pairs of R determinism runs")
    write_new_json(qual_dir / "r_determinism_qualification.json", r_det_results)
    print("[qualify] Tiny R determinism qualification PASSED.")

    write_new_json(qual_dir / "qualification.done", {
        "status": "passed",
        "completed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "quest_calls": len(quest_results),
        "sim_calls": len(sim_results),
        "physical_calls": len(phy_results),
        "r_searches": len(r_det_results) * 2,
    })
    print("[qualify] ALL QUALIFICATION GATES PASSED.")


def generate_r_paths_cmd(
    work: Path,
    source: Path,
    manifest_path: Path,
    selection_path: Path,
    out_dir: Path,
    spec_path: Path | None = None,
) -> list[dict]:
    work = work.resolve()
    source = source.resolve()
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    spec = read_json(spec_path or (HERE / "protocol.json"))
    manifest = read_json(manifest_path)
    selection = read_json(selection_path)
    pc.check_seal(manifest)
    pc.check_seal(selection)

    win_by_family = {(r["family"], r["policy"]): r["selected"] for r in selection["selections"]}
    final_cases = [c for c in manifest["cases"] if c["family"] != "ghz"]
    require(len(final_cases) == 52, f"expected 52 final cases, got {len(final_cases)}")

    path_records = []
    print(f"[generate-r-paths] Generating R paths for {len(final_cases)} final cases...")
    for i, c in enumerate(final_cases, 1):
        cid = c["case_id"]
        prec = out_dir / f"{cid}.json"
        if prec.exists():
            r = read_json(prec)
            print(f"[generate-r-paths] [{i}/52] {cid}: already generated ({r['status']})")
        else:
            f32_win = win_by_family[(c["family"], FP)]
            print(f"[generate-r-paths] [{i}/52] {cid} (family={c['family']}, n={c['n']}): running 128-proposal search...")
            start_t = time.perf_counter()
            r = run_r_path_generation_for_case(
                source=source,
                work_dir=work,
                case_info=c,
                selected_f32_topology=f32_win,
                selection_sha=selection["content_sha256"],
                spec=spec,
            )
            elapsed = time.perf_counter() - start_t
            write_new_json(prec, r)
            print(f"[generate-r-paths] [{i}/52] {cid}: status={r['status']}, score={r.get('r_score')}, time={elapsed:.2f}s")
        path_records.append(r)

    records_file = work / "path_records.json"
    if not records_file.exists():
        write_new_json(records_file, path_records)
    print(f"[generate-r-paths] COMPLETE. All 52 path records written to {records_file}.")
    return path_records


def run_block_cmd(
    phase: str,
    block: int,
    work: Path,
    source: Path,
    build: Path,
    manifest_path: Path,
    lock: Path,
    eval_commit: str,
    run_id: str,
    paths_path: Path | None = None,
    spec_path: Path | None = None,
    simulator: bool = False,
) -> list[dict]:
    work = work.resolve()
    source = source.resolve()
    build = build.resolve()
    lock = lock.resolve()
    manifest_path = manifest_path.resolve()
    spec = read_json(spec_path or (HERE / "protocol.json"))
    pc.validate_spec(spec)

    apply_thread_environment(spec, 1)
    if not simulator:
        os.environ["UPMEM_ALLOW_PHYSICAL_HARDWARE"] = "1"

    print(f"[run-block] Acquiring flock on {lock} (phase={phase}, block={block})...")
    lock_fd = os.open(str(lock), os.O_RDWR | os.O_CREAT, 0o666)
    t0 = time.time()
    while True:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except (BlockingIOError, OSError):
            if time.time() - t0 > 900:
                raise TimeoutError(f"flock timeout on {lock}")
            time.sleep(1)
    print(f"[run-block] Lock acquired after {time.time() - t0:.1f}s.")

    try:
        st = os.statvfs(str(work))
        free_bytes = st.f_bavail * st.f_frsize
        require(free_bytes >= 2 * 1024**3, f"Storage free ({free_bytes / (1024**2):.1f} MiB) < 2 GiB before block")

        manifest = read_json(manifest_path)
        if phase == "calibration":
            slots = [s for s in manifest["calibration_slots"] if s["block"] == block]
            cells = {c["cell_id"]: c for c in manifest["calibration_cells"]}
            cases = {c["case_id"]: c for c in manifest["cases"]}
            paths_by_id = {}
        else:
            slots = [s for s in manifest["slots"] if s["block"] == block]
            cells = {c["cell_id"]: c for c in manifest["cells"]}
            static_m = read_json(work / "static/manifest.json")
            cases = {c["case_id"]: c for c in static_m["cases"]}
            paths_by_id = {}
            if paths_path and Path(paths_path).exists():
                paths_list = read_json(paths_path)
                for p in paths_list:
                    if "path_id" in p and "path" in p and p["path"] is not None:
                        paths_by_id[p["path_id"]] = p["path"]

        receipts_dir = work / "receipts" / phase
        receipts_dir.mkdir(parents=True, exist_ok=True)
        block_done_file = work / f"{phase}_block_{block}.done"
        block_rows_file = work / f"{phase}_rows_block_{block}.json"

        rows = []
        print(f"[run-block] Executing {len(slots)} slots for {phase} block {block}...")
        for i, slot in enumerate(slots, 1):
            sid = slot["slot_id"]
            cell = cells[slot["cell_id"]]
            case_obj = cases[slot["case_id"]]
            issued_file = receipts_dir / f"{sid}.issued.json"
            receipt_file = receipts_dir / f"{sid}.json"

            if receipt_file.exists():
                rec = read_json(receipt_file)
                binding = {
                    "protocol_sha256": pc.sha(spec),
                    "cell_id": slot["cell_id"],
                    "arm": cell["arm"],
                    "case_id": slot["case_id"],
                    "implementation_commit": FROZEN_IMPLEMENTATION,
                    "evaluation_commit": eval_commit,
                }
                binding_sha = pc.sha(binding)
                row = {
                    "slot_id": sid,
                    "cell_id": slot["cell_id"],
                    "case_id": slot["case_id"],
                    "phase": phase,
                    "block": slot["block"],
                    "warmup": slot["warmup"],
                    "backend": slot["backend"],
                    "protocol_sha256": pc.sha(spec),
                    "run_id": run_id,
                    "implementation_commit": FROZEN_IMPLEMENTATION,
                    "evaluation_commit": eval_commit,
                    "execution_binding_sha256": binding_sha,
                    "issued": rec.get("issued", True),
                    "status": rec["status"],
                    "prepared_call_s": rec.get("prepared_call_s"),
                    "job_to_state_cached_path_s": rec.get("job_to_state_cached_path_s"),
                    "finite": rec.get("finite", False),
                    "same_policy_passed": rec.get("same_policy_passed", False),
                    "accuracy_qualified": rec.get("accuracy_qualified", False),
                    "reason": rec.get("reason"),
                }
                rows.append(row)
                continue

            if issued_file.exists() and not receipt_file.exists():
                raise RuntimeError(f"Unresolved issued slot {sid} without terminal receipt: STOP. Manual review required.")

            st = os.statvfs(str(work))
            free_bytes = st.f_bavail * st.f_frsize
            if free_bytes < 512 * 1024**2:
                raise RuntimeError(f"EMERGENCY STOP: storage free ({free_bytes / (1024**2):.1f} MiB) < 512 MiB")
            if free_bytes < 2 * 1024**3:
                raise RuntimeError(f"STOP: storage free ({free_bytes / (1024**2):.1f} MiB) < 2 GiB before attempt")

            if phase == "final" and not cell.get("eligible_for_runtime_admission", True):
                binding = {
                    "protocol_sha256": pc.sha(spec),
                    "cell_id": slot["cell_id"],
                    "arm": cell["arm"],
                    "case_id": slot["case_id"],
                    "implementation_commit": FROZEN_IMPLEMENTATION,
                    "evaluation_commit": eval_commit,
                }
                binding_sha = pc.sha(binding)
                row = {
                    "slot_id": sid,
                    "cell_id": slot["cell_id"],
                    "case_id": slot["case_id"],
                    "phase": phase,
                    "block": slot["block"],
                    "warmup": slot["warmup"],
                    "backend": slot["backend"],
                    "protocol_sha256": pc.sha(spec),
                    "run_id": run_id,
                    "implementation_commit": FROZEN_IMPLEMENTATION,
                    "evaluation_commit": eval_commit,
                    "execution_binding_sha256": binding_sha,
                    "issued": False,
                    "status": "not_issued_unsupported",
                    "reason": cell.get("not_runnable_reason"),
                    "prepared_call_s": None,
                }
                rows.append(row)
                continue

            issued_record = {
                "slot_id": sid,
                "cell_id": slot["cell_id"],
                "case_id": slot["case_id"],
                "block": slot["block"],
                "warmup": slot["warmup"],
                "phase": phase,
                "backend": slot["backend"],
                "role": cell.get("role"),
                "arm": cell["arm"],
                "issued_time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            write_new_json(issued_file, issued_record)

            threads = int(cell["arm"].get("threads", 1))
            apply_thread_environment(spec, threads)
            avail = sorted(os.sched_getaffinity(0))
            if threads > 1:
                os.sched_setaffinity(0, set(avail[:min(len(avail), threads)]))
            else:
                os.sched_setaffinity(0, {avail[0]})

            result = {
                "schema": "unified_v4_worker_result_v1",
                "slot_id": sid,
                "cell_id": slot["cell_id"],
                "case_id": slot["case_id"],
                "block": slot["block"],
                "warmup": slot["warmup"],
                "arm": cell["arm"],
                "phase": phase,
                "implementation_commit": FROZEN_IMPLEMENTATION,
                "evaluation_commit": eval_commit,
            }

            try:
                if slot["backend"] == "quest32":
                    qasm_path = work / "cases" / f"{case_obj['case_id']}.qasm"
                    libfile = build / "quest-p1/lib/libquest_bridge.so"
                    output, metrics = quest_in_subprocess(source, qasm_path, int(case_obj["n"]), libfile, threads)
                else:
                    cached_path = None
                    if phase == "final" and cell.get("selected_path_id"):
                        cached_path = paths_by_id.get(cell["selected_path_id"])
                        require(cached_path is not None, f"cached path missing for {cell['selected_path_id']}")
                    output, metrics = execute_tn_slot(
                        source=source,
                        work_dir=work,
                        case_info=case_obj,
                        arm_info=cell["arm"],
                        spec=spec,
                        cached_path=cached_path,
                        simulator=simulator,
                    )

                ref_path = work / "references" / f"{case_obj['case_id']}.npy"
                if ref_path.exists():
                    import numpy as np
                    ref = np.load(ref_path, allow_pickle=False)
                    err = errors_against_reference(output, ref)
                else:
                    err = errors_analytic(output, case_obj)

                acc_qualified = check_accuracy(err, spec["validation"]) if cell["arm"].get("policy") == FP else bool(err.get("finite", False))
                max_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

                result.update(
                    status="success",
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

            write_new_json(receipt_file, result)

            binding = {
                "protocol_sha256": pc.sha(spec),
                "cell_id": slot["cell_id"],
                "arm": cell["arm"],
                "case_id": slot["case_id"],
                "implementation_commit": FROZEN_IMPLEMENTATION,
                "evaluation_commit": eval_commit,
            }
            binding_sha = pc.sha(binding)

            row = {
                "slot_id": sid,
                "cell_id": slot["cell_id"],
                "case_id": slot["case_id"],
                "phase": phase,
                "block": slot["block"],
                "warmup": slot["warmup"],
                "backend": slot["backend"],
                "protocol_sha256": pc.sha(spec),
                "run_id": run_id,
                "implementation_commit": FROZEN_IMPLEMENTATION,
                "evaluation_commit": eval_commit,
                "execution_binding_sha256": binding_sha,
                "issued": True,
                "status": result["status"],
                "prepared_call_s": result.get("prepared_call_s"),
                "job_to_state_cached_path_s": result.get("job_to_state_cached_path_s"),
                "finite": result.get("finite", False),
                "same_policy_passed": result.get("same_policy_passed", False),
                "accuracy_qualified": result.get("accuracy_qualified", False),
                "reason": result.get("reason"),
            }
            rows.append(row)

            if result["status"] not in ("success", "unsupported"):
                raise RuntimeError(f"Slot {sid} execution failed with status '{result['status']}': {result.get('error')}")

            if i % 50 == 0 or i == len(slots):
                print(f"[run-block] [{i}/{len(slots)}] sid={sid} status={result['status']} call_s={result.get('prepared_call_s')}")

        write_atomic_json(block_rows_file, rows)
        write_new_json(block_done_file, {"block": block, "completed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        print(f"[run-block] Block {block} complete. Written {len(rows)} rows to {block_rows_file}.")
        return rows
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


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

    def run_ssh(cmd_args: list[str], check: bool = True) -> subprocess.CompletedProcess:
        if is_remote:
            ssh_cmd = ["ssh"]
            key_path = Path.home() / ".ssh/id_ed25519_upmem_eth"
            if key_path.exists():
                ssh_cmd += ["-i", str(key_path)]
            target = f"{ssh_user}@{ssh_host}" if ssh_user else ssh_host
            quoted = " ".join(shlex.quote(str(arg)) for arg in cmd_args)
            full_cmd = ssh_cmd + [target, quoted]
            print(f"[all->ssh] {quoted}")
            return subprocess.run(full_cmd, check=check, text=True)
        else:
            print(f"[all->local] {' '.join(shlex.quote(str(arg)) for arg in cmd_args)}")
            return subprocess.run(cmd_args, check=check, text=True)

    def rsync_to_remote(src: Path | str, dst_rel: str) -> None:
        if is_remote:
            key_path = Path.home() / ".ssh/id_ed25519_upmem_eth"
            ssh_opt = f"ssh -i {key_path}" if key_path.exists() else "ssh"
            target = f"{ssh_user}@{ssh_host}" if ssh_user else ssh_host
            remote_dst = f"{target}:{rem_work}/{dst_rel}"
            cmd = ["rsync", "-avz", "-e", ssh_opt, str(src), remote_dst]
            subprocess.run(cmd, check=True)

    def rsync_from_remote(src_rel: str, dst: Path | str) -> None:
        if is_remote:
            dst_p = Path(dst)
            if src_rel.endswith("/"):
                dst_p.mkdir(parents=True, exist_ok=True)
            else:
                dst_p.parent.mkdir(parents=True, exist_ok=True)
            key_path = Path.home() / ".ssh/id_ed25519_upmem_eth"
            ssh_opt = f"ssh -i {key_path}" if key_path.exists() else "ssh"
            target = f"{ssh_user}@{ssh_host}" if ssh_user else ssh_host
            remote_src = f"{target}:{rem_work}/{src_rel}"
            cmd = ["rsync", "-avz", "-e", ssh_opt, remote_src, str(dst)]
            subprocess.run(cmd, check=True)

    print(f"[all] Starting unified v4 campaign: run_id={run_id}, eval_commit={evaluation_commit}")

    rem_work = Path(mach["remote_evidence_parent"]) / run_id
    loc_work = receipt_root / run_id
    archive_A = Path(mach["local_archive_A"]) / run_id
    archive_B = Path(mach["local_archive_B"]) / run_id

    loc_work.mkdir(parents=True, exist_ok=True)
    archive_A.mkdir(parents=True, exist_ok=True)
    archive_B.mkdir(parents=True, exist_ok=True)

    for p in ("cases", "references", "receipts/calibration", "receipts/final", "paths", "qualification"):
        (loc_work / p).mkdir(parents=True, exist_ok=True)

    if is_remote:
        run_ssh(["mkdir", "-p",
                 f"{rem_work}/cases", f"{rem_work}/references",
                 f"{rem_work}/receipts/calibration", f"{rem_work}/receipts/final",
                 f"{rem_work}/paths", f"{rem_work}/qualification"])
        lock_file = Path(mach["remote_lock"])
        run_ssh(["mkdir", "-p", str(lock_file.parent)])
        run_ssh(["touch", str(lock_file)])

    # 1. Compile static manifest
    static_manifest_dir = loc_work / "static"
    if not (static_manifest_dir / "manifest.json").exists():
        manifest = pc.compile_manifest(spec)
        pc.write_manifest(static_manifest_dir, manifest)
    else:
        manifest = read_json(static_manifest_dir / "manifest.json")
    pc.check_seal(manifest)

    if is_remote:
        rsync_to_remote(static_manifest_dir, "")

    # 2. Preparation: QASM
    print("[all] Stage 1: Preparing QASM...")
    loc_cases_dir = loc_work / "cases"
    loc_cases_dir.mkdir(parents=True, exist_ok=True)
    for c in manifest["cases"]:
        qasm_path = loc_cases_dir / f"{c['case_id']}.qasm"
        if not qasm_path.exists():
            qasm_bytes = qasm_for_case(HERE.parents[1], c)
            qasm_path.write_bytes(qasm_bytes)

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
        qasm_path = loc_cases_dir / f"{q['case_id']}.qasm"
        if not qasm_path.exists():
            qasm_bytes = qasm_for_case(HERE.parents[1], q)
            qasm_path.write_bytes(qasm_bytes)

    if is_remote:
        rsync_to_remote(f"{loc_cases_dir}/", "cases/")

    # 3. Stage 0: Qualification
    qual_done_file = loc_work / "qualification/qualification.done"
    if not qual_done_file.exists():
        print("[all] Stage 0: Running qualification gates...")
        (loc_work / "qualification").mkdir(parents=True, exist_ok=True)
        if is_remote:
            ssh_cmd = [
                mach["remote_python"],
                str(Path(mach["remote_evaluator"]) / "evaluation/unified_v4/runner.py"),
                "qualify",
                "--work", str(rem_work),
                "--source", str(mach["remote_implementation"]),
                "--build", str(mach["remote_build_root"]),
                "--lock", str(mach["remote_lock"]),
            ]
            run_ssh(ssh_cmd, check=True)
            rsync_from_remote("qualification/", loc_work / "qualification/")
            rsync_from_remote("references/", loc_work / "references/")
        else:
            qualify_cmd(
                work=loc_work,
                source=HERE.parents[1],
                build=Path(mach["remote_build_root"]),
                lock=Path(mach["remote_lock"]),
            )
        require(qual_done_file.exists(), "qualification.done was not produced")
        shutil.copytree(loc_work / "qualification", archive_A / "qualification", dirs_exist_ok=True)
        shutil.copytree(loc_work / "qualification", archive_B / "qualification", dirs_exist_ok=True)
        print("[all] Stage 0: Qualification PASSED and retained in Archive A & B.")
    else:
        print("[all] Stage 0: Qualification already completed. Skipping.")

    # Generate benchmark Stress references if not present
    loc_ref_dir = loc_work / "references"
    loc_ref_dir.mkdir(parents=True, exist_ok=True)
    stress_cases = [c for c in manifest["cases"] if c["family"] == "stress"]
    stress_missing = [c for c in stress_cases if not (loc_ref_dir / f"{c['case_id']}.npy").exists()]
    if stress_missing:
        print(f"[all] Generating QuEST-P2 references for {len(stress_missing)} stress benchmark cases...")
        if is_remote:
            gen_script = f"""
import sys
from pathlib import Path
sys.path.insert(0, '{mach["remote_evaluator"]}/evaluation/unified_v4')
import runner
source = Path('{mach["remote_implementation"]}')
build = Path('{mach["remote_build_root"]}')
work = Path('{rem_work}')
p2_lib = build / 'quest-p2/lib/libquest_bridge.so'
(work / 'references').mkdir(parents=True, exist_ok=True)
manifest = runner.read_json(work / 'static/manifest.json')
for c in manifest['cases']:
    if c['family'] == 'stress':
        ref_p = work / f"references/{{c['case_id']}}.npy"
        if not ref_p.exists():
            runner.quest_in_subprocess(source, work / f"cases/{{c['case_id']}}.qasm", int(c['n']), p2_lib, 1, output_npy=ref_p)
            print('Generated reference for', c['case_id'])
"""
            run_ssh([mach["remote_python"], "-c", gen_script], check=True)
            rsync_from_remote("references/", loc_work / "references/")
        else:
            p2_lib = Path(mach["remote_build_root"]) / "quest-p2/lib/libquest_bridge.so"
            for c in stress_missing:
                quest_in_subprocess(HERE.parents[1], loc_cases_dir / f"{c['case_id']}.qasm", int(c["n"]), p2_lib, 1, output_npy=loc_ref_dir / f"{c['case_id']}.npy")
        for c in stress_cases:
            shutil.copy2(loc_ref_dir / f"{c['case_id']}.npy", archive_A / f"{c['case_id']}.npy")
            shutil.copy2(loc_ref_dir / f"{c['case_id']}.npy", archive_B / f"{c['case_id']}.npy")

    # 4. Calibration Phase C
    print("[all] Stage 2: Calibration Phase (2,674 slots in 8 blocks)...")
    cal_slots = manifest["calibration_slots"]
    cal_cells = {c["cell_id"]: c for c in manifest["calibration_cells"]}

    verified_rows_path = loc_work / "calibration_rows.json"
    rows_by_slot = {}
    if verified_rows_path.exists():
        rows_by_slot = {r["slot_id"]: r for r in read_json(verified_rows_path)}

    blocks = sorted({s["block"] for s in cal_slots})
    for b in blocks:
        block_checkpoint = loc_work / f"cal_block_{b}.done"
        if block_checkpoint.exists():
            print(f"[all] Calibration Block {b} already completed. Skipping.")
            continue

        block_slots = [s for s in cal_slots if s["block"] == b]
        print(f"[all] Executing Calibration Block {b} ({len(block_slots)} slots)...")
        if is_remote:
            ssh_cmd = [
                mach["remote_python"],
                str(Path(mach["remote_evaluator"]) / "evaluation/unified_v4/runner.py"),
                "run-block",
                "--phase", "calibration",
                "--block", str(b),
                "--work", str(rem_work),
                "--source", str(mach["remote_implementation"]),
                "--build", str(mach["remote_build_root"]),
                "--manifest", str(rem_work / "static/manifest.json"),
                "--lock", str(mach["remote_lock"]),
                "--eval-commit", evaluation_commit,
                "--run-id", run_id,
            ]
            run_ssh(ssh_cmd, check=True)
            rsync_from_remote("receipts/calibration/", loc_work / "receipts/calibration/")
            rsync_from_remote(f"calibration_rows_block_{b}.json", loc_work / f"calibration_rows_block_{b}.json")
            b_rows = read_json(loc_work / f"calibration_rows_block_{b}.json")
        else:
            b_rows = run_block_cmd(
                phase="calibration",
                block=b,
                work=loc_work,
                source=HERE.parents[1],
                build=Path(mach["remote_build_root"]),
                manifest_path=static_manifest_dir / "manifest.json",
                lock=Path(mach["remote_lock"]),
                eval_commit=evaluation_commit,
                run_id=run_id,
            )

        # Verification of block receipts
        for s in block_slots:
            sid = s["slot_id"]
            issued_p = loc_work / f"receipts/calibration/{sid}.issued.json"
            rec_p = loc_work / f"receipts/calibration/{sid}.json"
            require(issued_p.exists(), f"missing issued record {issued_p}")
            require(rec_p.exists(), f"missing receipt record {rec_p}")

        for r in b_rows:
            rows_by_slot[r["slot_id"]] = r

        write_atomic_json(verified_rows_path, list(rows_by_slot.values()))
        write_new_json(block_checkpoint, {"block": b, "completed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        shutil.copy2(verified_rows_path, archive_A / "calibration_rows.json")
        shutil.copy2(verified_rows_path, archive_B / "calibration_rows.json")
        shutil.copytree(loc_work / "receipts/calibration", archive_A / "receipts/calibration", dirs_exist_ok=True)
        shutil.copytree(loc_work / "receipts/calibration", archive_B / "receipts/calibration", dirs_exist_ok=True)
        print(f"[all] Calibration Block {b} verified and checkpointed to Archive A and B ({len(rows_by_slot)} total rows).")

    # 5. Topology Selection
    print("[all] Stage 3: Topology Selection from verified calibration rows...")
    selection_path = loc_work / "selection.json"
    if not selection_path.exists():
        rows_list = list(rows_by_slot.values())
        selection = pc.select_topologies(spec, manifest, rows_list)
        write_new_json(selection_path, selection)
        shutil.copy2(selection_path, archive_A / "selection.json")
        shutil.copy2(selection_path, archive_B / "selection.json")
        if is_remote:
            rsync_to_remote(selection_path, "selection.json")
    else:
        selection = read_json(selection_path)
    pc.check_seal(selection)
    print(f"[all] Selected {len(selection['selections'])} family/policy winners. Selection seal: {selection['content_sha256']}")

    # 6. R Path Generation
    print("[all] Stage 4: R Path Generation for all 52 final cases...")
    path_records_path = loc_work / "path_records.json"
    if not path_records_path.exists():
        if is_remote:
            ssh_cmd = [
                mach["remote_python"],
                str(Path(mach["remote_evaluator"]) / "evaluation/unified_v4/runner.py"),
                "generate-r-paths",
                "--work", str(rem_work),
                "--source", str(mach["remote_implementation"]),
                "--manifest", str(rem_work / "static/manifest.json"),
                "--selection", str(rem_work / "selection.json"),
                "--out", str(rem_work / "paths"),
            ]
            run_ssh(ssh_cmd, check=True)
            rsync_from_remote("paths/", loc_work / "paths/")
            rsync_from_remote("path_records.json", loc_work / "path_records.json")
            path_records = read_json(path_records_path)
        else:
            path_records = generate_r_paths_cmd(
                work=loc_work,
                source=HERE.parents[1],
                manifest_path=static_manifest_dir / "manifest.json",
                selection_path=selection_path,
                out_dir=loc_work / "paths",
            )
        shutil.copy2(path_records_path, archive_A / "path_records.json")
        shutil.copy2(path_records_path, archive_B / "path_records.json")
    else:
        path_records = read_json(path_records_path)

    # Bind final manifest
    final_manifest_path = loc_work / "final_manifest.json"
    if not final_manifest_path.exists():
        final_manifest = pc.materialize_final(spec, manifest, selection, path_records)
        write_new_json(final_manifest_path, final_manifest)
        shutil.copy2(final_manifest_path, archive_A / "final_manifest.json")
        shutil.copy2(final_manifest_path, archive_B / "final_manifest.json")
        if is_remote:
            rsync_to_remote(final_manifest_path, "final_manifest.json")
    else:
        final_manifest = read_json(final_manifest_path)
    pc.check_seal(final_manifest)
    print(f"[all] Materialized final manifest: {len(final_manifest['cells'])} cells, {len(final_manifest['slots'])} slots.")

    # 7. Final Comparison Phase (W and S)
    print("[all] Stage 5: Final Comparison Phase (1,560 slots in 6 blocks)...")
    final_slots = final_manifest["slots"]
    final_cells = {c["cell_id"]: c for c in final_manifest["cells"]}
    final_rows_path = loc_work / "final_rows.json"
    final_rows_by_slot = {}
    if final_rows_path.exists():
        final_rows_by_slot = {r["slot_id"]: r for r in read_json(final_rows_path)}

    fblocks = sorted({s["block"] for s in final_slots})
    for b in fblocks:
        b_checkpoint = loc_work / f"final_block_{b}.done"
        if b_checkpoint.exists():
            print(f"[all] Final Block {b} already completed. Skipping.")
            continue

        b_slots = [s for s in final_slots if s["block"] == b]
        print(f"[all] Executing Final Block {b} ({len(b_slots)} slots)...")
        if is_remote:
            ssh_cmd = [
                mach["remote_python"],
                str(Path(mach["remote_evaluator"]) / "evaluation/unified_v4/runner.py"),
                "run-block",
                "--phase", "final",
                "--block", str(b),
                "--work", str(rem_work),
                "--source", str(mach["remote_implementation"]),
                "--build", str(mach["remote_build_root"]),
                "--manifest", str(rem_work / "final_manifest.json"),
                "--paths", str(rem_work / "path_records.json"),
                "--lock", str(mach["remote_lock"]),
                "--eval-commit", evaluation_commit,
                "--run-id", run_id,
            ]
            run_ssh(ssh_cmd, check=True)
            rsync_from_remote("receipts/final/", loc_work / "receipts/final/")
            rsync_from_remote(f"final_rows_block_{b}.json", loc_work / f"final_rows_block_{b}.json")
            b_rows = read_json(loc_work / f"final_rows_block_{b}.json")
        else:
            b_rows = run_block_cmd(
                phase="final",
                block=b,
                work=loc_work,
                source=HERE.parents[1],
                build=Path(mach["remote_build_root"]),
                manifest_path=final_manifest_path,
                lock=Path(mach["remote_lock"]),
                eval_commit=evaluation_commit,
                run_id=run_id,
                paths_path=path_records_path,
            )

        for s in b_slots:
            sid = s["slot_id"]
            c = final_cells[s["cell_id"]]
            if c.get("eligible_for_runtime_admission", True):
                issued_p = loc_work / f"receipts/final/{sid}.issued.json"
                rec_p = loc_work / f"receipts/final/{sid}.json"
                require(issued_p.exists(), f"missing issued record {issued_p}")
                require(rec_p.exists(), f"missing receipt record {rec_p}")

        for r in b_rows:
            final_rows_by_slot[r["slot_id"]] = r

        write_atomic_json(final_rows_path, list(final_rows_by_slot.values()))
        write_new_json(b_checkpoint, {"block": b, "completed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        shutil.copy2(final_rows_path, archive_A / "final_rows.json")
        shutil.copy2(final_rows_path, archive_B / "final_rows.json")
        shutil.copytree(loc_work / "receipts/final", archive_A / "receipts/final", dirs_exist_ok=True)
        shutil.copytree(loc_work / "receipts/final", archive_B / "receipts/final", dirs_exist_ok=True)
        print(f"[all] Final Block {b} verified and checkpointed to Archive A and B ({len(final_rows_by_slot)} total rows).")

    # 8. Final Readout Generation
    print("[all] Stage 6: Running readout...")
    readout_dir = loc_work / "readout"
    if not readout_dir.exists():
        subprocess.run([sys.executable, str(HERE / "readout.py"), "--campaign", str(loc_work), "--output", str(readout_dir)], check=True)
        shutil.copytree(readout_dir, archive_A / "readout", dirs_exist_ok=True)
        shutil.copytree(readout_dir, archive_B / "readout", dirs_exist_ok=True)
    print("[all] Stage 6: Readout complete and copied to Archive A & B.")

    # 9. Dual-archive Equality Verification
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

    # qualify
    p_qua = sub.add_parser("qualify")
    p_qua.add_argument("--work", type=Path, required=True)
    p_qua.add_argument("--source", type=Path, required=True)
    p_qua.add_argument("--build", type=Path, required=True)
    p_qua.add_argument("--lock", type=Path, required=True)
    p_qua.add_argument("--spec", type=Path)

    # generate-r-paths
    p_gen = sub.add_parser("generate-r-paths")
    p_gen.add_argument("--work", type=Path, required=True)
    p_gen.add_argument("--source", type=Path, required=True)
    p_gen.add_argument("--manifest", type=Path, required=True)
    p_gen.add_argument("--selection", type=Path, required=True)
    p_gen.add_argument("--out", type=Path, required=True)
    p_gen.add_argument("--spec", type=Path)

    # run-block
    p_blk = sub.add_parser("run-block")
    p_blk.add_argument("--phase", required=True, choices=["calibration", "final"])
    p_blk.add_argument("--block", type=int, required=True)
    p_blk.add_argument("--work", type=Path, required=True)
    p_blk.add_argument("--source", type=Path, required=True)
    p_blk.add_argument("--build", type=Path, required=True)
    p_blk.add_argument("--manifest", type=Path, required=True)
    p_blk.add_argument("--lock", type=Path, required=True)
    p_blk.add_argument("--eval-commit", type=str, required=True)
    p_blk.add_argument("--run-id", type=str, required=True)
    p_blk.add_argument("--paths", type=Path)
    p_blk.add_argument("--spec", type=Path)
    p_blk.add_argument("--simulator", action="store_true")

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
    elif args.command == "qualify":
        qualify_cmd(
            work=args.work,
            source=args.source,
            build=args.build,
            lock=args.lock,
            spec_path=args.spec,
        )
    elif args.command == "generate-r-paths":
        generate_r_paths_cmd(
            work=args.work,
            source=args.source,
            manifest_path=args.manifest,
            selection_path=args.selection,
            out_dir=args.out,
            spec_path=args.spec,
        )
    elif args.command == "run-block":
        run_block_cmd(
            phase=args.phase,
            block=args.block,
            work=args.work,
            source=args.source,
            build=args.build,
            manifest_path=args.manifest,
            lock=args.lock,
            eval_commit=args.eval_commit,
            run_id=args.run_id,
            paths_path=args.paths,
            spec_path=args.spec,
            simulator=args.simulator,
        )


if __name__ == "__main__":
    main()
