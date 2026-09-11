# Thesis research material

This directory contains the thesis implementation, literature-review PDF, and
preserved research protocols. The execution-system study and P6 campaign are
complete. Their accepted evidence must not be altered by publication work.

## Navigation

| Material | Purpose |
| --- | --- |
| [Implementation](implementation/README.md) | Supported execution routes and verified commands |
| [Architecture](implementation/ARCHITECTURE.md) | Complex arithmetic, lowering, scheduling, kernels, and timing boundaries |
| [Status](implementation/STATUS.md) | Retained, rejected, bounded, and out-of-scope mechanisms |
| [Documentation index](implementation/docs/README.md) | Current contracts versus historical records |
| [Result-package index](implementation/thesis_results/README.md) | Distinct evidence packages; they are not one pooled experiment |
| [P6 readout](implementation/thesis_results/upmem_cost_guided_path_v1/readout/report.md) | Frozen path-study result |
| [Scoping literature review](Scoping%20Literature%20Review%20Thesis.pdf) | Literature basis for the research |
| [Root reproducibility guide](../REPRODUCIBILITY.md) | Software, evidence, and provenance checks |

## Preserved protocols

The original [plan](upmem-system-and-path-optimization-plan.md),
[v2 plan](upmem-system-and-path-optimization-plan-v2.md), and
[P6 operational runbook](upmem-path-search-operational-runbook-v1.md) remain at
their recorded paths. Their historical instructions and checkpoint-local
"pending" statements do not authorize a new run. The final state is described
by the implementation status and accepted evidence.

## What is not present yet

There is no consolidated thesis-result calculation layer under `publication/`.
Do not use commands from an earlier proposed package as though they were already
implemented here. Existing readout scripts and tables belong to their specific
accepted studies, with their own source identities and measurement scopes.

For installation, start at the repository root and follow
[REPRODUCIBILITY.md](../REPRODUCIBILITY.md). No additional physical execution is
required to verify a documentation change.
