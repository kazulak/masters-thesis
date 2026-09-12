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
- `retention.json`: Verification receipt with exact archive paths, sha256 digests, and slot attempt counts.

All raw native worker receipts, issued records, and full statevector reference arrays are permanently retained in two byte-identical independent archives (`archive-A` and `archive-B`). Independent readout regeneration from both archives was verified before publication.
