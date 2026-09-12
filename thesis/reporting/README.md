# Thesis reporting

Five main figures and five main tables present the primary results. Three appendix
figures and six appendix tables expose supplementary behaviour, exact values,
numerical quality, planning costs and research decisions.

Standalone scripts read accepted inputs directly from:

- [Unified-v4 results](../implementation/thesis_results/unified_final_v4/)
- [Path-selection results](../implementation/thesis_results/upmem_cost_guided_path_v1/)
- [Historical mechanism ledger](../../evaluation/final_v1/historical_results.csv)

Evidence is immutable; reporting is disposable. No scientific evidence is copied
here. There is no reporting data directory, intermediate CSV or statistical cache.
Scripts calculate values in memory and write only their named SVG/PNG or Typst
presentation files. Missing or invalid inputs cause an error. They never run
hardware, benchmarks, path searches or canonical readout generation.

## Build and review

Use Python ≥3.11 in a separate environment with `requirements.txt`. From the
repository root:

```sh
python -m pip install -r thesis/reporting/requirements.txt
python thesis/reporting/build_all.py
typst compile --root . thesis/reporting/review.typ /tmp/thesis-reporting-review.pdf
```

`build_all.py` explicitly invokes eight figure and eleven table scripts. Each can
also run independently, for example:

```sh
python thesis/reporting/figures/fig04_quantization.py
python thesis/reporting/tables/table04_path_selection.py
```

Python scripts work from any directory when invoked by absolute path. Generated
SVG/PNG and Typst table fragments are tracked. The PDF above is a local review
artifact, not a repository file. The [review document](review.typ) supplies titles,
captions and main/appendix numbering; it is not the thesis manuscript.
Typst 0.13.1 and DejaVu fonts are used for the review.

The final CPU figure is now F5 (`fig05_final_cpu`); the detailed path forest is
A-F1 (`app01_path_selection`). Their previous `fig06_final_cpu` and
`fig05_path_selection` entrypoints have been replaced, without changing plotted
values. F1–F4 retain their existing scripts and outputs.

## F1 — tasklet scaling

[SVG](generated/figures/fig01_tasklets.svg) · [PNG](generated/figures/fig01_tasklets.png)

**Caption:** Tasklet scaling across the six primary circuit families on one
physical DPU, using float32, serial unfused execution. Points show each circuit's
median execution-call wall time at one tasklet divided by its median at the
indicated tasklet count. This time includes opening the UPMEM session, execution
and transfers, output materialization, and closing the session. Circuit lowering,
contraction-path search, DAG construction and physical mapping are excluded.
Each median summarizes five measured blocks. Whiskers transform runtime median
± raw median absolute deviation with the one-tasklet median held fixed. They
describe runtime dispersion, not confidence intervals, and omit baseline
uncertainty. The one-tasklet point self-normalizes to exactly 1× with zero
whisker. EDC uses 17 qubits; the other families use 18 qubits. The dashed
horizontal line marks 1×.

F1 reads only canonical `unified_final_v4/readout/T.csv` and shows all 144 primary
family/tasklet points. Supplementary Stress results are not part of this figure.
The source size is 160 × 105 mm; PNG export is 300 dpi.

## F2 — DPU scaling

[SVG](generated/figures/fig02_dpus.svg) · [PNG](generated/figures/fig02_dpus.png)

**Caption:** DPU scaling across the six primary circuit families within one
physical rank, using float32, static-DAG scheduling and complex launch /
four-product fusion. Contraction paths use the declared greedy algorithm.
Points show median execution-call wall time at one DPU divided by its median at
the indicated DPU count, with tasklets per DPU held at 8 or 24. Each series uses
its own one-DPU baseline; the relative heights do not compare absolute T8 and
T24 runtimes. Execution-call time includes opening the UPMEM session, execution
and transfers, output materialization, and closing the session. Circuit lowering,
contraction-path search, DAG construction and physical mapping are excluded.
Each median summarizes five measured blocks. Whiskers transform runtime median
± raw median absolute deviation with the matched one-DPU median held fixed.
They describe runtime dispersion, not confidence intervals, and omit baseline
uncertainty. One-DPU points self-normalize to exactly 1× with zero whiskers.
EDC uses 17 qubits; the other families use 18 qubits. The horizontal dashed line
marks 1×; the DPU-count axis is logarithmic with base 2.

