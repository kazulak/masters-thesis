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
