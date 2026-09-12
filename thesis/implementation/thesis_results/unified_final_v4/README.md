# Unified Final Evaluation v4 Evidence

Source: `f6b570a98a610d41b5b16401a42ce12a94042d38`.
Base: `683194cf4895420898297095a0d92e83c282b355`.
Run ID: `unified-v4-20260912T041549Z-73e415abac7b`.

This directory contains the canonical published results of the prospective unified six-family evaluation campaign v4.

## Contents
- `readout/`: Canonical analytical tables (`A.csv`, `D.csv`, `Q.csv`, `T.csv`, `W.csv`, `S.csv`, `aggregates.csv`, `times.csv`, `coverage.csv`, `cold_cost.csv`, `observations.csv`, and `report.md`).
- `manifest/`: Static manifest compilation, counts, case definitions, and calibration view specifications.
- `selection.json`: Deterministic calibration topology selection (14 family/policy winners).
- `path_records.json`: Sealed R-path search records (128 proposals per case for all 52 comparison cases).
- `final_manifest.json`: Materialized and sealed final comparison manifest.
- `calibration_rows.json`: Complete 2,674-slot calibration execution ledger across blocks 0..7.
- `final_rows.json`: Complete 1,560-slot final comparison execution ledger across blocks 0..5.
- `readout/accounting.json`: Derived route/status/reason accounting, R-search outcomes, and actual physical issues.
- `retention.json`: Verification receipt with exact archive paths, sha256 digests, and slot attempt counts.

All raw native worker receipts, issued records, and full statevector reference arrays are permanently retained in two byte-identical independent archives (`archive-A` and `archive-B`). Independent readout regeneration from both archives was verified before publication.

## Reporting correction

Original published result commit: `d886e3b7e04a4c3be4a6d4d463206b66f5c0c2a0`.
The corrected derived readout reports 52 R searches: 46 selected paths and six
`no_selected_R_path` / `no_admitted_candidate` outcomes. Final route issues are
276 each for UPMEM float32, UPMEM int8 and NumPy same-DAG, and 312 each for QuEST
P8 and P1. This gives 1,452 issued final slots, 108 unsupported slots, and 3,334
physical UPMEM issues across qualification, calibration and final evaluation.

`cold_cost.csv` retains all 52 search costs. Its `path_status` and `path_reason`
columns explain unavailable paths; empty execution and amortization fields mean
unavailable, never zero. Supported costs use cached-path job-to-state timings.
The amortized costs and `cold_estimate` are derived estimates, not directly timed
cold executions.

The archives and `retention.json` remain frozen, including their original derived
readouts. Corrected readouts were regenerated into separate directories from both
archives and compared byte-for-byte. The original raw rows, manifests, selections
and sealed paths are unchanged; no campaign measurements or searches were rerun.
The [publication synthesis](../../../synthesis/unified_v4/README.md) consumes the
corrected readout. The branch remains subject to merge review before manuscript use.
