// Standalone presentation review; reads generated assets only.
// Compile from the repository root:
// typst compile --root . thesis/reporting/review.typ /tmp/thesis-reporting-review.pdf
#set document(title: "Thesis reporting review", author: "Tomasz Kazulak", date: none)
#set page(paper: "a4", margin: (x: 25mm, y: 20mm), numbering: "1")
#set text(font: "DejaVu Sans", size: 9pt, lang: "en")
#set par(justify: false)
#set heading(numbering: none)
#show heading.where(level: 1): set text(size: 12pt)

= Thesis reporting review

Five main figures, five main tables, three appendix figures and six appendix
tables, generated directly from accepted evidence. The figures show trends;
the tables give exact comparisons, numerical quality and experimental scope.

This is a review document for manuscript integration. It neither executes nor
regenerates the scientific campaign. Figure and table sources and complete notes
are documented in the reporting README. Historical experiments retain their own
scope and provenance; their effects are not combined into a cumulative speedup.

#outline(title: [Contents], depth: 1)

#pagebreak()
= F1 — Tasklet scaling

#image("generated/figures/fig01_tasklets.svg", width: 160mm)
#v(3pt)
#text(size: 8.5pt, "Execution-call speedup across tasklets on one physical DPU, using float32 and serial unfused execution. The fixed reference is the same circuit at one tasklet. Five measured blocks support each median; whiskers transform median ± raw MAD with the reference held fixed, describing dispersion and omitting reference uncertainty. The reference self-normalizes to one. Execution-call time includes opening the runtime, execution and transfers, output materialization and closing; it excludes circuit lowering, path search, DAG construction and physical mapping. EDC uses 17 qubits; the other families use 18.")

#pagebreak()
= F2 — DPU scaling

#image("generated/figures/fig02_dpus.svg", width: 160mm)
#v(3pt)
#text(size: 8.5pt, "One-rank DPU scaling with float32, greedy contraction paths, complex launch fusion and static-DAG scheduling. Eight- and 24-tasklet series each use their own one-DPU median reference; their relative heights do not compare absolute runtimes. Five measured blocks support medians. Whiskers transform median ± raw MAD with the matched reference fixed, describing dispersion rather than confidence intervals. Runtime is the execution-call boundary defined for F1. EDC uses 17 qubits and the other families 18. DPU count is logarithmic.")

#pagebreak()
= F3 — Cumulative executor changes

#image("generated/figures/fig03_ablation.svg", width: 160mm)
#v(3pt)
#text(size: 8.5pt, "Bars show float32 execution-call runtime as a percentage of the same circuit’s serial baseline; lower is faster. Each configuration retains all preceding changes: baseline = one DPU/one tasklet, then eight tasklets, four DPUs, complex launch/four-product fusion, and static-DAG scheduling. The last three configurations all use eight tasklets per DPU. Before the final step, contraction nodes are scheduled serially. Seven measured blocks support each median; whiskers are raw MAD scaled by the fixed baseline, without baseline uncertainty. The baseline is exactly 100%. Paths are greedy. The six-family baseline-to-final geometric-mean speedup is approximately 6.25×. A-T6 gives the exact timings and configurations.")

#pagebreak()
= F4 — Physical int8 performance

#image("generated/figures/fig04_quantization.svg", width: 160mm)
#v(3pt)
#text(size: 8.5pt, "Float32/int8 execution-call median-time ratios at matched circuit, DPU and tasklet configurations. Values above one favor int8. Both policies use greedy paths, complex launch fusion and static-DAG scheduling. Each median summarizes five measured blocks; ratios have no uncertainty intervals. The x-axis changes DPU count, with circuit widths fixed at 17 for EDC and 18 otherwise. Execution-call timing follows F1. Int8 uses shared scaling and approximate arithmetic; runtime ratios do not imply equal accuracy. T2 and A-T5 disclose numerical quality. No post-hoc approximation-quality tuning was used.")

#pagebreak()
= F5 — Final UPMEM and CPU comparison

