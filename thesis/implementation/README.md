# Research implementation

This is the active implementation of deterministic, full pre-measurement
statevector simulation for supported circuits through exact, untruncated
complex tensor-network contraction with physical UPMEM offload.

[Architecture](ARCHITECTURE.md), [status](STATUS.md),
[research records](docs/README.md), and
[interpretation](docs/RESULTS_INTERPRETATION.md) define the completed research.
The [root reproducibility guide](../../REPRODUCIBILITY.md) is the canonical
installation and verification entry point.

## Execution pipeline

```text
SimulationJob -> TensorNetwork -> complete path -> ContractionDAG
  -> UpmemPlan -> static dependency-ready cohorts
  -> packed-wave transport -> persistent native host
  -> WRAM-panel DPU execution -> host reconstruction/reduction
  -> little-endian full statevector -> validation and evidence
```

The conventional contraction is lowered to batched `(B,M,K) @ (B,K,N)` products.
This mathematical GEMM lowering does not mean that a generic GPU/CPU BLAS library
runs on UPMEM. The retained DPU implementation is the thesis-owned panel kernel.

## Retained execution profile

| Decision | Retained policy |
| --- | --- |
| Scope | One UPMEM rank |
| Transport | `packed_wave_v1` |
| Schedule | `static_dag_waves_v1` |
| Complex dispatch | `fused_when_admitted_v1` |
| Geometry | `panel_only_v1` |
| Intermediate placement | `host_roundtrip_v1` |
| Primary numerical policy | `split_complex_float32_v1` |
| Separate approximate policy | `complex_int8_shared_scale_v1` |

Parallelism exists within a DPU across tasklets, across tiles of one contraction
on multiple DPUs, and across dependency-ready contractions on disjoint DPU groups.
Cohorts are synchronous. This is not asynchronous transfer/kernel overlap.

Complex products use RR, II, RI, and IR lanes; the host reconstructs
`real = RR - II`, `imag = RI + IR`. Fusion reduces launch boundaries where memory
admission permits; it neither removes the four real products nor silently moves
contraction work to the CPU.

UPMEM has no hardware FPU, but the float32 policy executes software floating-point
arithmetic on DPUs. Int8 quantization is optional and has its own error analysis.
Correct replay of int8 arithmetic does not imply acceptable full-precision error.

## Source map

| Source | Responsibility |
| --- | --- |
| `circuits.py`, `lowering.py`, `model.py` | Supported circuit semantics, TN/DAG construction and validation |
| `upmem/tiling.py`, `upmem/plan.py` | Label-to-matrix geometry and bounded physical work |
| `upmem/scheduling.py` | Deterministic ready-node scheduling and disjoint groups |
| `numerics.py`, `quantized_contraction.py` | Complex policies, quantization, reconstruction and policy replay |
| `upmem/wave_work.py`, `packed_wave.py`, `wave_protocol.py`, `wave_result.py` | Shared launch decisions and checked packed protocol |
| `upmem/runtime.py`, `upmem/native_session.py` | Host orchestration, session exclusivity, reconstruction and evidence facts |
| `native/upmem/runtime/` | Native host, checked controls, WRAM-panel/four-product DPU kernels |
| `upmem/execution_features.py`, `upmem/path_heuristic.py` | Complete-plan facts and scoring primitives |
| `scripts/upmem_cost_guided_path.py`, `scripts/upmem_cost_guided_execution.py` | Bounded P6 search/fitting and physical-controller contract |
| `cpu.py`, `baselines.py` | Same-DAG/policy references and external simulation adapters |
| `cli.py`, `experiment.py`, `evidence.py`, `report.py` | Collection, validation, evidence and reporting |

Several source identifiers still contain `v4`, `M5`, or older checkpoint wording.
Those historical names do not determine the active transport. The retained wave
route uses ABI-v5 controls. Do not rename or cosmetically edit hash-bound source
files merely to remove historical terminology.

## P6

The completed float32 study uses `upmem_launch_cost_v1`, a five-term,
launch-aware ranking surrogate. The final integer coefficient vector is
`[1,2,1,1,5]` over `(H,P,N,M,W)`, normalized by ten. It is not a runtime-share
breakdown or a uniquely identified set of machine constants.

The module also retains older six-term and grouped scoring helpers for historical
studies. They are not the final P6 objective. P6 uses a separate serial ask/tell
search adapter; reading the legacy helpers alone gives an incorrect description
of the final algorithm.

The immutable [P6 package](thesis_results/upmem_cost_guided_path_v1/README.md)
records 678 physical attempts, a frozen evaluation, and the primary R/U result.
The overall near-neutral R/U result coexists with gains over F and regressions
against G for particular cells. See the complete
[interpretation](docs/RESULTS_INTERPRETATION.md), not only aggregate speedups.

## Baselines and timing

The sequential reference uses greedy, D1/T1, separate real-product launches, and
WRAM-panel staging. It is not an unstaged scalar-MRAM whole-circuit baseline.
The separate scalar/panel microablation isolates staging on a small fixed GEMM.
Do not combine those experiments into a manufactured cumulative speedup.

`steady_execution_v1` includes host preparation/encoding, requests, transfers,
launches, reconstruction, and final output copying inside its measured boundary.
It excludes planning and session lifecycle. Session-inclusive time adds the
measured open and close times per sample. Neither is the complete one-shot job
including path search and reference validation.

The native `kernel_time_s` counter times synchronous SDK launch/wait on the host.
It is not a direct measurement of arithmetic-only DPU cycles. Cohort counters
are attributed once, not independently to every concurrently executed node.

## Evidence schemas

Manifests use `evidence_manifest_v2`, samples use `evidence_sample_v4`, sessions use
`evidence_session_v1`, and reports use `evidence_report_v5`. These identifiers are
part of the active evidence contract and are the schemas used by the current reporting
pipeline.

## Verification from the repository root

```bash
python3.10 -m venv thesis/.venv
thesis/.venv/bin/python -m pip install --upgrade pip
thesis/.venv/bin/python -m pip install \
  -c thesis/implementation/ci/constraints.txt \
  -e './thesis/implementation[dev,path-search]'
make -C thesis/implementation/native/quest_cpu
PY="$(pwd)/thesis/.venv/bin/python"
PYTEST_ADDOPTS=-ra make -C thesis/implementation PYTHON="$PY" test
"$PY" -m ruff check thesis/implementation/src thesis/implementation/tests thesis/implementation/scripts
```

SDK-dependent tests may skip when their prerequisites are absent. Do not turn a
collection count into a pass count. No physical campaign should be launched by
these commands. Accepted physical evidence is independently source-bound.