F2 reads only canonical `unified_final_v4/readout/D.csv` and shows all 84 primary
family/topology points. Supplementary Stress results are not part of this figure.
The source size is 160 × 110 mm; PNG export is 300 dpi.

## F3 — cumulative implementation changes

[SVG](generated/figures/fig03_ablation.svg) · [PNG](generated/figures/fig03_ablation.png)

**Caption:** Cumulative implementation changes across the six primary circuit
families, using float32 and greedy contraction paths. Bars show median
execution-call wall time as a percentage of the same circuit's serial baseline;
lower bars mean shorter runtime. Each step retains the preceding changes. Each
median summarizes seven measured blocks. Whiskers show raw median absolute
deviation scaled by the fixed baseline median, describing runtime dispersion
rather than confidence intervals and omitting baseline uncertainty. The baseline
self-normalizes to exactly 100% with zero whisker. Execution-call
time includes session opening, execution and transfers, output materialization,
and session closing; it excludes circuit lowering, contraction-path search,
DAG construction and physical mapping. EDC uses 17 qubits; the other families
use 18 qubits. The baseline-to-final six-family geometric-mean speedup is
approximately 6.25×.

| Plot label | Configuration |
| --- | --- |
| Baseline | 1 DPU, 1 tasklet, serial, unfused |
| 8 tasklets | 1 DPU, 8 tasklets, serial, unfused |
| 4 DPUs | 4 DPUs, 8 tasklets per DPU, serial, unfused |
| Launch fusion | 4 DPUs, 8 tasklets per DPU, serial, complex launch / four-product fusion |
| DAG | 4 DPUs, 8 tasklets per DPU, static-DAG scheduling, complex launch / four-product fusion |

Fusion refers to combining the real products of complex contractions into
launches, not quantum-gate fusion. These are cumulative configurations rather
than independently estimated contributions from each change. These five steps
correspond to A0–A4 in the canonical evidence.

F3 reads only canonical `unified_final_v4/readout/A.csv` and shows all 30 primary
family/configuration points. The source size is 160 × 115 mm; PNG is 300 dpi.

## F4 — physical quantization runtime

[SVG](generated/figures/fig04_quantization.svg) · [PNG](generated/figures/fig04_quantization.png)

**Caption:** Physical UPMEM execution-call wall-time ratios between split-complex
float32 and complex int8 with shared scaling. Each ratio divides the float32
median by the int8 median for the same circuit, DPU count and tasklets per DPU;
values above 1× favor int8. Both policies use static-DAG scheduling, complex
launch / four-product fusion and the declared greedy path algorithm. Each
median summarizes five measured blocks. Ratios of medians are shown without
uncertainty intervals. Execution-call time includes session opening, execution
and transfers, output materialization, and session closing; circuit lowering,
contraction-path search, DAG construction and physical mapping are excluded.
EDC uses 17 qubits; the other families use 18 qubits. The horizontal line marks
equal runtimes. DPU count uses a logarithmic axis with base 2.

The plot covers all declared primary topologies without filtering by a post-hoc
approximation-quality threshold. Int8 is an approximate numeric policy;
runtime ratios do not imply equal numerical accuracy. Canonical validation
measurements are retained in
[observations.csv](../implementation/thesis_results/unified_final_v4/readout/observations.csv).
Resource selection used the frozen execution/correctness contract and no
post-hoc approximation-quality tuning.

F4 reads only canonical `unified_final_v4/readout/Q.csv`; 168 timing medians
produce 84 matched-policy ratios. The source size is 160 × 110 mm; PNG is 300 dpi.

## F5 — final CPU and UPMEM comparison

[SVG](generated/figures/fig05_final_cpu.svg) · [PNG](generated/figures/fig05_final_cpu.png)

**Caption:** Final five-route comparison across the six primary circuit families
and eight declared widths per family. Points show median cached-path job-to-state
time in seconds from five measured blocks; whiskers show raw median absolute
deviation, describing dispersion rather than confidence intervals. The elapsed
time runs from a preloaded circuit to an owned statevector. For TN routes it
includes lowering, DAG construction, physical mapping where applicable, session
opening, execution and transfers, output materialization, and session closing.
For QuEST it includes input packing and the native evaluation call. Circuit
parsing, one-time R-path search, subsequent validation and result serialization
are excluded. The time axis is logarithmic.

UPMEM float32 and int8 use their frozen, family-specific selected topologies.
Both UPMEM policies and NumPy use the shared float32-R-selected contraction DAG;
QuEST evaluates the circuit directly. P8 and P1 request eight and one CPU threads,
respectively. Int8 uses approximate arithmetic; its runtime curve does not imply
float32-equivalent accuracy.