#image("generated/figures/fig05_final_cpu.svg", width: 160mm)
#v(3pt)
#text(size: 8.5pt, "Median cached-path job-to-state runtime from five measured blocks; whiskers are raw MAD, describing dispersion rather than confidence intervals. Time runs from a preloaded circuit to an owned statevector. TN routes include lowering, DAG construction, physical mapping where applicable, runtime opening, execution and transfers, output materialization and closing. QuEST includes input packing and native evaluation. Circuit parsing, one-time R search, subsequent validation and serialization are excluded. UPMEM policies use their frozen family-specific resource choices; both share the R-selected DAG with NumPy. QuEST evaluates the circuit directly; P8/P1 request eight/one CPU threads. Int8 remains approximate. The logarithmic plot contains 222 timings. Shading marks the six maximum-width cases with no admitted R candidate: UPMEM and NumPy have no runtime there, while both QuEST endpoints remain valid. Shading has no runtime ordinate. T5 summarizes ratios only over common supported widths.")

#pagebreak()
= T1 — Benchmark definitions

#include "generated/tables/table01_workloads.typ"

#pagebreak()
= T2 — Numerical correctness and approximation quality

#include "generated/tables/table02_correctness.typ"

#pagebreak()
= T3 — Calibrated topology selections

#include "generated/tables/table03_resources.typ"

#pagebreak()
= T4 — Path-selection summary

#include "generated/tables/table04_path_selection.typ"

#pagebreak()
= T5 — Final CPU comparison summary

#include "generated/tables/table05_cpu_comparison.typ"

#pagebreak()
= A-F1 — Detailed path-selection results

#image("generated/figures/app01_path_selection.svg", width: 160mm)
#v(3pt)
#text(size: 8.5pt, "Execution speedups on held-out instances from the same six families used in development. All methods use float32, eight tasklets per DPU, complex launch fusion and static-DAG scheduling. Each panel compares its evaluated method with the named reference at the same DPU count: reference median time divided by evaluated median time; right of one is faster. Blue circles denote one DPU, orange squares four. Overall is the family-balanced geometric mean over six families × two configurations. Horizontal segments are the stored descriptive paired-block 95% bootstrap intervals, using 10,000 common resamples of five block IDs; narrow intervals may be hidden by markers. Method aliases share physical samples. Time includes runtime opening, execution of the selected/mapped path, and closing, excluding path search and planning. Inference is conditional on these fixed instances and one paired search-seed schedule. The primary UPMEM-guided/reranking comparison shows no resolved additional benefit; this is not an equivalence test. T4 explains the methods and exact aggregate values.")

#pagebreak()
= A-F2 — Supplemental resource studies

#image("generated/figures/app02_supplemental_resources.svg", width: 160mm)
#v(3pt)
#text(size: 8.5pt, "Stress16 with two layers: tasklet scaling, DPU scaling at eight/24 tasklets per DPU, and cumulative executor changes. All use float32 and greedy paths, with the corresponding configurations and execution-call timing of F1–F3. The scaling panels contain 24 and 14 median-ratio points from five measured blocks, with transformed raw MAD and fixed matched references. The five ablation bars use seven measured blocks and raw MAD scaled by the fixed baseline. Baselines self-normalize exactly. Whiskers describe dispersion, not confidence intervals.")

#pagebreak()
= A-F3 — Supplemental quantization and final comparison

#image("generated/figures/app03_supplemental_quantization.svg", width: 160mm)
#v(3pt)
#text(size: 8.5pt, "The first three panels show 42 matched-resource float32/int8 execution-call ratios for Stress16, Stress18 and GHZ18, using the same timing and execution settings as F4. Values above one favor int8; no ratio uncertainty intervals are inferred. The last panel shows all 20 final Stress timings at four widths, with F5’s cached-path job-to-state boundary and median ± raw MAD on a logarithmic axis. Every median uses five measured blocks. Stress uses two layers; all four widths have admitted R paths. Both final UPMEM policies use 16 DPUs and 24 tasklets per DPU, sharing the R-selected DAG with NumPy. Int8 quality is disclosed in A-T5, including its larger errors on Stress.")

#pagebreak()
= A-T1 — Mechanism qualification and outcomes

#include "generated/tables/app_table01_mechanisms.typ"

#pagebreak()
= A-T2 — One-time search and amortized costs

#include "generated/tables/app_table02_cold_cost.typ"

#pagebreak()
= A-T3 — Campaign accounting

#include "generated/tables/app_table03_accounting.typ"

#pagebreak()
= A-T4 — Tested path-admission frontiers

#include "generated/tables/app_table04_frontiers.typ"

#pagebreak()
= A-T5 — UPMEM numerical-validation detail

#include "generated/tables/app_table05_validation.typ"

#pagebreak()
= A-T6 — Exact cumulative ablation values

#include "generated/tables/app_table06_ablation.typ"
