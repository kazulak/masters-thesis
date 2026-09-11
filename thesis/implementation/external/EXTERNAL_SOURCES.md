# External Submodules

Active external source dependencies are Git submodules under:

```text
thesis/implementation/external/
```

They are pinned to exact commits.

They are not vendored copies.

## Setup

From the standalone repository root:

```bash
git submodule update --init --recursive
```

Or explicitly:

```bash
git submodule update --init --recursive   thesis/implementation/external/QuEST   thesis/implementation/external/SimplePIM   thesis/implementation/external/PID-Comm
```

## Registry

| Path         | Upstream                                      | Pinned commit                              | Final thesis role                                                                                       |
| ------------ | --------------------------------------------- | ------------------------------------------ | ------------------------------------------------------------------------------------------------------- |
| `QuEST/`     | `https://github.com/quest-kit/QuEST.git`      | `9d7618d7263e3bfba433b88cf1eac0647f08fa0a` | CPU/full-state benchmark dependency                                                                     |
| `SimplePIM/` | `https://github.com/CMU-SAFARI/SimplePIM.git` | `1d639c53532555f01e9f71d872e7712b166d6cba` | Bounded management/initialization dependency around the UPMEM runtime; not the complete final scheduler |
| `PID-Comm/`  | `https://github.com/AIS-SNU/PID-Comm.git`     | `cecc39e29e6576ced73b2041db6e357769a6531a` | Retained qualification/provenance source; not the active final communication provider                   |

ATiM and SparseP remain research references only and are not active standalone submodules.

## Update policy

The thesis research is frozen.

Do not update submodule commits in this repository merely because newer upstream versions exist.

A submodule update would define a new software version and must not be mixed with the accepted thesis evidence.

## Licensing

Each submodule retains its upstream license and attribution requirements.

See the repository-root `THIRD_PARTY.md`.