Shading marks the largest declared width in each family, where no R candidate
satisfied the admission contract (`no_selected_R_path / no_admitted_candidate`).
The two UPMEM routes and NumPy same-DAG have no execution at those six endpoints;
both QuEST routes retain their valid measurements there. Shading has no numerical
runtime coordinate and does not represent an MRAM limit or execution failure.
The plot contains 48 median timings per QuEST route and 42 per R-dependent route,
for 222 total. EDC spans 7–25 qubits; the other families span 8–26 qubits.

F5 reads canonical `unified_final_v4/readout/W.csv`, `final_manifest.json` and
`path_records.json`. It checks the declared 46 selected paths and six no-path
outcomes before drawing the frontier. The source size is 160 × 125 mm;
PNG is 300 dpi.

## Main tables

All tables read frozen sources directly. Source links in generated fragments pin
the accepted evaluation merge, or the historical revision named in its ledger.

| Table | Generated Typst | Definition |
| --- | --- | --- |
| T1 — Benchmark definitions | [table01_workloads.typ](generated/tables/table01_workloads.typ) | Six circuit meanings, constructor parameters, allocated-qubit formulas and calibration cases. Family alignment does not assert exact PIMutation instance reproduction. |
| T2 — Numerical correctness | [table02_correctness.typ](generated/tables/table02_correctness.typ) | Worst errors across all issued, non-warmup primary-family UPMEM calibration and final observations, deduplicated by physical slot. Float32 validation and int8 approximation/replay are distinguished. |
| T3 — Selected resources | [table03_resources.typ](generated/tables/table03_resources.typ) | Frozen family/policy DPU and tasklet choices from `selection.json`, transferred unchanged from calibration to the final sweep. |
| T4 — Path-selection results | [table04_path_selection.typ](generated/tables/table04_path_selection.typ) | Four method/reference contrasts at one DPU, four DPUs and Overall, with stored descriptive paired-block 95% bootstrap intervals. |
| T5 — Final CPU comparison | [table05_cpu_comparison.typ](generated/tables/table05_cpu_comparison.typ) | Both UPMEM policies divided by each of QuEST P8, QuEST P1 and NumPy same-DAG; geometric means across seven common supported widths, then equal weight per family for Overall. |

T2 uses 245 float32 and 105 int8 measured observations per primary family. The
float32 relative-L2 limit is 1e-5 and norm-drift limit 2e-5, with elementwise
absolute/relative tolerances 1e-5. Int8 has no post-hoc approximation-quality
threshold. Its retained execution/replay status does not imply float32 accuracy.
The supplementary Stress18 final int8 relative-L2 maximum is about 8.69%; A-T5
discloses it alongside the primary families.

T4 uses reference/evaluated execution time, so values above one favor the evaluated
method. All methods use float32, eight tasklets per DPU, complex launch fusion and
static-DAG scheduling. The overall speedups are approximately 1.217× (FLOP-guided
versus greedy), 1.039× (reranking versus FLOP-guided), 1.001× (UPMEM-guided versus
reranking), and 1.267× (UPMEM-guided versus greedy). The UPMEM-guided/reranking
interval spans one: no additional benefit is resolved, and no statistical
equivalence or universal per-circuit improvement is claimed. Search and planning
are excluded from these execution times. The accepted study uses held-out
instances from the same six families, five timing blocks and one paired
search-seed schedule; its 10,000 block resamples use the same draws across
methods and circuit/configuration combinations.

T5 uses the opposite orientation: UPMEM/CPU runtime, so values above one mean
UPMEM is slower. Each family contributes seven per-width ratios of median
cached-path job-to-state time; their geometric mean includes small widths and
must not be interpreted as the largest-width result. Overall weights families
equally. The six no-path widths are excluded from these matched ratios while
their valid CPU results remain visible in F5. Policy-specific resource selections
may differ. No new uncertainty intervals are inferred for this descriptive table.

## A-F1 — detailed path selection

[SVG](generated/figures/app01_path_selection.svg) · [PNG](generated/figures/app01_path_selection.png)

**Caption:** Execution speedup from contraction-path selection on held-out circuit instances
from the same six families used in development. All methods use float32, eight
tasklets per DPU, complex launch fusion and static-DAG scheduling. Each panel names the
method being evaluated and its reference method. Speedup divides the reference
method's median execution time by the evaluated method's median: points to the
right of 1× indicate faster execution, and points to the left indicate slower
execution. All panels use the same linear 0.5–3.0× scale. Each median summarizes
five measured blocks.

