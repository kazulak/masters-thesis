# Documentation Index

This repository is the final publication surface for the completed thesis research.

The documents below are separated into final/current contracts, supporting scientific
milestone records, and historical stable-path records.

Historical files are retained only where they remain useful for scientific provenance or
are referenced by preserved research records. Development-only archive clutter has been
removed from the current tree and remains available in Git history.

## Final/current documents

| Document | Role |
| --- | --- |
| [../README.md](../README.md) | Implementation entry point, final execution profile, commands, and P6 summary |
| [../STATUS.md](../STATUS.md) | Final capability matrix and accepted research state |
| [../ARCHITECTURE.md](../ARCHITECTURE.md) | Final execution architecture and P6 planning architecture |
| [ROADMAP.md](ROADMAP.md) | Closed research roadmap and final disposition of planned mechanisms |
| [RESULTS_INTERPRETATION.md](RESULTS_INTERPRETATION.md) | Thesis-safe interpretation and claim boundaries for accepted results |
| [repository_lineage.md](repository_lineage.md) | Original source/tag lineage and standalone-publication provenance |
| [reset_contract.md](reset_contract.md) | Core software/data/evidence contracts retained by the final implementation |
| [identities.md](identities.md) | Problem, plan, executable, environment, run, session, and sample identities |
| [timing.md](timing.md) | Timing scopes and admissible comparison rules |
| [evidence_workflow.md](evidence_workflow.md) | Evidence verification, reporting, and preservation rules |
| [upmem_kernel_schedule_system_v1.md](upmem_kernel_schedule_system_v1.md) | Detailed final P1-P5 UPMEM execution-system research record |
| [upmem_cost_guided_path_v1.md](upmem_cost_guided_path_v1.md) | Detailed P6 software, calibration, and evaluation record |
| [quantized_contraction_policy_v1.md](quantized_contraction_policy_v1.md) | Shared-scale complex-int8 numerical policy |
| [quantized_upmem_execution_diagnostic_v1.md](quantized_upmem_execution_diagnostic_v1.md) | Physical int8 diagnostic and approximation boundary |
| [upmem_pimutation_workload_reconciliation_v1.md](upmem_pimutation_workload_reconciliation_v1.md) | Final family-aligned workload provenance |
| [upmem_resident_pair_measurement_boundary.md](upmem_resident_pair_measurement_boundary.md) | Bounded residency experiment and measurement boundary |

## Supporting scientific milestone records

These documents describe measured or qualified stages that contribute to the final
research history. They are not open work items.

| Document | Role |
| --- | --- |
| [sequential_upmem_baseline.md](sequential_upmem_baseline.md) | Qualified sequential UPMEM baseline lineage |
| [hierarchical_parallel_diagnostic.md](hierarchical_parallel_diagnostic.md) | Physical tasklet/DPU hierarchical diagnostic |
| [circuit_resource_sensitivity_diagnostic.md](circuit_resource_sensitivity_diagnostic.md) | Circuit/resource sensitivity diagnostic |
| [packed_operation_transport_adoption.md](packed_operation_transport_adoption.md) | Packed-operation transport adoption record |
| [upmem_execution_integration_v1.md](upmem_execution_integration_v1.md) | Integration-stage record leading to the final executor |

## Historical/superseded stable-path records

These records are intentionally retained at their existing paths because older plans,
reports, or provenance material refer to them.

They are not current protocols and must not be resumed.

- [upmem_execution_preparation_v1.md](upmem_execution_preparation_v1.md)
- [upmem_final_system_path_study_v2.md](upmem_final_system_path_study_v2.md)
- [upmem_path_heuristic_generalization_v1.md](upmem_path_heuristic_generalization_v1.md)
- [upmem_path_heuristic_v1.md](upmem_path_heuristic_v1.md)

The authoritative final path result is:

```text
../thesis_results/upmem_cost_guided_path_v1/
```

## Minimal retained archive

The current archive contains only historical material still required by final provenance:

* [archive/README.md](archive/README.md)
* [archive/architecture-reset-2026/THESIS_BENCHMARK_MATRIX.md](archive/architecture-reset-2026/THESIS_BENCHMARK_MATRIX.md)

All other former architecture-reset planning/audit files remain recoverable through Git
history.

## Scientific identities

The authoritative final executor identity is:

```text
459935f586fdd16c82013838e6d27a12604c3093
thesis-upmem-kernel-schedule-system-v1
```

The authoritative P6 identities are:

```text
2beea27411c16e90ed76988613ddb00bcc09f942
thesis-upmem-cost-guided-software-v1

8df2ebac61bacd08309ea490309be5a8dcb943b2
thesis-upmem-cost-guided-results-v1
```
