# Research and validation status

The retained execution-system study and P6 physical path campaign are complete.
A consolidated thesis-result presentation is not the same thing as another
execution-system optimization or hardware campaign.

## Scientific identities

| Role | Commit | Tag |
| --- | --- | --- |
| Executor | `459935f586fdd16c82013838e6d27a12604c3093` | `thesis-upmem-kernel-schedule-system-v1` |
| P6 software | `2beea27411c16e90ed76988613ddb00bcc09f942` | `thesis-upmem-cost-guided-software-v1` |
| P6 results | `8df2ebac61bacd08309ea490309be5a8dcb943b2` | `thesis-upmem-cost-guided-results-v1` |

## Capability and adoption matrix

| Mechanism | Disposition | Boundary |
| --- | --- | --- |
| Supported circuit -> TN -> complete path -> DAG | Implemented | Supported deterministic full pre-measurement statevector queries |
| Batched GEMM lowering | Implemented | Label permutation, one-sided reductions, bounded output/K tiling |
| Scalar-MRAM route | Controlled microablation | Not a complete matched whole-circuit naive baseline |
| WRAM-panel real-product kernel | Retained | KC=64, NC=32; bounded admission |
| Tasklets within a DPU | Retained and physically studied | T1-T24 build support; physical measurement subsets stated separately |
| Multiple DPUs per contraction | Retained and physically studied | One-rank tile/work-unit execution |
| Independent DAG nodes on disjoint groups | Retained and physically studied | Static synchronous cohorts, not arbitrary asynchronous scheduling |
| Four real products in one admitted launch | Retained | Correct complex reconstruction remains explicit |
| Packed transport / persistent native host | Retained | Fewer/cheaper request boundaries; host work remains |
| Split-complex float32 | Primary retained policy | Software DPU floating-point arithmetic |
| Shared-scale complex int8 | Separately characterized | Replay correctness does not imply full-precision accuracy qualification |
| Outer-K1 specialization | Implemented, evaluated, rejected | Negative adoption result, not an unimplemented requirement |
| Resident intermediate pair | Bounded prototype, rejected | No graph-wide production residency claim |
| Exact slicing / concurrency | Bounded evaluated transformation | Positive and negative cells; not automatic universal selection |
| Five-term UPMEM cost | Implemented and calibrated | Ranking surrogate, not uniquely identifiable physical constants |
| UPMEM reranking | Implemented and evaluated | R uses the F trace |
| UPMEM-guided generation | Implemented and evaluated | U has a separate bounded trace; no resolved aggregate advantage over R |
| NumPy/Quimb/cotengra/QuEST adapters | Implemented for declared roles | Adapter availability is not a completed matched final performance comparison |
| Multi-rank / asynchronous overlap / automatic CPU-DPU placement | Outside retained scope | No performance claim |
| Energy efficiency | Not established | Some external energy-related code is not an accepted UPMEM energy study |

## Accepted findings

The detailed [executor record](docs/upmem_kernel_schedule_system_v1.md) preserves
per-study source, measurement boundary, controls, adoption rules and archives.
Representative recorded results include:

| Comparison | Recorded session-inclusive ratio | Qualification |
| --- | ---: | --- |
| Final Stress16 D1/T1 -> D1/T16 | 4.501040x | Composed-executor resource diagnostic |
| Final Stress16 D1/T8 -> D4/T8 | 1.530679x | Composed-executor resource diagnostic |
| Complex launch fusion confirmation | 1.9034x | Fresh development confirmation for its declared cell |
| Six-cell serial/static-DAG A/B | 1.214213x | Equal-cell development aggregate |
| Stress16 D4/T8 DAG confirmation | 1.431726x | Fresh development confirmation, not untouched cross-family testing |
| Outer-K1 target region | 0.985619x | Adoption rejected |
| Stress16 bounded residency probe | 0.959855x | Adoption rejected |
| Stress16 slicing, D2 / D4 | 0.608676x / 0.780553x | Negative combined transformation/scheduling results |
| EDC14 D4 slicing confirmation | 1.125244x | Positive bounded development result |

These ratios belong to separate experiments. They must not be multiplied into a
single cumulative speedup. The scalar/panel result is a microablation with a
separate boundary, not another whole-circuit row in this table.

## P6 accounting and interpretation

| Stage | Accepted physical attempts |
| --- | ---: |
| Initial | 192 |
| Feedback 1 | 144 |
| Feedback 2 | 144 |
| Evaluation | 198 |
| Total | 678 |

The ceiling was 768; retries and replacements were zero. Evaluation used 33
unique cell/path selections per block after method-role deduplication, so
`33 * (1 warmup + 5 measurements) = 198`. It is not an incomplete 288-attempt run.

Final integer weights: `[1,2,1,1,5]`. The 1,001-tuple development grid produces
47 distinct measured-pool selection vectors, with 16 tuples tied at the best
rounded training objective. Weights are ranking parameters, not measured shares.

Primary R/U session-inclusive ratio: **1.001343x**, descriptive interval
**[0.994836, 1.008509]**, same selected path in **8/12 cells**.

F/U is **1.040425x** overall and **1.081841x** at four DPUs. G/U is **1.266508x**
overall. U is nevertheless slower than G in four cells; for HS18 at four DPUs,
G/U is **0.687613x**. Report regressions, search cost, and lifecycle timing with
aggregate improvements. See [interpretation](docs/RESULTS_INTERPRETATION.md).

## Software evidence is not hardware evidence

For the cleanup audit anchor `7c2bd4094192644139f6b2c218bbcbe91e3fc079`, hosted run
`34584955327` / job `103216904431` reported **2,257 passed and 232 skipped**, not
2,489 executed passes. The run checked PR merge commit
`a1c4cf2bfe62d75736748c1934367c2541bbef0d`; its Git tree
`6490e7c082d3a6f9038e4f83e88340917a501cd3` matches the audited branch tree.
That is successful tree-equivalent PR CI, not a literal checkout of the head SHA.

The operator separately reported 2,489 passes in an SDK-equipped local/fresh-clone
environment. Those local claims must be tied to their retained logs and environment.
Subsequent runs must record collected/passed/skipped/failed counts, skip reasons,
actual checkout SHA, tree SHA, Python version and SDK availability.

SDK absence explains skips in SDK-gated tests; it does not invalidate the distinct
historical physical qualifications. Conversely, green generic CI cannot replace
SDK or physical qualification. Preserve full Git history for provenance checks.

## Evidence access and remaining presentation gaps

The committed [P6 package](thesis_results/upmem_cost_guided_path_v1/README.md)
contains compact accepted records and readout tools. Original physical archive
bytes are stored separately; a digest alone is not a downloadable raw dataset.
Several earlier mechanism studies are documented through their accepted records
and archive identities rather than a single public raw-data bundle.

The historical sequential CPU control and the scalar kernel microablation have
different purposes. No matched final CPU-versus-retained-UPMEM speedup follows
from P6 alone. No new measurement, refitting, or hardware invocation is authorized
by this status document.
