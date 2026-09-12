# Unified evaluation v4

A prospective six-family campaign on the unchanged `f6b570a…` implementation.
T/D/A/Q share a deduplicated calibration schedule. Family/policy resources are
selected deterministically before fixed-model R paths and fresh final CPU/UPMEM
measurements. Old evidence and P6 remain unchanged.

```sh
python -m unittest discover -s evaluation/unified_v4/tests -v
python evaluation/unified_v4/protocol_core.py compile --out /new/manifest-directory
```

`protocol_core.py` performs no hardware execution. It supplies manifests,
coverage checks, resource selection and final-path binding. The execution adapter
must pass its separate source/SDK/numerical gates before running measurements.
The long operator instructions remain outside this repository.

## Reporting-only regeneration

The completed v4 hardware campaign is closed. The accepted readouts are frozen.
Current presentation uses `python thesis/reporting/build_all.py`; verification uses
`python tools/verify_release.py`. Neither command rebuilds canonical readouts.

For historical inspection only, the readout utility can write a separate scratch
directory from a frozen archive. This is not required for release verification and
must never overwrite accepted evidence:

```sh
python evaluation/unified_v4/readout.py --campaign /path/to/frozen/archive/run \
  --retention thesis/implementation/thesis_results/unified_final_v4/retention.json \
  --output /new/readout-directory
```

The retired synthesis generator is available at the
[historical publication entrypoint](../../thesis/synthesis/unified_v4/README.md).
The readout validates sealed inputs, retained byte digests, slot
identities and overlapping native/issued receipt fields. `accounting.json`
distinguishes planned slots, actual issues, route outcomes and R-path admission
frontiers. A readout build alone does not re-verify equality of the archive bytes.

The [published local validation receipt](validation/reporting-20260912/README.md)
contains the correction commit's original test logs, JUnit results, provenance,
checksums and a verifier. It explicitly distinguishes local validation from
GitHub-hosted CI, and retains both the initial location-dependent test failure
and its successful durable-worktree rerun.
