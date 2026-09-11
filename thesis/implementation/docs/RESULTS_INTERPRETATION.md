# Interpretation of the accepted research results

This document clarifies existing results. It neither modifies frozen evidence nor
prescribes a new experiment or a new estimator for an already completed study.

## 1. There is more than one baseline

The scientific progression is not one interchangeable sequence of timing rows.

| Baseline / control | What it controls | What it does not establish |
| --- | --- | --- |
| Frozen sequential full-circuit reference | Greedy, D1/T1, float32, sequential real products; same-DAG NumPy pairing | Unstaged scalar-MRAM whole-circuit performance or the final executor's CPU competitiveness |
| Scalar versus panel microablation | Staging at fixed small GEMM, numeric mode, topology, transport and launch boundary | A complete scalar-versus-final-simulator speedup |
| Matched mechanism A/B | One declared intervention with contemporaneous control | Effects of unrelated changes across releases |
| Composed-executor resource study | Resource scaling with the retained system | A pure DAG-only or tile-only causal effect when scheduling also changes |
| P6 G/F/R/U | Path-method effects on the frozen executor | CPU/GPU speedup or a change in the kernel |

The sequential source `fc02ecce69f92bccb180b4cc52ad66b7cda871b8` already uses a
WRAM-panel kernel. Do not retrospectively label it a scalar-MRAM naive kernel.
The primary control may be called a **greedy sequential reference**, with its
actual implementation stated.

Keep negative payload-staging, C-constructor, outer-K1, residency, slicing, and
path-generation results. A completed negative experiment is not unfinished work.

## 2. Timing and arithmetic definitions

For comparable arms A and B, report `S = T_A / T_B`; values above one favor B.
The corresponding time reduction is

$$
100(1-1/S)\%.
$$

Thus 1.266508x corresponds to about 21.04% less execution time, not 26.65% less
time. When S<1, use `100(1/S-1)%` to express how much more time B takes.

For each sample, form session-inclusive time as open + steady + close before
summarization. The median of that sum is generally not the sum of the three
component medians. Nested timers are not independent additive bars.

The native UPMEM `kernel_time_s` interval surrounds the synchronous SDK launch
and wait on the host. Use **SDK launch/wait** or explain the project's historical
"kernel" label. Do not call it arithmetic-only hardware time. `total_wall_s`
is steady host-plus-DPU execution, not "pure kernel and transfer time".

Do not multiply speedups from different circuits, sources, paths, environments,
or timing boundaries. A literal cumulative pipeline comparison requires a matched
ladder, which cannot be constructed by chaining historical headline ratios.

## 3. Complex arithmetic and quantization

The model contracts complex tensors. Real planes are an implementation device:
RR-II and RI+IR reconstruct the complex result. Software float32 on UPMEM and
shared-scale int8 are distinct policies. Quantization is not compulsory merely
because no hardware FPU is available.

A policy-replay pass means the hardware implemented the declared arithmetic.
Full-precision error answers a separate question. The reported approximately
8.3% Stress18 int8 relative-L2 error prevents an unqualified equal-accuracy
performance claim for that case. Exact contraction means no algorithmic
truncation, not zero finite-precision error.

## 4. P6: what is actually compared

G is deterministic greedy. F selects by conventional FLOPs from its bounded
trace. R applies the final UPMEM score to that same F trace. U has its own trace,
with the UPMEM score returned to the adaptive generator between proposals.
The comparison R/U isolates the additional value of adaptive hardware-aware
proposal generation beyond hardware-aware selection within the F trace.

Final integer weights `[1,2,1,1,5]` parameterize the normalized five-term model.
They are not 10/20/10/10/50 percent of physical runtime. The final development
diagnostics report 47 distinct selection vectors across 1,001 tuples and
16 tuples tied at the best rounded training objective. Feature correlation and
decision equivalence limit coefficient identification.

## 5. P6 positive, neutral, and negative results

The committed [aggregate table](../thesis_results/upmem_cost_guided_path_v1/readout/aggregates.csv)
reports the following session-inclusive ratios:

