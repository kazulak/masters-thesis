# Research results

This is a synthesis of completed studies, not a new benchmark or recalculation.
Mechanism results below are transcribed from their recorded studies; P6 values
come from its committed tables. Different sources, workloads and timing scopes
must not be pooled into a cumulative speedup.

## Authoritative final evaluation: unified-v4

The [accepted unified package](thesis_results/unified_final_v4/README.md) is the final
six-family dataset. It supersedes earlier campaigns as the headline evaluation;
those remain separate evidence for mechanisms and design decisions.

- Calibration completed 2,674 physical executions. Qualification issued 108 and
  final UPMEM execution issued 552, totaling **3,334 ≤ 3,406**.
- Of 52 final R searches, 46 selected a path and six maximum-width primary cases
  admitted no candidate. These are planning frontiers, not failed executions.
- Final accounting is 1,560 planned / 1,452 issued and successful / 108 unissued.
  UPMEM float32, int8 and NumPy each issued 276; QuEST P8 and P1 each issued 312.
- Cumulative A0–A4 execution-call speedup has a six-family geometric mean of
  approximately 6.25×. A1 is D1/T8; A3 adds complex launch/four-product fusion;
  A4 adds static-DAG scheduling. Fusion is not quantum-gate fusion.
- One-rank DPU scaling saturated after D16, with lower aggregate speedup at
  D32/D64. The timings alone do not establish a dominant causal component.
- Int8 is approximate. Resource selection used no post-hoc quality tuning.
  Numerical quality is disclosed separately from physical execution success.

See the [current reporting captions and tables](../reporting/README.md) for exact
metrics, uncertainty definitions and CPU comparisons. Final comparisons use
cached-path job-to-state time; calibration plots use execution-call wall time.
One-time R preparation/search cost is separate. Raw archives retain the original
readouts; corrected committed canonical readouts are authoritative for reporting.
The [release audit](../../release/AUDIT.md) explains this distinction and verifies
all retained packages. No data were regenerated during release preparation.

## Historical mechanism and supporting studies

The following results retain their original scope and source identities.

## Foundation and execution studies

The sequential full-circuit reference used greedy, one DPU, one tasklet,
split-complex float32 **and an existing WRAM-panel kernel**. It was paired with
same-DAG NumPy under recorded diagnostic conditions. It is not a scalar-MRAM
whole-circuit baseline. GEMM lowering and complex reconstruction are structural
foundations, not independently measured speedups. [Baseline][baseline]

| Investigation | Recorded finding | Disposition |
| --- | --- | --- |
| Scalar-MRAM vs panel | M=N=K=32, D1/T8 microablation: approximately 1.154× kernel and 1.0452× inclusive | Staging evidence for that microcase only |
| Tasklet and multi-DPU execution | T1–T24 builds and selected physical routes, including non-power-of-two counts | Retained; support range is not a scaling claim |
| Circuit/resource sensitivity | Host request costs remained important across Stress18, HS18 and GHZ18 | Workload-dependent bottleneck evidence |
| First payload-staging attempt | Failed its adoption gate | Negative result |
| Session-local templates | Reduced repeated record construction | Retained historical optimization |
| Constructor-only C migration | Slower without removing request/filesystem boundaries | Rejected |
| Packed-operation transport | 72 A/B attempts; 5.90–30.65% inclusive time reduction across tested cells | Adopted |
| Complex launch fusion | 1.9034× inclusive fresh development confirmation | Retained when admitted |
| Outer-K1 specialization | 0.985619× inclusive; interval spans one | Not adopted |
| Static DAG waves | 1.214213× inclusive six-cell aggregate; 1.431726× selected fresh confirmation | Retained |
| Resident pair | Stress16 D1: 0.959855× | Not adopted |
| Exact slicing plus static scheduling | Stress16 D2: 0.608676×; D4: 0.780553×; EDC14 D4 confirmation: 1.125244× | Mixed; not automatic |
| Final composed tasklet scaling | Stress16 D1/T1→D1/T16: 4.501040× inclusive | Composed-system diagnostic |
| Final composed DPU scaling | Stress16 D1/T8→D4/T8: 1.530679× inclusive | Composed-system diagnostic |

Evidence: [hierarchical scaling][hierarchy], [circuit sensitivity][sensitivity],
[transport][transport], [final kernel/scheduling record][executor].
The slice comparison changes both transformation and schedule; it does not isolate
slice concurrency. Selected development confirmations are not untouched tests.

## Quantization

