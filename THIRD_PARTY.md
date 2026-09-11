# Third-Party Software

No new project-wide open-source license is declared for this standalone thesis snapshot.

Third-party components retain their own upstream copyright and licensing terms.

## Git submodules

### QuEST

```text
path:
thesis/implementation/external/QuEST

upstream:
https://github.com/quest-kit/QuEST.git

pinned commit:
9d7618d7263e3bfba433b88cf1eac0647f08fa0a
```

QuEST is used as a full-state quantum-simulation baseline dependency.

Consult the upstream QuEST repository for its license and attribution requirements.

### SimplePIM

```text
path:
thesis/implementation/external/SimplePIM

upstream:
https://github.com/CMU-SAFARI/SimplePIM.git

pinned commit:
1d639c53532555f01e9f71d872e7712b166d6cba
```

The final thesis implementation uses bounded SimplePIM management/initialization components around the UPMEM runtime; it does not claim SimplePIM as the complete final execution scheduler.

Consult the upstream SimplePIM repository for its license and attribution requirements.

### PID-Comm

```text
path:
thesis/implementation/external/PID-Comm

upstream:
https://github.com/AIS-SNU/PID-Comm.git

pinned commit:
cecc39e29e6576ced73b2041db6e357769a6531a
```

PID-Comm is retained as qualification/provenance material and is not the active final communication provider.

Consult the upstream PID-Comm repository for its license and attribution requirements.

## External system dependency

UPMEM SDK/runtime components are external system dependencies and are not redistributed by this repository as a project-wide licensed component.

Historical physical experiments recorded the exact UPMEM SDK version used by each accepted campaign.

## Python and system packages

Python packages and system libraries installed through package managers are not vendored by this repository unless explicitly tracked.

Each dependency retains its own upstream license.

## License policy for this snapshot

The absence of a project-wide `LICENSE` file is intentional in Chunk 2.

Do not infer that third-party licenses are replaced by the status of this parent repository.

A future explicit licensing review may add a project-wide license only after ownership and compatibility of all retained original/adapted source has been reviewed.
