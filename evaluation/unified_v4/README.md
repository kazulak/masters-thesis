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

The completed v4 hardware campaign is closed. Rebuild readouts directly from each
frozen archive into a new directory; this command performs no workload execution:

```sh
python evaluation/unified_v4/readout.py --campaign /path/to/frozen/archive/run \
  --retention thesis/implementation/thesis_results/unified_final_v4/retention.json \
  --output /new/readout-directory
python thesis/synthesis/unified_v4/build.py --readout /new/readout-directory \
  --output /new/publication-directory
```

Compare the separately regenerated archive-A and archive-B readouts before
publishing. The readout validates sealed inputs, retained byte digests, slot
identities and overlapping native/issued receipt fields. `accounting.json`
distinguishes planned slots, actual issues, route outcomes and R-path admission
frontiers. A readout build alone does not re-verify equality of the archive bytes.