The shared-scale complex-int8 diagnostic accepted 180 physical attempts and matched
same-policy CPU replay. It accelerated every tested fixed route, but Stress18 had
approximately **8.3% relative L2 error**. GHZ18 and HS18 matched their tested float32
results. The best observed HS18/Stress18 route changed from four DPUs to two under
int8. Numerical suitability and useful parallelism are workload-dependent. [Record][int8]

## Supporting path-selection study (historical tag P6)

G is greedy; F selects by FLOPs; R reranks F's candidate trace with the UPMEM score;
U generates a separate adaptive trace using that score. Each search has 128 proposals.
Training-only fitting selected integer weights **[1,2,1,1,5]**: ranking coefficients,
not physical time shares. There were 47 distinct selection vectors across 1,001
tuples and 16 tuples tied at the best rounded training objective.

The campaign accepted **192 + 144 + 144 + 198 = 678 attempts**, within 768,
with no retries or replacements. Evaluation used 12 circuit/topology cells. Method
aliases were deduplicated: 33 distinct cell/path selections × six blocks = 198.

| Session-inclusive contrast | Overall ratio |
| --- | ---: |
| G/F | 1.217299× |
| F/R | 1.039030× |
| R/U — primary | 1.001343× |
| F/U | 1.040425× |
| G/U | 1.266508× |

R/U's descriptive paired-block 95% interval is **[0.994836, 1.008509]**;
R and U selected the same path in 8/12 cells. Hardware-aware selection helped,
but adaptive generation provided no resolved additional execution benefit.
Four-DPU F/U was 1.081841× inclusive and 1.115376× steady wall time.

U was slower than G in **four cells**. HS18/D4 had G/U = **0.687613×**, or
about **45.43% more inclusive time** for U (0.967281 s versus 1.406722 s).
The opening-time difference was substantial; this does not show a 45% arithmetic
slowdown. Do not fit a post-hoc exception to this evaluated case.

Sources: [readout](thesis_results/upmem_cost_guided_path_v1/readout/report.md),
[aggregates](thesis_results/upmem_cost_guided_path_v1/readout/aggregates.csv),
[per-method times](thesis_results/upmem_cost_guided_path_v1/readout/methods.csv),
[model diagnostics](thesis_results/upmem_cost_guided_path_v1/readout/model_diagnostics.json).
The earlier path pilot is exploratory: original raw archives were lost; it is not
canonical final held-out evidence.

## Interpretation and CPU context

Ratios are baseline time / alternative time; time reduction is **100(1−1/ratio)%**.
A 1.266508× speedup means 21.04% less time, not 26.65%. Inclusive sums are formed
per sample; medians and nested timers cannot be added indiscriminately.

P6 tests instance/parameter transfer within six represented families, not unseen
families. Its bootstrap uses five timing blocks and one paired search-seed schedule;
it is descriptive, not an equivalence test. Offline search time is separate.

Same-DAG NumPy, CPU physical-plan replay, Quimb/cotengra and QuEST serve different
controls. The historical CPU/UPMEM sequential comparison is diagnostic; **P6 does
not establish final-system CPU superiority**. Matched query, precision/error,
path policy, timing and host/thread settings are required for a speedup claim.

See [evidence packages](thesis_results/README.md) and
[reproducibility](../../REPRODUCIBILITY.md). No universal UPMEM acceleration,
energy benefit, globally optimal path or universally accurate int8 is established.

[baseline]: https://github.com/kazulak/masters-thesis/blob/504e614c5064ba020e5f47f6d05202568faadd69/thesis/implementation/docs/sequential_upmem_baseline.md
[hierarchy]: https://github.com/kazulak/masters-thesis/blob/504e614c5064ba020e5f47f6d05202568faadd69/thesis/implementation/docs/hierarchical_parallel_diagnostic.md
[sensitivity]: https://github.com/kazulak/masters-thesis/blob/504e614c5064ba020e5f47f6d05202568faadd69/thesis/implementation/docs/circuit_resource_sensitivity_diagnostic.md
[transport]: https://github.com/kazulak/masters-thesis/blob/504e614c5064ba020e5f47f6d05202568faadd69/thesis/implementation/docs/packed_operation_transport_adoption.md
[executor]: https://github.com/kazulak/masters-thesis/blob/504e614c5064ba020e5f47f6d05202568faadd69/thesis/implementation/docs/upmem_kernel_schedule_system_v1.md
[int8]: https://github.com/kazulak/masters-thesis/blob/504e614c5064ba020e5f47f6d05202568faadd69/thesis/implementation/docs/quantized_upmem_execution_diagnostic_v1.md
