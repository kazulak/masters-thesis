#!/usr/bin/env python3
"""Finite evaluation harness. Research implementation is imported read-only at FROZEN.

Commands never refit P6. Outputs live outside the measured source checkout.
The companion protocol defines the estimands and which comparisons are admissible.
"""
from __future__ import annotations
import argparse
from collections import Counter
from collections.abc import Mapping
import contextlib
import csv
import ctypes
import dataclasses
import fcntl
import hashlib
import importlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import resource
import re
import signal
import shutil
import traceback
import socket
import subprocess
import sys
import tarfile
import time

FROZEN = "f6b570a98a610d41b5b16401a42ce12a94042d38"
PACKAGE = Path(__file__).resolve().parents[1]
F32 = "split_complex_float32_v1"
I8 = "complex_int8_shared_scale_v1"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def read(path):
    return json.loads(Path(path).read_text())


def safe_json(value):
    if dataclasses.is_dataclass(value):
        return {f.name: safe_json(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, Mapping):
        return {str(k): safe_json(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [safe_json(v) for v in value]
    if hasattr(value, "item") and getattr(value, "ndim", None) == 0:
        return value.item()
    if isinstance(value, Path):
        return str(value)
    return value


def canonical(value):
    return json.dumps(safe_json(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as f:
        f.write(canonical(value) + b"\n")
        f.flush()
        os.fsync(f.fileno())


def git(source, *args):
    return subprocess.check_output(["git", "-C", str(source), *args], text=True).strip()


def check_source(source):
    require(git(source, "rev-parse", "HEAD") == FROZEN, "wrong research source commit")
    require(not git(source, "status", "--porcelain"), "research checkout is dirty")
    require(git(source, "rev-parse", "--is-shallow-repository") == "false", "full history required")


def imports(source):
    root = Path(source) / "thesis/implementation"
    sys.path.insert(0, str(root / "src"))
    sys.path.insert(0, str(root / "scripts"))
    return root


def case_id(family, n, layers=1):
    return f"{family}_n{n:02d}" + (f"_l{layers}" if family == "stress" else "")


def cases(spec):
    out = []
    for family in spec["primary_families"]:
        for width in spec["width_slots"]:
            n = width - 1 if family == "edc" else width
            out.append(
                dict(
                    case_id=case_id(family, n, 1),
                    family=family,
                    n=n,
                    layers=1,
                    width_slot=width,
                    role="width",
                )
            )
    out.append(
        dict(
            case_id="stress_n16_l2",
            family="stress",
            n=16,
            layers=2,
            width_slot=16,
            role="ablation_resource",
        )
    )
    return sorted(out, key=lambda c: c["case_id"])


def dpu_grid(capacity, spec):
    require(4 <= capacity <= 64, "requires one rank with 4..64 available DPUs")
    return sorted({d for d in spec["dpu_grid"] if d <= capacity} | {capacity})


def up(d=4, t=8, schedule="static_dag_waves_v1", fuse=True, policy=F32):
    return dict(
        backend="upmem",
        dpus=d,
        tasklets=t,
        schedule=schedule,
        fuse=fuse,
        policy=policy,
        geometry="panel_only_v1",
        threads=1,
    )


def arm_id(arm):
    if arm["backend"] != "upmem":
        return f"{arm['backend']}_p{arm['threads']}"
    return (
        f"upmem_d{arm['dpus']}_t{arm['tasklets']}_"
        f"{arm['schedule']}_{int(arm['fuse'])}_{'i8' if arm['policy'] == I8 else 'f32'}"
    )


def suite_definitions(spec, capacity, cpu_cores):
    ds = dpu_grid(capacity, spec)
    all_cases = cases(spec)
    by_id = {c["case_id"]: c for c in all_cases}

    # Suite T: HS18 and Stress16/L2, D1, T1..24, serial, unfused
    t_cases = ["hs_n18", "stress_n16_l2"]
    t_arms = [up(1, t, "serial_nodes_v1", False) for t in spec["tasklets"]]
    t_entries = [dict(case_id=c, arm_id=arm_id(a), arm=a) for c in t_cases for a in t_arms]

    # Suite D: HS18 and Stress16/L2, D in ds, T8 and T24, final route
    d_cases = ["hs_n18", "stress_n16_l2"]
    d_arms = [up(d, t) for d in ds for t in (8, 24)]
    d_entries = [dict(case_id=c, arm_id=arm_id(a), arm=a) for c in d_cases for a in d_arms]

    # Suite A: EDC17, HS18, Stress16/L2, A0..A4
    a_cases = ["edc_n17", "hs_n18", "stress_n16_l2"]
    a_arms = [
        up(1, 1, "serial_nodes_v1", False),
        up(1, 8, "serial_nodes_v1", False),
        up(4, 8, "serial_nodes_v1", False),
        up(4, 8, "serial_nodes_v1", True),
        up(4, 8),
    ]
    a_entries = [dict(case_id=c, arm_id=arm_id(a), arm=a) for c in a_cases for a in a_arms]

    # Suite W: 48 width cases
    w_cases = [c for c in all_cases if c["role"] == "width"]
    w_entries = []
    for c in w_cases:
        cid = c["case_id"]
        # UPMEM max
        u_max = up(capacity, 24)
        w_entries.append(dict(case_id=cid, arm_id=arm_id(u_max), arm=u_max))
        # QuEST multicore
        q_multi = dict(backend="quest32", threads=cpu_cores)
        w_entries.append(dict(case_id=cid, arm_id=arm_id(q_multi), arm=q_multi))
        # Explanatory CPU controls on anchor widths 8, 12, 16, 18
        if c["width_slot"] in spec["anchor_widths"]:
            if cpu_cores != 1:
                q_one = dict(backend="quest32", threads=1)
                w_entries.append(dict(case_id=cid, arm_id=arm_id(q_one), arm=q_one))
            np_arm = dict(backend="numpy", threads=1)
            w_entries.append(dict(case_id=cid, arm_id=arm_id(np_arm), arm=np_arm))

    defs = {
        "T": dict(entries=t_entries, warmups=spec["warmups"], measurements=spec["resource_measurements"]),
        "D": dict(entries=d_entries, warmups=spec["warmups"], measurements=spec["resource_measurements"]),
        "A": dict(entries=a_entries, warmups=spec["warmups"], measurements=spec["ablation_measurements"]),
        "W": dict(entries=w_entries, warmups=spec["warmups"], measurements=spec["resource_measurements"]),
    }
    for suite, d in defs.items():
        require(all(e["case_id"] in by_id for e in d["entries"]), "case definition missing")
    return by_id, defs


def order_entries(entries, seed, suite, block):
    return sorted(
        entries,
        key=lambda e: hashlib.sha256(
            f"{seed}|{suite}|{block}|{e['case_id']}|{e['arm_id']}".encode()
        ).hexdigest(),
    )


def counts(defs):
    all_count = physical = 0
    for d in defs.values():
        reps = d["warmups"] + d["measurements"]
        all_count += len(d["entries"]) * reps
        physical += sum(e["arm"]["backend"] == "upmem" for e in d["entries"]) * reps
    return dict(measurement_and_warmup_attempts=all_count, physical_attempts=physical)


def cpu_selection():
    permitted = set(os.sched_getaffinity(0))
    data = json.loads(subprocess.check_output(["lscpu", "-J", "-e=CPU,CORE,SOCKET,NODE,ONLINE"], text=True))
    rows = []
    for r in data["cpus"]:
        online = str(r.get("online", "yes")).lower() in ("yes", "true", "1")
        if online and int(r["cpu"]) in permitted:
            rows.append(
                {
                    k: (int(r[k]) if str(r[k]) not in ("-", "", "None") else 0)
                    for k in ("cpu", "core", "socket", "node")
                }
            )
    require(rows, "no permitted CPUs")
    first = min(rows, key=lambda r: r["cpu"])
    chosen = {}
    for r in sorted(rows, key=lambda r: r["cpu"]):
        if r["socket"] == first["socket"] and r["node"] == first["node"]:
            chosen.setdefault(r["core"], r["cpu"])
    return sorted(chosen.values()), first["node"]


def rank_free():
    entries = sorted(Path("/sys/class/dpu_rank").glob("dpu_rank*"))
    require(entries, "UPMEM rank sysfs unavailable")
    snapshot = {p.name: (p / "is_owned").read_text().strip() for p in entries}
    require(
        "dpu_rank1" in snapshot and all(v == "0" for v in snapshot.values()),
        "UPMEM ranks occupied; do not disturb any user",
    )
    return snapshot


def governors(cpus):
    out = {}
    for cpu in cpus:
        p = Path(f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor")
        out[str(cpu)] = p.read_text().strip() if p.exists() else "unavailable"
    return out


def host_checks(spec, cpus=None):
    require(socket.gethostname().split(".")[0].startswith(spec["expected_host_prefix"]), "wrong host")
    sdk = subprocess.check_output(["dpu-pkg-config", "--modversion", "dpu"], text=True).strip()
    require(sdk == spec["sdk_version"], "wrong SDK; do not upgrade silently")
    require(sys.version_info[:2] == (3, 10), "use Python 3.10")
    mem = {line.split(":")[0]: line.split(":")[1].strip() for line in Path("/proc/meminfo").read_text().splitlines()}
    require(
        int(mem["MemAvailable"].split()[0]) * 1024 >= spec["required_free_memory_bytes"],
        "insufficient available RAM for the declared campaign; no automatic smaller campaign",
    )
    if cpus:
        require(set(cpus) <= set(os.sched_getaffinity(0)), "frozen CPU allocation unavailable")
    return sdk


def package_hashes():
    result = {}
    for p in sorted(PACKAGE.rglob("*")):
        if p.is_file() and not any(s in ("__pycache__", ".pytest_cache") for s in p.parts):
            result[p.relative_to(PACKAGE).as_posix()] = digest(p)
    return result


def qasm_for(case):
    from upmem_family_workload import build_family_qasm
    from quantum_bench.circuits import builtin_circuit

    f, n = case["family"], case["n"]
    if f in ("bb84", "qrng"):
        return build_family_qasm(f, {"n_qubits": n})
    if f in ("bv", "xor"):
        return build_family_qasm(f, {"data_qubits": n - 1})
    if f == "edc":
        return build_family_qasm(f, {"data_qubits": (n + 1) // 2})
    if f == "hs":
        return build_family_qasm(f, {"allocated_qubits": n})
    c = builtin_circuit(
        "ghz_chain" if f == "ghz" else "quantization_stress",
        {"n_qubits": n} if f == "ghz" else {"n_qubits": n, "repeat_layers": case.get("layers", 1)},
    )
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";', f"qreg q[{n}];"]
    for o in c.operations:
        gate = o.gate + ("(" + ",".join(format(float(v), ".17g") for v in o.params) + ")" if o.params else "")
        lines.append(gate + " " + ",".join(f"q[{w}]" for w in o.wires) + ";")
    return ("\n".join(lines) + "\n").encode("ascii")


def load_case(source, work, case):
    imports(source)
    from quantum_bench.circuits import parse_openqasm2
    from quantum_bench.model import make_simulation_job

    path = Path(work) / "cases" / (case["case_id"] + ".qasm")
    circuit = parse_openqasm2(path)
    require(circuit.n_qubits == case["n"], "qubit count changed")
    require({o.gate for o in circuit.operations} <= {"h", "x", "ry", "rz", "cx"}, "unsupported bridge gate")
    return make_simulation_job(circuit=circuit)


def prepare_one(source, work, case):
    import numpy as np
    from quantum_bench.lowering import lower_tensor_network, build_contraction_dag, contraction_dag_hash
    from quantum_bench.planning import plan_opt_einsum

    job = load_case(source, work, case)
    started = time.perf_counter()
    network, inputs = lower_tensor_network(job)
    path, provenance = plan_opt_einsum(network, optimize="greedy")
    dag = build_contraction_dag(network, path)
    gate_depth = [0] * job.circuit.n_qubits
    gates = Counter()
    for op in job.circuit.operations:
        depth = 1 + max(gate_depth[w] for w in op.wires)
        for w in op.wires:
            gate_depth[w] = depth
        gates[op.gate] += 1
    outputs = [math.prod(node.output.shape) for node in dag.nodes]
    working_bound = 32 * sum(outputs) + sum(a.nbytes for a in inputs.values()) * 2 + 48 * (1 << case["n"]) + (1 << 30)
    if case.get("family") == "stress" and case.get("layers", 1) > 2:
        logical_plan_id = hashlib.sha256(canonical(path)).hexdigest()
    else:
        logical_plan_id = contraction_dag_hash(dag)
    return dict(
        case=case,
        qasm_sha256=digest(Path(work) / "cases" / (case["case_id"] + ".qasm")),
        path=path,
        path_id=hashlib.sha256(canonical(path)).hexdigest(),
        logical_plan_id=logical_plan_id,
        planner=provenance,
        gate_counts=dict(gates),
        gate_depth=max(gate_depth),
        tensor_count=len(network.tensors),
        node_count=len(dag.nodes),
        largest_intermediate_elements=max(outputs, default=1),
        sum_intermediate_elements=sum(outputs),
        working_bound_bytes=working_bound,
        full_state_c64_bytes=8 * (1 << case["n"]),
        full_state_c128_bytes=16 * (1 << case["n"]),
        preparation_observation_s=time.perf_counter() - started,
    )


def ndarray_hash(a):
    import numpy as np

    a = np.ascontiguousarray(a)
    h = hashlib.sha256()
    view = memoryview(a).cast("B")
    for start in range(0, len(view), 1024 * 1024):
        h.update(view[start : start + 1024 * 1024])
    return h.hexdigest()


def expected_chunk(case, start, end):
    import numpy as np

    family, n = case["family"], case["n"]
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
                valid &= digit == bit
        expected[valid] = sign[valid] * 2.0 ** (-hcount / 2)
    else:
        raise ValueError(f"unknown analytic family: {family}")
    return expected


def errors_analytic(output, case):
    import numpy as np

    n = case["n"]
    require(output.size == (1 << n), "wrong full output length")
    total = refnorm = norm = 0.0
    peak = refpeak = 0.0
    overlap = 0j
    finite = True
    elementwise = True
    for start in range(0, output.size, 1 << 18):
        end = min(start + (1 << 18), output.size)
        x = np.asarray(output[start:end], dtype=np.complex128)
        y = expected_chunk(case, start, end)
        if not (np.isfinite(x).all() and np.isfinite(y).all()):
            finite = False
            break
        diff = x - y
        elementwise = elementwise and bool(np.all(np.abs(diff) <= 1e-5 + 1e-5 * np.abs(y)))
        total += float(np.vdot(diff, diff).real)
        refnorm += float(np.vdot(y, y).real)
        norm += float(np.vdot(x, x).real)
        peak = max(peak, float(np.max(np.abs(diff), initial=0)))
        refpeak = max(refpeak, float(np.max(np.abs(y), initial=0)))
        overlap += np.vdot(y, x)
    if not finite or refnorm <= 0:
        return dict(finite=False, relative_l2=None, max_abs=None, norm_drift=None, reference_peak=None)
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


def errors(output, reference):
    import numpy as np

    require(output.size == reference.size, "wrong full output length")
    total = refnorm = norm = 0.0
    peak = refpeak = 0.0
    overlap = 0j
    finite = True
    elementwise = True
    for i in range(0, output.size, 1 << 18):
        x = np.asarray(output[i : i + (1 << 18)], dtype=np.complex128)
        y = np.asarray(reference[i : i + (1 << 18)], dtype=np.complex128)
        if not (np.isfinite(x).all() and np.isfinite(y).all()):
            finite = False
            break
        diff = x - y
        elementwise = elementwise and bool(np.all(np.abs(diff) <= 1e-5 + 1e-5 * np.abs(y)))
        total += float(np.vdot(diff, diff).real)
        refnorm += float(np.vdot(y, y).real)
        norm += float(np.vdot(x, x).real)
        peak = max(peak, float(np.max(np.abs(diff), initial=0)))
        refpeak = max(refpeak, float(np.max(np.abs(y), initial=0)))
        overlap += np.vdot(y, x)
    if not finite or refnorm <= 0:
        return dict(finite=False, relative_l2=None, max_abs=None, norm_drift=None, reference_peak=None)
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


def accuracy(err, spec):
    v = spec["validation"]
    return bool(
        err["finite"]
        and err.get("elementwise_allclose", False)
        and err["relative_l2"] <= v["fp32_relative_l2_max"]
        and err["norm_drift"] <= v["fp32_norm_drift_max"]
        and err["max_abs"] <= v["fp32_atol"] + v["fp32_rtol"] * err["reference_peak"]
    )


def quest_once(job, libfile, threads):
    import numpy as np

    lib = ctypes.CDLL(str(libfile))
    lib.eval_precision_bytes.restype = ctypes.c_int
    real_bytes = lib.eval_precision_bytes()
    require(real_bytes in (4, 8), "unsupported QuEST precision")
    fun = lib.eval_circuit
    ip = ctypes.POINTER(ctypes.c_int)
    dp = ctypes.POINTER(ctypes.c_double)
    fun.argtypes = [
        ctypes.c_int,
        ctypes.c_int,
        ip,
        ip,
        ip,
        dp,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_uint64,
        dp,
        ip,
    ]
    fun.restype = ctypes.c_int
    start = time.perf_counter()
    table = {"h": 0, "x": 1, "ry": 2, "rz": 3, "cx": 4}
    ops = list(job.circuit.operations)
    op = np.array([table[o.gate] for o in ops], dtype=np.int32)
    a = np.array([o.wires[0] for o in ops], dtype=np.int32)
    b = np.array([o.wires[1] if len(o.wires) == 2 else 0 for o in ops], dtype=np.int32)
    angle = np.array([o.params[0] if o.params else 0.0 for o in ops], dtype=np.float64)
    packing = time.perf_counter() - start
    start = time.perf_counter()
    output = np.empty(1 << job.circuit.n_qubits, dtype=np.complex64 if real_bytes == 4 else np.complex128)
    times = np.zeros(4, np.float64)
    deployment = np.zeros(3, np.int32)
    code = fun(
        job.circuit.n_qubits,
        len(ops),
        op.ctypes.data_as(ip),
        a.ctypes.data_as(ip),
        b.ctypes.data_as(ip),
        angle.ctypes.data_as(dp),
        threads,
        output.ctypes.data,
        output.nbytes,
        times.ctypes.data_as(dp),
        deployment.ctypes.data_as(ip),
    )
    wall = time.perf_counter() - start
    require(code == 0, f"QuEST bridge returned {code}")
    require(deployment[1] == 0 and deployment[2] == 0, "unexpected accelerated/distributed QuEST")
    return output, dict(
        prepared_call_s=wall,
        job_to_state_s=packing + wall,
        session_inclusive_s=float(sum(times)),
        native_open_s=float(times[0]),
        kernel_s=float(times[1]),
        native_output_copy_s=float(times[2]),
        native_close_s=float(times[3]),
        real_bytes=real_bytes,
        actual_multithreading=bool(deployment[0]),
        requested_threads=threads,
        bridge_sha256=digest(libfile),
    )


def tn_once(source, work, case, arm, spec, simulator=False):
    import numpy as np
    from quantum_bench.lowering import lower_tensor_network, build_contraction_dag, contraction_dag_hash
    from quantum_bench.planning import plan_opt_einsum
    from quantum_bench.cpu import run_cpu_once, replay_upmem_plan_once
    from quantum_bench.upmem.plan import UpmemTopology, UpmemResources, plan_upmem, physical_plan_id
    from quantum_bench.upmem.runtime import open_upmem, open_upmem_simulator

    job = load_case(source, work, case)
    frozen = read(Path(work) / "plans" / (case["case_id"] + ".json"))
    start = time.perf_counter()
    mark = start
    network, inputs = lower_tensor_network(job)
    lower_s = time.perf_counter() - mark
    mark = time.perf_counter()
    path, prov = plan_opt_einsum(network, optimize="greedy")
    search_s = time.perf_counter() - mark
    mark = time.perf_counter()
    dag = build_contraction_dag(network, path)
    dag_s = time.perf_counter() - mark
    details = {
        "lowering_s": lower_s,
        "planning_s": search_s,
        "dag_s": dag_s,
        "logical_plan_id": frozen["logical_plan_id"],
        "path_id": frozen["path_id"],
    }
    if arm["backend"] == "numpy":
        begin = time.perf_counter()
        sample = run_cpu_once(dag, inputs, F32)
        output = np.asarray(sample.output).ravel(order="F").copy()
        details["prepared_call_s"] = time.perf_counter() - begin
        details["job_to_state_s"] = time.perf_counter() - start
        require(canonical(path) == canonical(frozen["path"]), "greedy path drift")
        dag_id = (
            hashlib.sha256(canonical(path)).hexdigest()
            if (case.get("family") == "stress" and case.get("layers", 1) > 2)
            else contraction_dag_hash(dag)
        )
        require(dag_id == frozen["logical_plan_id"], "DAG identity drift")
        details["session_inclusive_s"] = sample.measurement.total_wall_s
        details["measurement"] = safe_json(sample.measurement)
        details["backend_facts"] = safe_json(sample.backend_facts)
        return output, details
    mark = time.perf_counter()
    plan = plan_upmem(
        dag,
        numeric_policy=arm["policy"],
        topology=UpmemTopology(dpu_count=arm["dpus"], tasklets_per_dpu=arm["tasklets"], rank_count=1),
        schedule_policy=arm["schedule"],
    )
    details["mapping_s"] = time.perf_counter() - mark
    details["physical_plan_id"] = physical_plan_id(plan)
    native = Path(source) / "thesis/implementation/native/upmem/runtime/bin"
    t = arm["tasklets"]
    resource_record = UpmemResources(
        session_root=str(Path(work) / "active-session"),
        host_binary=str(native / f"host_upmem_execution_plan_v4_t{t}"),
        dpu_binary=str(native / f"dpu_wave_v5_t{t}"),
        initialization_binary=str(native / f"dpu_simplepim_management_init_t{t}"),
        rank_paths=() if simulator else (spec["rank"],),
        request_transport="packed_wave_v1",
    )
    begin = time.perf_counter()
    mark = begin
    opener = open_upmem_simulator if simulator else open_upmem
    session = opener(
        dag,
        plan,
        resource_record,
        timeout_s=spec["attempt_timeout_s"],
        fuse_complex=arm["fuse"],
        geometry_policy=arm["geometry"],
        host_memory_budget_bytes=spec["executor_host_budget_bytes"],
        host_memory_reserve_bytes=0,
    )
    opening = time.perf_counter() - mark
    try:
        sample = session.run_once(inputs)
        output = np.asarray(sample.output).ravel(order="F").copy()
    finally:
        mark = time.perf_counter()
        terminal = session.close()
        closing = time.perf_counter() - mark
    details["prepared_call_s"] = time.perf_counter() - begin
    details["job_to_state_s"] = time.perf_counter() - start
    require(canonical(path) == canonical(frozen["path"]), "greedy path drift")
    dag_id = (
        hashlib.sha256(canonical(path)).hexdigest()
        if (case.get("family") == "stress" and case.get("layers", 1) > 2)
        else contraction_dag_hash(dag)
    )
    require(dag_id == frozen["logical_plan_id"], "DAG identity drift")
    details["session_inclusive_s"] = opening + sample.measurement.total_wall_s + closing
    details["session_open_s"] = opening
    details["session_close_s"] = closing
    details["measurement"] = safe_json(sample.measurement)
    details["backend_facts"] = safe_json(sample.backend_facts)
    details["numeric_facts"] = safe_json(sample.numeric_facts)
    details["terminal_facts"] = safe_json(terminal)
    require(sample.backend_facts.get("cpu_fallback_used") is False, "unexpected CPU fallback")
    require(terminal.get("native_identity_verified") is True, "native identity not verified")
    if not simulator:
        require(terminal.get("target_observed") == "physical_hardware", "not physical hardware")
    replay = replay_upmem_plan_once(dag, plan, inputs)
    if arm["policy"] == I8:
        require(
            sample.numeric_facts["raw_lane_records"] == replay.numeric_facts["raw_lane_records"],
            "integer raw-lane policy mismatch",
        )
        require(np.array_equal(output, np.asarray(replay.output).ravel(order="F")), "int8 replay mismatch")
        details["same_policy_passed"] = True
        float_control = run_cpu_once(dag, inputs, F32)
        details["error_vs_float32_same_dag"] = errors(output, np.asarray(float_control.output).ravel(order="F"))
    else:
        pe = errors(output, np.asarray(replay.output).ravel(order="F"))
        require(accuracy(pe, spec), "float32 physical-plan replay mismatch")
        details["same_policy_passed"] = True
    return output, details


def analytic_check(case, output):
    """Independent closed-form checks for structured families; no circuit simplifier is timed."""
    import numpy as np

    family = case["family"]
    if family == "stress":
        return False
    for start in range(0, output.size, 1 << 18):
        end = min(start + (1 << 18), output.size)
        expected = expected_chunk(case, start, end)
        np.testing.assert_allclose(output[start:end], expected, atol=1e-12, rtol=1e-12)
    return True


def worker(args):
    import numpy as np

    source, work = Path(args.source), Path(args.work)
    imports(source)
    spec = read(PACKAGE / "scope.json")
    resource.setrlimit(resource.RLIMIT_AS, (spec["child_address_space_bytes"], spec["child_address_space_bytes"]))
    case = read(args.case)
    result = {
        "schema": "thesis_final_evaluation_sample_v1",
        "source_commit": FROZEN,
        "case_id": case["case_id"],
        "mode": args.mode,
    }
    try:
        if args.mode == "admit":
            result = admit_one(source, work, case, spec)
        elif args.mode == "plan":
            result = prepare_one(source, work, case)
        elif args.mode == "reference":
            job = load_case(source, work, case)
            if case["family"] == "stress" or case["case_id"].startswith("qual_"):
                output, details = quest_once(job, Path(args.quest64), 1)
                require(output.dtype == np.complex128, "reference is not double precision")
                if case["n"] <= 12:
                    from quantum_bench.cpu import run_complex128_reference
                    from quantum_bench.lowering import lower_tensor_network, build_contraction_dag
                    from quantum_bench.planning import plan_opt_einsum

                    net, inputs = lower_tensor_network(job)
                    path, _ = plan_opt_einsum(net)
                    ref = run_complex128_reference(build_contraction_dag(net, path), inputs).ravel(order="F")
                    np.testing.assert_allclose(output, ref, atol=1e-12, rtol=1e-12)
                require(np.isfinite(output).all(), "nonfinite oracle")
                out = work / "references" / (case["case_id"] + ".npy")
                require(not out.exists(), "reference already exists")
                np.save(out, output, allow_pickle=False)
                result.update(
                    status="success",
                    reference_sha256=digest(out),
                    metrics=details,
                    analytic_reference_checked=False,
                    complex128_dag_checked=case["n"] <= 12,
                )
            else:
                details = {}
                if case["n"] <= 12:
                    output, details = quest_once(job, Path(args.quest64), 1)
                    require(output.dtype == np.complex128, "reference is not double precision")
                    analytic_check(case, output)
                result.update(
                    status="success",
                    analytic_reference_checked=True,
                    complex128_dag_checked=case["n"] <= 12,
                    metrics=details,
                )
        else:
            arm = read(args.arm)
            if arm["backend"] == "quest32":
                job = load_case(source, work, case)
                output, details = quest_once(job, Path(args.quest32), arm["threads"])
                require(output.dtype == np.complex64, "CPU performance route is not single precision")
            else:
                output, details = tn_once(source, work, case, arm, spec, args.mode == "simulator")
            ref_path = work / "references" / (case["case_id"] + ".npy")
            if ref_path.exists():
                ref = np.load(ref_path, mmap_mode="r", allow_pickle=False)
                err = errors(output, ref)
            else:
                err = errors_analytic(output, case)
            require(err["finite"], "nonfinite output")
            result.update(
                status="success",
                arm_id=arm_id(arm),
                arm=arm,
                metrics=details,
                validation=err,
                accuracy_qualified=accuracy(err, spec) if arm.get("policy") != I8 else None,
                full_output_amplitudes=int(output.size),
                output_sha256=ndarray_hash(output),
                rss_max_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            )
    except Exception as exc:
        traceback.print_exc()
        from quantum_bench.results import UnsupportedExecution

        timed = isinstance(exc, TimeoutError) or str(getattr(exc, "reason", "")) == "UPMEM operation deadline expired"
        result.update(
            status=(
                "unsupported"
                if isinstance(exc, UnsupportedExecution)
                else (
                    "timeout"
                    if timed
                    else ("memory_limit" if isinstance(exc, MemoryError) else "failure")
                )
            ),
            error_type=type(exc).__name__,
            error=str(exc),
            error_stage=getattr(exc, "stage", None),
            capability=getattr(exc, "capability", None),
        )
    write(args.output, result)
    if result.get("status") == "failure":
        raise SystemExit(1)


def call_worker(source, work, mode, casepath, out, arm=None, cpus=None, quest32=None, quest64=None):
    spec = read(PACKAGE / "scope.json")
    argv = [
        sys.executable,
        str(Path(__file__).resolve()),
        "worker",
        "--source",
        str(source),
        "--work",
        str(work),
        "--mode",
        mode,
        "--case",
        str(casepath),
        "--output",
        str(out),
    ]
    if arm:
        argv += ["--arm", str(arm)]
    if quest32:
        argv += ["--quest32", str(quest32)]
    if quest64:
        argv += ["--quest64", str(quest64)]
    cpus = cpus or [min(os.sched_getaffinity(0))]
    argv = ["taskset", "-c", ",".join(map(str, cpus)), *argv]
    env = dict(
        os.environ,
        OMP_NUM_THREADS=str(len(cpus)),
        OPENBLAS_NUM_THREADS=str(len(cpus)),
        MKL_NUM_THREADS=str(len(cpus)),
        BLIS_NUM_THREADS=str(len(cpus)),
        OMP_DYNAMIC="FALSE",
        OMP_PROC_BIND="TRUE",
        OMP_PLACES="cores",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONHASHSEED="0",
    )
    if mode == "physical":
        env["UPMEM_ALLOW_PHYSICAL_HARDWARE"] = "1"
    else:
        env.pop("UPMEM_ALLOW_PHYSICAL_HARDWARE", None)
    imports(source)
    bounded = importlib.import_module("upmem_cost_guided_execution")
    limit = spec["planning_timeout_s"] if mode in ("plan", "admit") else spec["worker_timeout_s"]
    with Path(str(out) + ".log").open("xb") as log:
        rc, timed, elapsed = bounded.run_bounded(argv, Path(source) / "thesis/implementation", env, log, limit)
    if not Path(out).exists():
        write(out, dict(status="timeout" if timed else "failure", returncode=rc, elapsed_worker_s=elapsed, mode=mode))
    result = read(out)
    if timed:
        result = {**result, "status": "timeout", "result_written_before_process_exit": True}
    write(
        str(out) + ".execution.json",
        dict(argv=argv, returncode=rc, timed_out=timed, elapsed_worker_s=elapsed, cpus=cpus, mode=mode),
    )
    result["worker_returncode"] = rc
    result["worker_elapsed_s"] = elapsed
    return result


def configure(args):
    source, work = Path(args.source).resolve(), Path(args.work).resolve()
    require(not work.exists(), "new work directory required; never overwrite a campaign")
    check_source(source)
    spec = read(PACKAGE / "scope.json")
    imports(source)
    require(re.fullmatch(r"[0-9a-f]{40}", args.evaluation_commit) is not None, "evaluation code commit required")
    subprocess.run(["git", "-C", str(source), "merge-base", "--is-ancestor", FROZEN, args.evaluation_commit], check=True)
    changed = git(source, "diff", "--name-only", FROZEN, args.evaluation_commit).splitlines()
    require(
        changed and all(p.startswith("evaluation/final_v1/") for p in changed),
        "evaluation code commit changed another surface",
    )
    code_paths = [
        p
        for p in package_hashes()
        if p in ("README.md", "scope.json", "historical_sources.json", "historical_results.csv")
        or p.startswith(("tools/", "native/", "tests/"))
    ]
    for rel in code_paths:
        data = subprocess.check_output(
            ["git", "-C", str(source), "show", f"{args.evaluation_commit}:evaluation/final_v1/{rel}"]
        )
        require(hashlib.sha256(data).hexdigest() == digest(PACKAGE / rel), f"uncommitted evaluation code: {rel}")
    host_checks(spec)
    require(shutil.disk_usage(work.parent).free >= spec["required_free_storage_bytes"], "insufficient evidence storage")
    cpus, node = cpu_selection()
    require(len(cpus) >= 1, "no CPU cores")
    inventory = read(args.inventory)
    require(
        inventory["rank_path"] == spec["rank"] and inventory["rank_count"] == 1 and inventory["released"],
        "invalid rank inventory",
    )
    by_id, defs = suite_definitions(spec, inventory["dpu_capacity"], len(cpus))
    require(
        counts(defs)["physical_attempts"] + 200 <= spec["physical_execution_ceiling"],
        "physical ceiling exceeded",
    )
    require(
        counts(defs)["measurement_and_warmup_attempts"] + 500 <= spec["all_attempts_ceiling"],
        "attempt ceiling exceeded",
    )
    work.mkdir(parents=True)
    for name in (
        "cases",
        "case_records",
        "plans",
        "references",
        "reference_records",
        "arms",
        "suites",
        "receipts",
        "admission",
    ):
        (work / name).mkdir()
    binding = dict(
        experiment_id="final-evaluation-v2-" + str(time.time_ns()),
        source=str(source),
        source_commit=FROZEN,
        evaluation_code_commit=args.evaluation_commit,
        source_tree=git(source, "rev-parse", "HEAD^{tree}"),
        specification=spec,
        capacity=inventory["dpu_capacity"],
        cpu_cpus=cpus,
        numa_node=node,
        governors=governors(cpus),
        host=socket.gethostname(),
        system=platform.uname()._asdict(),
        lscpu=json.loads(subprocess.check_output(["lscpu", "-J"], text=True)),
        initial_loadavg=Path("/proc/loadavg").read_text().strip(),
        packages=subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True).splitlines(),
        package_sha256=package_hashes(),
        quest32=str(Path(args.quest32).resolve()),
        quest64=str(Path(args.quest64).resolve()),
        quest32_sha256=digest(args.quest32),
        quest64_sha256=digest(args.quest64),
        counts=counts(defs),
        rank_inventory=inventory,
    )
    native = source / "thesis/implementation/native/upmem/runtime/bin"
    binding["native_binaries"] = {
        str(native / name): digest(native / name)
        for t in range(1, 25)
        for name in (
            f"host_upmem_execution_plan_v4_t{t}",
            f"dpu_wave_v5_t{t}",
            f"dpu_simplepim_management_init_t{t}",
        )
    }
    for cid, c in by_id.items():
        (work / "cases" / (cid + ".qasm")).write_bytes(qasm_for(c))
        write(work / "case_records" / (cid + ".json"), c)
    for name, d in defs.items():
        write(work / "suites" / (name + ".json"), d)
        for e in d["entries"]:
            ap = work / "arms" / (e["arm_id"] + ".json")
            if not ap.exists():
                write(ap, e["arm"])
    linked = {}
    for libpath in (args.quest32, args.quest64):
        buildroot = Path(libpath).resolve().parents[1]
        for lib in buildroot.rglob("*.so*"):
            if lib.is_file():
                linked[str(lib.resolve())] = digest(lib)
    require(linked, "QuEST shared-library bindings missing")
    binding["quest_shared_libraries"] = linked
    write(work / "binding.json", binding)


def prepare(args):
    source, work = Path(args.source).resolve(), Path(args.work).resolve()
    b = verify_binding(source, work)
    require(not (work / "prepared.json").exists(), "already prepared")
    by_id, defs = suite_definitions(b["specification"], b["capacity"], len(b["cpu_cpus"]))
    for cid, c in sorted(by_id.items()):
        cp = work / "case_records" / (cid + ".json")
        result = call_worker(source, work, "plan", cp, work / "plans" / (cid + ".json"), cpus=[b["cpu_cpus"][0]])
        require("path" in result, f"planner failed: {cid}")
        ref = work / "reference_records" / (cid + ".json")
        reference = call_worker(source, work, "reference", cp, ref, cpus=[b["cpu_cpus"][0]], quest64=b["quest64"])
        require(reference.get("status") != "failure", "reference failure: inspect retained receipt")
        admission = work / "admission" / (cid + ".json")
        if result.get("status") in ("timeout", "unsupported", "memory_limit"):
            write(admission, dict(status="unavailable", reason="plan_unavailable"))
        else:
            admitted = call_worker(source, work, "admit", cp, admission, cpus=[b["cpu_cpus"][0]])
            require(admitted.get("status") != "failure", "metadata admission failed")
    write(work / "prepared.json", dict(status="prepared", binding_sha256=digest(work / "binding.json")))


def admit_one(source, work, case, spec):
    from quantum_bench.lowering import lower_tensor_network, build_contraction_dag
    from quantum_bench.upmem.plan import UpmemTopology, plan_upmem
    from quantum_bench.upmem.runtime import _admit_prepared_snapshots
    from quantum_bench.upmem.execution_features import extract_execution_features
    from quantum_bench.upmem.tiling import canonical_label_geometry
    from quantum_bench.results import UnsupportedExecution

    frozen = read(work / "plans" / (case["case_id"] + ".json"))
    if frozen["working_bound_bytes"] > spec["planning_reference_work_bytes_limit"]:
        return dict(status="unavailable", reason="declared_reference_work_memory_limit")
    network, inputs = lower_tensor_network(load_case(source, work, case))
    dag = build_contraction_dag(network, frozen["path"])
    del inputs
    arms = {}
    for sp in sorted((work / "suites").glob("*.json")):
        for e in read(sp)["entries"]:
            if e["case_id"] == case["case_id"] and e["arm"]["backend"] == "upmem":
                arms[e["arm_id"]] = e["arm"]
    geometry = []
    for node in dag.nodes:
        if not hasattr(node, "left"):
            continue
        b, m, k, n = canonical_label_geometry(
            node.left.labels, node.left.shape, node.right.labels, node.right.shape, node.output_labels
        )
        geometry.append(
            dict(
                node_id=node.node_id,
                B=b,
                M=m,
                K=k,
                N=n,
                dependency_count=len({node.left.tensor_id, node.right.tensor_id} & {n.output.id for n in dag.nodes}),
                output_elements=b * m * n,
                real_macs=4 * b * m * k * n,
            )
        )
    records = {}
    for aid, a in sorted(arms.items()):
        try:
            plan = plan_upmem(
                dag,
                numeric_policy=a["policy"],
                topology=UpmemTopology(dpu_count=a["dpus"], tasklets_per_dpu=a["tasklets"], rank_count=1),
                schedule_policy=a["schedule"],
            )
            _admit_prepared_snapshots(
                dag,
                plan,
                fuse_complex=a["fuse"],
                geometry_policy=a["geometry"],
                host_memory_budget_bytes=spec["executor_host_budget_bytes"],
                host_memory_reserve_bytes=0,
            )
            facts = extract_execution_features(dag, plan, fuse_complex=a["fuse"], geometry_policy=a["geometry"])
            records[aid] = dict(
                status="admitted",
                plan=facts["plan"],
                totals=facts["totals"],
                static_memory=facts["static_memory"],
                host_buffers=facts["host_buffers"],
            )
        except UnsupportedExecution as exc:
            records[aid] = dict(status="unsupported", reason=str(exc), capability=getattr(exc, "capability", None))
    return dict(status="complete", geometry=geometry, arms=records)


def capsule_hashes(work):
    result = {}
    for dirname in ("cases", "case_records", "plans", "reference_records", "arms", "suites", "admission"):
        for p in sorted((Path(work) / dirname).glob("*")):
            if p.is_file() and not p.name.endswith(".log"):
                result[p.relative_to(work).as_posix()] = digest(p)
    for filename in ("binding.json", "prepared.json", "qualified.json"):
        result[filename] = digest(Path(work) / filename)
    return result


def seal(args):
    source, work = Path(args.source), Path(args.work)
    b = verify_binding(source, work)
    require(read(work / "prepared.json")["status"] == "prepared", "not prepared")
    qualified = read(work / "qualified.json")
    require(qualified["passed"] is True, "not qualified")
    for rel, h in qualified["receipt_sha256"].items():
        require(digest(work / rel) == h, "qualification receipt changed")
    for rp in (work / "reference_records").glob("*.json"):
        r = read(rp)
        if r.get("status") == "success" and "reference_sha256" in r:
            npy_file = work / "references" / (r["case_id"] + ".npy")
            if npy_file.exists():
                require(digest(npy_file) == r["reference_sha256"], "reference changed")
    write(
        work / "freeze.json",
        dict(
            schema="thesis_final_evaluation_freeze_v1",
            inputs=capsule_hashes(work),
            binding_sha256=digest(work / "binding.json"),
        ),
    )
    print(digest(work / "freeze.json"))


def verify_freeze(work):
    frozen = read(Path(work) / "freeze.json")
    require(capsule_hashes(work) == frozen["inputs"], "frozen evaluation inputs changed")
    return frozen


def run_suite(args):
    require(args.allow_physical, "--allow-physical is required")
    source, work = Path(args.source).resolve(), Path(args.work).resolve()
    b = verify_binding(source, work)
    spec = b["specification"]
    host_checks(spec, b["cpu_cpus"])
    verify_freeze(work)
    d = read(work / "suites" / (args.suite + ".json"))
    outdir = work / "receipts" / args.suite
    outdir.mkdir(parents=True, exist_ok=True)
    accounting = work / f"{args.suite}.accounting.json"
    require(not accounting.exists(), f"suite {args.suite} already accounted; no partial repair")
    start_time = time.perf_counter()
    attempts = timed_out = 0
    total_blocks = d["warmups"] + d["measurements"]
    for block in range(total_blocks):
        ordered = order_entries(d["entries"], spec["seed"], args.suite, block)
        for e in ordered:
            out = outdir / f"b{block:02d}__{e['case_id']}__{e['arm_id']}.json"
            if out.exists():
                continue
            case_path = work / "case_records" / (e["case_id"] + ".json")
            arm_path = work / "arms" / (e["arm_id"] + ".json")
            mode = "physical" if e["arm"]["backend"] == "upmem" else "cpu"
            lockpath = Path.home() / "evidence/upmem-experiment.lock"
            lockpath.parent.mkdir(parents=True, exist_ok=True)
            with lockpath.open("a") as lock:
                if mode == "physical":
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    rank_free()
                write(
                    str(out) + ".issued.json",
                    dict(
                        suite=args.suite,
                        block=block,
                        warmup=block < d["warmups"],
                        case_id=e["case_id"],
                        arm_id=e["arm_id"],
                        arm=e["arm"],
                    ),
                )
                r = call_worker(
                    source,
                    work,
                    mode,
                    case_path,
                    out,
                    arm=arm_path,
                    cpus=b["cpu_cpus"] if e["arm"].get("threads", 1) > 1 else [b["cpu_cpus"][0]],
                    quest32=b["quest32"],
                    quest64=b["quest64"],
                )
                if mode == "physical":
                    rank_free()
            attempts += 1
            if r.get("status") == "timeout":
                timed_out += 1
                for future in range(block + 1, total_blocks):
                    fout = outdir / f"b{future:02d}__{e['case_id']}__{e['arm_id']}.json"
                    write(
                        fout,
                        dict(
                            suite=args.suite,
                            block=future,
                            warmup=future < d["warmups"],
                            case_id=e["case_id"],
                            arm_id=e["arm_id"],
                            arm=e["arm"],
                            status="not_attempted",
                            reason="not_attempted_after_cell_timeout",
                        ),
                    )
            time.sleep(0.2)
    elapsed = time.perf_counter() - start_time
    write(
        accounting,
        dict(
            suite=args.suite,
            entries=len(d["entries"]),
            total_blocks=total_blocks,
            attempts_issued=attempts,
            timed_out=timed_out,
            suite_wall_s=elapsed,
            binding_sha256=digest(work / "binding.json"),
            completed_cleanly=True,
        ),
    )
    print(f"Suite {args.suite} finished in {elapsed:.1f}s ({attempts} attempts)")


def verify_binding(source, work):
    binding = read(Path(work) / "binding.json")
    check_source(source)
    require(binding["source_commit"] == FROZEN, "binding frozen commit mismatch")
    require(binding["source_tree"] == git(source, "rev-parse", "HEAD^{tree}"), "binding source tree mismatch")
    return binding


def archive(args):
    work = Path(args.work).resolve()
    part = Path(args.part)
    out = Path(args.output).resolve()
    require(not out.exists(), "archive destination already exists")
    target = (work / part).resolve()
    require(target.exists(), "part does not exist")
    out.parent.mkdir(parents=True, exist_ok=True)
    files_map = {}
    prefix = PurePosixPath(part.as_posix())
    with tarfile.open(out, "w:gz") as tar:
        if target.is_file():
            arcname = target.relative_to(work).as_posix()
            tar.add(target, arcname=arcname)
            rel = PurePosixPath(arcname).relative_to(prefix).as_posix() if str(prefix) != "." else arcname
            files_map[rel] = digest(target)
        else:
            for p in sorted(target.rglob("*")):
                if p.is_file() and not p.name.endswith(".log"):
                    arcname = p.relative_to(work).as_posix()
                    tar.add(p, arcname=arcname)
                    rel = PurePosixPath(arcname).relative_to(prefix).as_posix() if str(prefix) != "." else arcname
                    files_map[rel] = digest(p)
    write(str(out) + ".manifest.json", dict(archive_sha256=digest(out), relative_root=part.as_posix(), files=files_map))
    print(f"Archived {len(files_map)} files to {out}")


def extract_history(args):
    source, work = Path(args.source).resolve(), Path(args.work).resolve()
    history_file = PACKAGE / "historical_sources.json"
    results_file = PACKAGE / "historical_results.csv"
    require(history_file.exists() and results_file.exists(), "historical data missing from package")
    hist = read(history_file)
    results = list(csv.DictReader(results_file.open()))
    for r in hist:
        require(re.fullmatch(r"[0-9a-f]{40}", r["ref"]), "historical commit hash invalid")
    dest = work / "history"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(history_file, dest / "sources.json")
    shutil.copyfile(results_file, dest / "results.csv")
    print(f"Extracted {len(hist)} historical sources and {len(results)} mechanism findings")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    c_cfg = sub.add_parser("configure")
    c_cfg.add_argument("--source", required=True)
    c_cfg.add_argument("--work", required=True)
    c_cfg.add_argument("--evaluation-commit", required=True)
    c_cfg.add_argument("--inventory", required=True)
    c_cfg.add_argument("--quest32", required=True)
    c_cfg.add_argument("--quest64", required=True)

    c_prep = sub.add_parser("prepare")
    c_prep.add_argument("--source", required=True)
    c_prep.add_argument("--work", required=True)

    c_seal = sub.add_parser("seal")
    c_seal.add_argument("--source", required=True)
    c_seal.add_argument("--work", required=True)

    c_run = sub.add_parser("run")
    c_run.add_argument("--source", required=True)
    c_run.add_argument("--work", required=True)
    c_run.add_argument("--suite", required=True)
    c_run.add_argument("--allow-physical", action="store_true")

    c_arch = sub.add_parser("archive")
    c_arch.add_argument("--work", required=True)
    c_arch.add_argument("--part", required=True)
    c_arch.add_argument("--output", required=True)

    c_hist = sub.add_parser("history")
    c_hist.add_argument("--source", required=True)
    c_hist.add_argument("--work", required=True)

    c_w = sub.add_parser("worker")
    c_w.add_argument("--source", required=True)
    c_w.add_argument("--work", required=True)
    c_w.add_argument("--mode", required=True)
    c_w.add_argument("--case", required=True)
    c_w.add_argument("--output", required=True)
    c_w.add_argument("--arm")
    c_w.add_argument("--quest32")
    c_w.add_argument("--quest64")

    args = p.parse_args()
    dispatch = {
        "configure": configure,
        "prepare": prepare,
        "seal": seal,
        "run": run_suite,
        "archive": archive,
        "history": extract_history,
        "worker": worker,
    }
    dispatch[args.cmd](args)


if __name__ == "__main__":
    main()
