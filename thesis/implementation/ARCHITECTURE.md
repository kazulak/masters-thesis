# Architecture of the retained thesis implementation

This describes the retained executor and completed P6 study. Historical source
names and checkpoint comments are not the authority for the current configuration.
The detailed development record is
[upmem_kernel_schedule_system_v1.md](docs/upmem_kernel_schedule_system_v1.md).

## 1. Semantic and execution layers

```text
SimulationJob
  -> supported deterministic circuit
  -> TensorNetwork and complex operands
  -> complete contraction path
  -> ContractionDAG
  -> UpmemPlan for a declared numeric policy and resource topology
  -> static dependency-ready cohorts / host-reduction stages
  -> prepared packed-wave controls
  -> persistent native host / synchronous UPMEM SDK calls
  -> DPU real-product kernels
  -> host K-chunk reduction and complex reconstruction
  -> full pre-measurement statevector
```

`TensorNetwork` is target-neutral. A path determines pairwise contraction order;
`ContractionDAG` records dependencies and explicit reductions. `UpmemPlan` records
target-specific work and scheduling. A plan is not a measurement, and successful
planning is not proof that a physical session ran.

The supported thesis query is the complete deterministic pre-measurement
statevector with declared basis ordering. No shots, noise, mid-circuit classical
feedback, or SVD truncation are introduced by the retained execution profile.
Bounded exact slicing preserves the declared output; it does not generally turn
a full-statevector query into one scalar per slice.

## 2. Tensor contraction becomes batched matrix multiplication

For a supported binary contraction, shared indices retained in the output form
batch axes, shared eliminated indices form the reduction axis, and remaining
output indices form free left/right axes. One-sided eliminated indices are
reduced before matrix multiplication. Permutation and reshape yield

$$
A\in\mathbb C^{B\times M\times K},\quad
B'\in\mathbb C^{B\times K\times N},\quad
C_{bmn}=\sum_k A_{bmk}B'_{bkn}.
$$

The implementation restores the requested output-label order after tile assembly.
An ordinary tensor contraction is bilinear: it does not conjugate an operand
unless the input tensor semantics explicitly require that conjugation.

`upmem/tiling.py` and `upmem/plan.py` share the label-to-geometry rules. Duplicate
input labels and unsupported geometries must be rejected rather than interpreted
as a different operation. Output tiles partition the output; K chunks produce
partials accumulated in a fixed order.

This GEMM lowering is already part of the baseline. It is not an additional
measured acceleration merely because later kernels operate on the same geometry.

## 3. Complex and finite-precision arithmetic

Write `A = Ar + i Ai` and `B = Br + i Bi`. The execution produces four real lanes:

$$
RR=A_rB_r,\quad II=A_iB_i,\quad RI=A_rB_i,\quad IR=A_iB_r,
$$
$$
C=(RR-II)+i(RI+IR).
$$

The physical kernels need not have a complex datatype to implement complex
contraction. Each output is reconstructed on the host in the declared policy.

### Float32 policy

`split_complex_float32_v1` uses float32 real and imaginary planes with scale one.
The DPU runs compiled software floating-point operations; absence of a hardware
FPU does not imply that quantization is mandatory. The output is complex64.

The reference for physical-policy correctness reproduces the intended tiling,
real-lane, accumulation, and reconstruction order. A complex128 semantic reference
serves a distinct full-precision accuracy role. Agreement with shared-lowering
replay alone is not an independent proof of correct circuit semantics.

### Shared-scale int8 policy

For each complex operand X,

$$
a(X)=\max(\max|\Re X|,\max|\Im X|),\qquad
s(X)=\begin{cases}1&a(X)=0\\a(X)/127&a(X)>0.\end{cases}
$$

Each plane uses nearest-even rounding and clipping into `[-127,127]`.
Per-lane products accumulate as integers; the host combines lanes and applies
`s(A)*s(B)`. The implementation widens integer lane values before their complex
combination and checks overflow where int64 values are combined. A conservative
admission bound is