Time includes opening the runtime, executing the already selected and mapped
path (host work, transfers and kernels), and closing the runtime. Path search
and logical/physical planning are excluded. This is the accepted
`session_inclusive_s` metric, not full job-to-state time.

The highlighted black diamond and bold value show the family-balanced geometric
mean speedup across all six families and both DPU configurations. These are
12 circuit/configuration combinations, with equal weight per family. The next
two rows summarize each DPU configuration across the six families. Blue circles
denote one DPU; orange squares denote four DPUs, for both summary and per-circuit
rows. Horizontal segments are the accepted descriptive paired-block 95%
bootstrap intervals, based on 10,000 common resamples of the five block IDs
across all methods and circuit/configuration combinations. Narrow intervals can
be smaller than their markers on the shared scale. Aliases selecting the same
path share physical measurements and do not add independent observations.

FLOP-guided search selects by FLOP count from an adaptive candidate pool.
Cost-model reranking selects from that same pool using the UPMEM cost model.
UPMEM-guided search uses that model for both adaptive generation and selection
from its own pool. Both pools include the greedy candidate. The declared primary
comparison is UPMEM-guided search against cost-model reranking (panel c).
Inference is limited to the fixed test circuits, five timing blocks and one
paired search-seed schedule; these intervals do not establish robustness across
new circuits or search seeds.

A-F1 reads `readout/aggregates.csv` and `readout/contrasts.csv` directly from the
[accepted path-selection package](../implementation/thesis_results/upmem_cost_guided_path_v1/).
It displays 12 aggregate and 48 individual circuit/configuration estimates
across four contrasts; it does not rerun the bootstrap. The source size is
160 × 165 mm; PNG is 300 dpi.

## A-F2 — supplemental resource studies

[SVG](generated/figures/app02_supplemental_resources.svg) · [PNG](generated/figures/app02_supplemental_resources.png)

**Caption:** Stress16 with two layers: tasklet scaling on one DPU, DPU scaling
at eight/24 tasklets per DPU, and cumulative executor changes. The three panels
use the same execution-call timing boundaries and definitions as F1, F2 and F3.
Tasklet/DPU speedups use their matched one-tasklet/one-DPU median as a fixed
reference and transform median ± raw MAD; reference points self-normalize to one.
Ablation bars show runtime as a percentage of the serial one-DPU/one-tasklet
baseline, retaining each preceding change; whiskers are raw MAD scaled by that
fixed baseline. Five measured blocks support scaling medians and seven support
ablation medians. These whiskers describe dispersion, not confidence intervals.

The script reads `T.csv`, `D.csv` and `A.csv` directly: 24 tasklet points,
14 DPU points and five ablation bars. All use float32 and greedy paths. Tasklet
scaling is serial/unfused; DPU scaling uses launch fusion/static-DAG scheduling.
The source size is 160 × 190 mm; PNG is 300 dpi.

## A-F3 — supplemental quantization and final comparison

[SVG](generated/figures/app03_supplemental_quantization.svg) · [PNG](generated/figures/app03_supplemental_quantization.png)

**Caption:** Physical int8 performance for Stress16, Stress18 and GHZ18 across
matched DPU counts and eight/24 tasklets per DPU, followed by the five-route final
Stress width comparison. Quantization panels use float32/int8 execution-call
median-time ratios and a common range; values above one favor int8. They share
F4's greedy-path, fused static-DAG execution settings and show no uncertainty
intervals. The final panel uses cached-path job-to-state medians ± raw MAD in
seconds on a logarithmic axis, sharing F5's timing boundary. Every median uses
five measured blocks. Stress uses two layers. All four final Stress widths have
admitted paths and all five routes are present.

The quantization panels contain 42 ratios from 84 `Q.csv` rows. The final panel
contains 20 timings from `S.csv` at 8, 12, 16 and 18 qubits. Final UPMEM routes use
the frozen Stress calibration selections (16 DPUs, 24 tasklets for both policies)
and share the R-selected DAG with NumPy; QuEST evaluates the circuit directly.
Int8 remains approximate, with quality disclosed in A-T5. The source size is
160 × 145 mm; PNG is 300 dpi.

## Appendix tables