| Contrast | Overall ratio | Meaning |
| --- | ---: | --- |
| G/F | 1.217299x | Conventional search improves the aggregate over greedy |
| F/R | 1.039030x | Hardware-aware reranking adds an aggregate benefit over FLOP selection |
| R/U | 1.001343x | No additional resolved aggregate advantage of U over R |
| F/U | 1.040425x | Aggregate U advantage over F |
| G/U | 1.266508x | Aggregate U advantage over G |

R/U's descriptive paired-block 95% interval is [0.994836,1.008509], and 8/12
cells use the same selected path. This is not proof of equivalence or universal
interchangeability. The reported conclusion is conditional on the 128-proposal
protocol, candidate generator, represented families, topologies and seed schedule.

U is slower than G in four session-inclusive cells. The HS18 four-DPU cell is an
important counterexample:

| Metric median (seconds) | G | U |
| --- | ---: | ---: |
| Session-inclusive | 0.967281 | 1.406722 |
| Steady execution | 0.522725 | 0.537877 |
| Session opening | 0.435377 | 0.863366 |

Its G/U ratio is 0.687613x, equivalent to **45.43% more session-inclusive time for
U**. The open-time difference is substantial. This is evidence of a lifecycle-
cost limitation of the selected route/model, not proof that the DPU arithmetic
alone became 45% slower. Do not infer a complete causal decomposition by adding
independently summarized medians. The [method table](../thesis_results/upmem_cost_guided_path_v1/readout/methods.csv)
is the source of these values.

The model's host-array-pass proxy is not a complete session-opening model.
Report that limitation without refitting on this observed test case. A post-hoc
"use greedy on HS" rule is not part of the accepted evaluation.

## 6. Attempt counts and uncertainty

P6 accepted 192+144+144+198=678 physical attempts. The maximum final evaluation
was 12 cells * 4 method roles * 6 blocks = 288. Coincident selected paths were
frozen and deduplicated before execution: 33 unique cell/path selections * 6
blocks = 198. Aliases share observations and must not be counted independently.

The final descriptive bootstrap uses five complete timing blocks and one paired
search-seed schedule. Its interval does not capture variability over arbitrary
new optimizer seeds, circuit populations, hosts or hardware configurations.
The test set is instance/size transfer within six represented families, not
family-held-out generalization. Do not change this design during presentation.

## 7. CPU comparisons

The [sequential baseline](sequential_upmem_baseline.md) declares matched
`numpy_same_dag` and physical D1/T1 routes within `steady_execution_v1`, with two
warmup and 30 measured complete blocks under recorded powersave/affinity/thread
conditions. Its diagnostic claim policy remains in force. Retrieve its bound raw
bundle before calculating or copying numerical ratios into a final table.

Quimb/cotengra external workflows and QuEST full-state evolution are different
controls. QuEST's adapter declares complex128 output and separates native
compute-only timing from external process wall time. Default output admission is
bounded. Do not compare a QuEST gate-only timer or an arbitrary laptop NumPy run
with UPMEM session-inclusive timing on ETH and call the result accelerator speedup.

For a valid CPU/UPMEM comparison, query, output extent/order, circuit instance,
precision/error criterion, path protocol, timing boundary, host and threading
facts must be explicit. Fixed-path execution and best-native workflows answer
different questions and must not share an unlabeled speedup table.

P6 contains no CPU method among G/F/R/U. It therefore does not establish a final
CPU-versus-UPMEM result. Absence of such a matched final result is an evidence
gap, not permission to relabel validation timings or invent a new measurement.

## 8. Availability and claim strength

A committed checksum and acceptance record establish what a package claims and
which bytes it binds. They are not cryptographic signatures from an independent
observer, and a raw-archive digest is not the archive itself.

Distinguish rederived raw-observation results, transcribed accepted summaries,
static/model facts, software-only checks, SDK simulator checks, and physical
measurements. Values copied from historical prose must retain that provenance
class until they are reproduced from the bound raw data.

No single giant "all optimizations combined" speedup is supported by merely
listing successful module experiments. The defensible thesis is a system design
and a sequence of controlled, bounded findings, including where complexity did
not earn a measurable benefit.