$$
2K\,127^2\le 2^{31}-1.
$$

The factor two bounds the two real product streams contributing to one complex
component. Intermediate outputs are reconstructed and requantized when consumed
by later contractions. Neither the policy nor quantum unitarity implies that an
arbitrary contraction-tree intermediate has every entry bounded by one.

Quantization changes numerical error, traffic, and useful resource allocation.
It does not become an equal-accuracy speedup by passing integer replay. Execution
success, same-policy correctness, and full-precision accuracy remain separate.

## 4. Memory and kernels

The retained prepared-wave contract admits work into a **512-KiB MRAM arena per
DPU**, not unrestricted use of the device's entire MRAM capacity. Its panel kernel
uses `KC=64`, `NC=32`, a shared B panel, tasklet-private A/output/scratch buffers,
and declared shape/alignment bounds.

For each panel, tasklets cooperatively fill disjoint portions of B, synchronize,
compute their cyclically owned output rows, and synchronize before B is reused.
For tasklet count T, row r belongs to exactly one tasklet `r mod T`. Tasklets with
no output row still participate in required barriers.

Odd-width outputs can share an aligned MRAM edge between adjacent logical rows.
The matching-version UPMEM SDK 2023.1.0 unaligned-write implementation uses
edge-granule locks for its read/modify/write operations. Therefore row ownership
alone is not the complete safety argument: kernel ownership, barriers, and the
SDK edge-write semantics must be considered together. Changing the SDK requires
renewed qualification; software tests do not prove every physical interleaving.

`fused_when_admitted_v1` retains all four real products and their separate outputs
but executes them within one admitted launch. The memory requirement includes
two complex operands and four output planes. Non-admitted fusion uses the declared
generic UPMEM route; it does not silently retile or fall back to CPU contraction.

The outer-K1 kernel remains available as a tested experimental mechanism but was
not retained by the performance adoption rule. The accepted general geometry
policy remains `panel_only_v1`.

## 5. Three distinct parallelism levels

| Level | Work split | Synchronization / communication |
| --- | --- | --- |
| Tasklets | Output rows within one DPU's tile computation | Shared WRAM panels and barriers |
| DPUs within one contraction | Distinct admitted output/K-chunk work units | Host distribution, collection, and declared partial reduction |
| Ready DAG contractions | Different nodes assigned disjoint DPU groups in one cohort | Dependency readiness before cohort; validated completion before dependent work |

Splitting one contraction across DPUs does not inherently require Cannon-style
cyclic tile exchange. The retained host-managed decomposition distributes complete
local work and pays explicit replication/transfer/reduction costs instead.

`static_dag_waves_v1` prioritizes dependency-ready nodes by remaining critical-path
work, with deterministic node-ID ties. It assigns disjoint groups, preserves
within-node wave/K-chunk order, and completes host-reduction dependencies before
consumer work. The runtime consumes the planned schedule rather than remapping it.

The whole cohort is executed and reconstructed before its results can be used by
a subsequent dependent cohort. It is not an asynchronous generic task scheduler.

Exact slicing is a separate transformation and bounded experiment. Slice count,
working-set feasibility, repeated work, and tensor-output reduction all matter;
independence alone does not guarantee a speedup.

## 6. Host lifecycle and evidence

The high-level session, low-level runtime session, and native session client have
nonblocking operation locks. Concurrent use of one session fails with a busy
error instead of interleaving requests or closing an active session. Separate
sessions are not globally serialized by these object-local locks; physical
experiment admission has its own process/rank lock and occupancy checks.

The native prepared-wave host validates controls, identities, spans and bounds,
performs synchronous transfers and launches, and returns checked completion
records. The client checks result size, digest and expected identities. Timeouts
poison the session and trigger termination/release handling. No direct CPU fallback
is accepted as physical UPMEM evidence.

