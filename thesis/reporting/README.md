# Thesis reporting

Simple figure and table scripts read accepted canonical scientific inputs directly:

- [Unified-v4 results](../implementation/thesis_results/unified_final_v4/)
- [Accepted P6 results](../implementation/thesis_results/upmem_cost_guided_path_v1/)

No scientific evidence is copied here. Each script calculates its plot coordinates
in memory and writes only its own final SVG/PNG under `generated/figures/`.
Missing or invalid source data cause an error. These scripts perform no hardware
execution, path search, benchmark execution, or canonical readout generation.

## Run

Use Python ≥3.11 in a separate environment with `requirements.txt`. From the
repository root:

```sh
python -m pip install -r thesis/reporting/requirements.txt
python thesis/reporting/figures/fig01_tasklets.py
python thesis/reporting/figures/fig02_dpus.py
python thesis/reporting/build_all.py
```

The scripts also work from another directory when invoked by their full paths.
The generated files are tracked; rebuilding overwrites only those figure files.
`build_all.py` rebuilds the six main figures. Each can also be run separately.

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
execution-call wall time divided by the same circuit's A0 median; lower values
mean shorter runtime. Each median summarizes seven measured blocks. Whiskers
show raw median absolute deviation divided by the fixed A0 median, describing
runtime dispersion rather than confidence intervals and omitting baseline
uncertainty. A0 self-normalizes to exactly 1× with zero whisker. Execution-call
time includes session opening, execution and transfers, output materialization,
and session closing; it excludes circuit lowering, contraction-path search,
DAG construction and physical mapping. EDC uses 17 qubits; the other families
use 18 qubits. The A0/A4 six-family geometric-mean speedup is approximately 6.25×.

| Step | Configuration |
| --- | --- |
| A0 | D1/T1, serial, unfused |
| A1 | D1/T8, serial, unfused |
| A2 | D4/T8, serial, unfused |
| A3 | D4/T8, serial, complex launch / four-product fusion |
| A4 | D4/T8, static-DAG scheduling, complex launch / four-product fusion |

Fusion refers to combining the real products of complex contractions into
launches, not quantum-gate fusion. These are cumulative configurations rather
than independently estimated contributions from each change.

F3 reads only canonical `unified_final_v4/readout/A.csv` and shows all 30 primary
family/configuration points. The source size is 160 × 115 mm; PNG is 300 dpi.

## F4 — physical quantization runtime

[SVG](generated/figures/fig04_quantization.svg) · [PNG](generated/figures/fig04_quantization.png)

**Caption:** Physical UPMEM execution-call runtime ratios between split-complex
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

## F5 — accepted P6 path-selection comparison

[SVG](generated/figures/fig05_path_selection.svg) · [PNG](generated/figures/fig05_path_selection.png)

**Caption:** Path-selection comparisons from the separate, accepted P6 test
campaign: G is greedy; F selects by FLOP count from FLOP-guided adaptive search;
R selects from the same pool using the UPMEM cost model; U uses that model for
both adaptive generation and selection from its own pool. Both pools also
include the greedy candidate. Each panel shows its numerator's session-inclusive time
divided by its denominator's time; values above 1× favor the denominator method.
Cell estimates are ratios of medians from five measured blocks. Session-inclusive
time sums session opening, execution wall time and session closing; it excludes
search and is not full job-to-state time.

Diamonds show family-balanced geometric ratios for all 12 test cells and for
each six-cell topology group. Circles and squares show the six circuit families
at D1/T8 and D4/T8, respectively. Horizontal segments reproduce the accepted
descriptive paired-block 95% bootstrap intervals, with common block resampling
across methods and cells. Families and cells are fixed, and method aliases that
select the same path share physical samples. The primary comparison is R/U.
Inference is limited to these test cells, five timing blocks and one paired
search-seed schedule. Horizontal axes are logarithmic, with different ranges
per contrast to make the stored intervals legible.

F5 reads canonical P6 `readout/aggregates.csv` and `readout/contrasts.csv`
directly. It displays 12 aggregate and 48 cell estimates across four contrasts;
it does not rerun the bootstrap. The source size is 160 × 165 mm; PNG is 300 dpi.

## F6 — final CPU and UPMEM comparison

[SVG](generated/figures/fig06_final_cpu.svg) · [PNG](generated/figures/fig06_final_cpu.png)

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

F6 reads canonical `unified_final_v4/readout/W.csv`, `final_manifest.json` and
`path_records.json`. It checks the declared 46 selected paths and six no-path
outcomes before drawing the frontier. The source size is 160 × 125 mm;
PNG is 300 dpi.

## Editing boundary

Evidence is immutable; reporting is disposable. A figure task changes its named
script and its generated SVG/PNG. Changes to `common.py`, numerical definitions,
or other figures require a separately scoped task. Never edit evaluation code,
implementation code, accepted evidence, canonical CSVs, selections, paths, or
validation receipts while editing a plot.

Refine one figure at a time after reviewing its output.
Add tables and appendix plots when the text needs them. The existing synthesis
packages remain in place until the new reporting set is integrated into the
manuscript.