| Table | Generated Typst | Definition |
| --- | --- | --- |
| A-T1 — Mechanism outcomes | [app_table01_mechanisms.typ](generated/tables/app_table01_mechanisms.typ) | Eight scoped historical/current comparisons. Historical values retain their provenance and claim limits; current fusion/DAG ratios come from A.csv. |
| A-T2 — Search and amortized costs | [app_table02_cold_cost.typ](generated/tables/app_table02_cold_cost.typ) | All 52 searches, float32 cached execution, and derived per-use costs for 1/10/100 uses. Unsuccessful searches retain search cost and show execution/amortization as unavailable. |
| A-T3 — Campaign accounting | [app_table03_accounting.typ](generated/tables/app_table03_accounting.typ) | Backend-specific qualification, calibration, five final routes, physical ceiling, path outcomes and two retained archives. Counts include warmups. |
| A-T4 — Path frontiers | [app_table04_frontiers.typ](generated/tables/app_table04_frontiers.typ) | Largest admitted and first tested no-path width for each primary family; no continuous-width or MRAM-limit claim. |
| A-T5 — Numerical-validation detail | [app_table05_validation.typ](generated/tables/app_table05_validation.typ) | All 110 UPMEM case/policy/phase groups, including supplementary workloads; configuration/sample counts, replay/validation and observed error extrema. |
| A-T6 — Exact ablation values | [app_table06_ablation.typ](generated/tables/app_table06_ablation.typ) | All 35 configurations across six primary families and Stress16: median, raw MAD, percentage of baseline and baseline/configuration speedup. |

Historical mechanism effects are not multiplied into a cumulative speedup. The
WRAM staging microcase has separate kernel and inclusive effects; outer-K1 and
residency were not adopted for their tested scopes, and slicing plus scheduling
had mixed results. No unverified chat transcription is promoted to a measurement.

Cold estimates use T_cached + T_search/k, where T_cached is the float32 final
cached-path job-to-state median. They are derived estimates, not new timed cold
executions. No-path outcomes preserve their real search cost and no runtime is
invented. Accounting preserves 46 selected paths plus six no-path outcomes,
1,560 final planned / 1,452 issued / 108 not issued, 3,334 physical UPMEM issues
within the 3,406 ceiling, and 8,288 files in each of two retained archives.

## Editing boundary

A future figure task changes its named script and generated SVG/PNG; a table task
changes its named script and Typst fragment. Shared definitions require an
explicitly broader task. Never edit accepted evidence, evaluation/implementation
code, canonical CSVs, selections or paths while editing a presentation.

The existing synthesis packages remain until the new reporting set is integrated
into the manuscript. This package does not add a timing-decomposition figure or
turn accounting, correctness and historical decisions into decorative plots.

## Local validation receipt — 2026-09-12

The package was validated against reporting base
`54af8ceb1675b49f2c881a55778c082335c28028` and accepted evaluation merge
`c7c6cac0b55bdff2f4c24b70397b36f89bedc45f`. These are local validation results,
not hosted CI results.

```sh
python -Werror::ResourceWarning -m unittest discover -s thesis/reporting/tests -v
python -m ruff check thesis/reporting
python -Werror::ResourceWarning thesis/reporting/build_all.py
typst compile --root . thesis/reporting/review.typ /tmp/thesis-reporting-review.pdf
```

- All 13 reporting regression tests passed, including warmup exclusion, physical
  slot deduplication, resource choices, ratio orientation, common-width summaries,
  no-path execution remaining unavailable, and archive-count consistency.
- Ruff passed. All 19 scripts built successfully with resource warnings treated
  as errors. Rebuilding from the repository root and from `/tmp` produced
  byte-identical contents for all 27 generated SVG, PNG and Typst files, using
  NumPy 2.3.5 and Matplotlib 3.10.8 from the pinned requirements.
- Independent calculations checked the 2,100 primary measured UPMEM observations,
  frozen topology selections, all 12 path-summary ratios and 24 bootstrap interval
  endpoints, and all 222 primary final timing medians plus 42 CPU-summary ratios.
  Supplemental plotted coordinates were checked against their canonical rows.
- The 22-page review compiled with Typst 0.13.1. New figures and all tables were
  visually inspected at 160 mm width, including continuation headers; PDF text
  bounds were checked for clipping.
- All 1,264 tracked evaluation/implementation files matched their initial hashes
  and the reporting base. F1–F4 scripts and SVG/PNG outputs remained byte-identical.
  All changes are confined to `thesis/reporting/`.
