# Architecture

## Data flow

```text
SimulationJob → TensorNetwork → complete path → ContractionDAG
  → UpmemPlan → static DAG waves → packed native request
  → DPU tile products → host reconstruction/reduction → full statevector
```

`TensorNetwork` expresses circuit semantics; `ContractionDAG` expresses dependencies.
`UpmemPlan` adds numerical policy, resource admission, tiling and placement.
Binary contractions lower by label permutation/reshaping to batched products
`(B,M,K) @ (B,K,N)`. Output reconstruction preserves canonical index ordering.
Planning, layout preparation and intermediate reconstruction remain on the host.

## Retained executor

| Layer | Mechanism |
| --- | --- |
| Within a DPU | Tasklets own cyclic output rows; private buffers consume shared WRAM B panels |
| Within one contraction | Tiles/K chunks are distributed across DPUs; host combines partial results |
| Between contractions | Dependency-ready DAG nodes use disjoint DPU groups in synchronous cohorts |
| Dispatch | Persistent native host, `packed_wave_v1`, prepared-wave ABI-v5 |
| Kernel | WRAM panels (`KC=64`, `NC=32`), `panel_only_v1` |
| Complex launch | Four product lanes in one launch when admitted; otherwise generic UPMEM execution |
| Intermediates | `host_roundtrip_v1`; one-rank scope |

Panel barriers separate loading, consumption and buffer reuse. Dependent nodes see
outputs only after their cohort completes. Session locks reject overlapping run/close
operations. These mechanisms are not asynchronous transfer/compute overlap.

## Complex numerical policies

For complex operands, four real products reconstruct the result:

\[
\Re(C)=A_rB_r-A_iB_i,\qquad \Im(C)=A_rB_i+A_iB_r.
\]

`split_complex_float32_v1` is the primary policy, including P6. UPMEM executes
software floating-point arithmetic; quantization is not compulsory.

For `complex_int8_shared_scale_v1`, the host computes
\(a(X)=\max(\lvert\Re X\rvert,\lvert\Im X\rvert)\),
\(s(X)=a(X)/127\) (or 1 for zero), then rounds each component to nearest-even and
clips to \([-127,127]\). Bounded integer product lanes are decoded and reconstructed
on the host; subsequent contractions requantize their operands. Policy replay and
full-precision error are separate checks. No SVD truncation is used.

## Path score

The final dimensionless ranking surrogate uses actual lowered-plan facts:

\[
C_\theta=\theta_HH/s_H+\theta_PP/s_P+\theta_NN/s_N
+\sum_\ell\max_d(\theta_MM_{\ell d}/s_M+\theta_WW_{\ell d}/s_W).
\]

H denotes host/DPU traffic, P the declared host array-pass proxy, N coordination,
M estimated local movement, and W real arithmetic work. Scales come from development
greedy cells. Movement and work are combined **before** each launch's DPU maximum.
The fitted weights rank plans; they are neither seconds nor runtime percentages.

## Measurement boundary

`total_wall_s` is steady host-plus-DPU execution. Per-sample session-inclusive time
adds opening and closing. The native `kernel_time_s` surrounds synchronous SDK
launch/wait; it is not arithmetic-only device time. Search time is separate.
Nested timers are not independent components; sum within samples before summarizing.

See [results](RESULTS.md) for retained/rejected experiments. Multi-rank execution,
energy measurement and automatic CPU/UPMEM placement are outside the completed scope.
