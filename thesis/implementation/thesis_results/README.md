# Evidence packages

Read [RESULTS.md](../RESULTS.md) for the scientific synthesis.
This directory contains distinct studies, not a combined benchmark.

| Package | Role |
| --- | --- |
| [unified_final_v4](unified_final_v4/README.md) | Authoritative final six-family calibration, selected resources, paths and CPU/UPMEM width sweep |
| [upmem_cost_guided_path_v1](upmem_cost_guided_path_v1/README.md) | Supporting accepted path-selection study, fit profiles and readout |
| [final_evaluation_v1](final_evaluation_v1/README.md) | Historical calibration/final package; superseded as the headline dataset |
| `quantized_contraction_policy_v1/` | Numerical-policy characterization |
| `upmem_execution_integration_v1/` | Integration evidence |
| `physical_hardware_mvp_v1/`, `physical_simplepim_taskgraph_m4_5/` | Earlier physical functionality |
| `current/` | Historical CPU/GPU/TN and simulator snapshot; not the final result set |
| `planner_v2/` | Historical model-only results |
| `upmem_path_heuristic_v1/`, `upmem_path_heuristic_generalization_v1/` | Superseded studies and retained test inputs |

Per-study packages are unchanged. Old paths/status fields describe their recorded
source, not current instructions. Raw archives are separate from their digests.
The [artifact release](../../../release/README.md) publishes eleven raw archives
and a read-only verifier. Current plots and tables live in [reporting](../../reporting/README.md).