Host arrays, encoded operands, and raw-lane evidence buffers can remain live
through a run. Theoretical maximum intermediate tensor size is not the full host
working set or measured RSS. The current system is not a graph-wide MRAM-resident
simulator, and Python orchestration is part of the measured implementation.

## 7. Timing semantics

| Quantity | Interpretation |
| --- | --- |
| `steady_execution_v1` / `total_wall_s` | Measured host-plus-DPU execution boundary, including preparation, transport and reconstruction; excludes planning/session lifecycle |
| Session-inclusive | Per-sample open + steady + close, summed before summarization |
| Native `kernel_time_s` | Host clock around synchronous SDK launch and wait; not arithmetic-only DPU time |
| DPU cycle facts | Distinct device-side counter observations, where recorded |
| External `simulation_end_to_end_v1` | Route-specific preparation-through-output boundary; inspect adapter and declared scope |
| Offline search time | Separate planning cost, not hidden inside execution speedup |

Concurrent-cohort aggregate timing is attributed once (on the first node in the
recording scheme), not measured separately for every node. Do not interpret this
accounting convention as one node doing all the work. Nested timers and separately
summarized medians are not automatically additive.

Validation, reference calculation, evidence hashing, and reporting are outside
the relevant execution timing scopes where the experiment contract says so.
Their actual cost still matters for one-shot usability, but cannot be reconstructed
by relabeling a steady timer as complete job time.

## 8. Final path-search model

The P6 model is `upmem_launch_cost_v1`:

$$
C_\theta(\Pi)=\theta_HH/s_H+\theta_PP/s_P+\theta_NN/s_N+
\sum_\ell\max_d(\theta_MM_{\ell d}/s_M+\theta_WW_{\ell d}/s_W).
$$

H denotes planned host/DPU traffic; P is the declared host array-pass proxy; N is
the specified coordination count; M and W are local movement and real arithmetic
work per DPU/launch. The weighted M+W contribution is formed before taking the
per-launch maximum. Aggregate work is not charged again as a second parallelism
penalty. Scales are frozen from development-greedy facts.

The model is a ranking surrogate, not a prediction in seconds. Its host-pass proxy
is not a complete model of Python, hashing, allocation or session-opening cost.
The retained older six-term/grouped helpers are not P6's active objective.

P6 enumerates the 1,001 nonnegative integer five-tuples summing to ten, using the
specified training objective and deterministic ties. Final weights are
`[1,2,1,1,5] / 10`; they are not physical runtime shares.

A serial cotengra/Optuna ask/tell adapter generates one complete candidate, lowers
and scores it, and returns the score before requesting the next proposal. F tells
FLOP cost; U tells UPMEM cost. R reranks F's trace. This is adaptive generator-
parameter search, not a newly implemented contraction-tree engine or literal
local tree-mutation annealing. The final evaluation is frozen and never refitted.

## 9. CPU/reference roles and limits

NumPy same-DAG replay controls path and arithmetic differences. Quimb/cotengra
provides an external TN workflow; QuEST provides an independent supported
full-state route. These adapters do not create a fair speedup comparison merely
by existing. Match query/output, numeric policy, host/thread settings, workload,
and timing scope. QuEST's native compute-only timer is not comparable directly
with UPMEM session-inclusive time; its adapter also reports a separate external
wall-time scope and complex128 output.

No final matched CPU-versus-retained-UPMEM competitiveness result is established
by P6's G/F/R/U comparison. The historical same-DAG CPU comparison remains a
conditioned diagnostic at its own frozen source.

## 10. Scientific identities

Executor: `459935f586fdd16c82013838e6d27a12604c3093`.
P6 software: `2beea27411c16e90ed76988613ddb00bcc09f942`.
P6 results: `8df2ebac61bacd08309ea490309be5a8dcb943b2`.

Preserve those identities and their evidence. Publication corrections do not
retroactively change an executed algorithm, policy, candidate set, or result.
