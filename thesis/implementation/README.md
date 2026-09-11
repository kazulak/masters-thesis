# Implementation

Supported deterministic circuits are simulated to a complete pre-measurement statevector
using exact tensor-network contraction and declared finite-precision arithmetic.

Read [architecture](ARCHITECTURE.md), [results](RESULTS.md), and the
[installation/verification guide](../../REPRODUCIBILITY.md).

| Directory | Purpose |
| --- | --- |
| `src/quantum_bench/` | Circuit/TN lowering, planning, execution and evidence |
| `native/` | UPMEM runtime/kernels and QuEST helper |
| `configs/` | Workload and experiment definitions |
| `scripts/` | Qualification and study-specific analysis tools |
| `tests/` | Semantic, numerical, runtime and evidence checks |
| `thesis_results/` | Recorded study artifacts; do not pool distinct studies |

From this directory, with the documented environment installed:

```bash
make help
make PYTHON=../.venv/bin/python test
../.venv/bin/python -m ruff check src tests scripts
```

Manifests use `evidence_manifest_v2`, samples `evidence_sample_v4`, sessions
`evidence_session_v1`, and reports `evidence_report_v5`.
Software checks do not rerun accepted physical measurements. Historical utility
paths and source guards remain unchanged; use their original source when replaying them.
