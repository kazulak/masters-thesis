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

## Editing boundary

Evidence is immutable; reporting is disposable. A figure task changes its named
script and its generated SVG/PNG. Changes to `common.py`, numerical definitions,
or other figures require a separately scoped task. Never edit evaluation code,
implementation code, accepted evidence, canonical CSVs, selections, paths, or
validation receipts while editing a plot.

Review each new figure before proceeding to the next, one figure at a time.
Add tables and appendix plots when the text needs them. The existing synthesis
packages remain in place until the new reporting set is integrated into the
manuscript.
