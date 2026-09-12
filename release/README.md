# Master's thesis research artifact 1.0.0

The `thesis-artifact-v1.0.0` release freezes the implementation, accepted evidence,
and current figures/tables. It is the research artifact, not the complete thesis
manuscript. The 22-page reporting review is included as a convenience.

## Repository layers

- `evaluation/`: the recorded protocols, evaluators, readouts and validation.
- `thesis/implementation/thesis_results/`: immutable accepted packages.
- `thesis/reporting/`: standalone presentation scripts reading accepted files directly.

The current synthesis directories contain historical pointers only. Their former
framework, duplicated publication CSVs and obsolete assets remain in Git history.
The review consumes only current reporting outputs. No evidence is copied into reporting.

## Verify a release without rerunning experiments

Use a full-history clone with scientific tags. GitHub's automatic source ZIP does
not include the history required for provenance verification.

```sh
git clone --recurse-submodules https://github.com/kazulak/masters-thesis.git
cd masters-thesis
git checkout thesis-artifact-v1.0.0
python3 tools/verify_release.py --repo . --output /tmp/compact-evidence.json
mkdir -p /tmp/thesis-release-download
gh release download thesis-artifact-v1.0.0 --repo kazulak/masters-thesis \
  --dir /tmp/thesis-release-download
(cd /tmp/thesis-release-download && sha256sum -c SHA256SUMS)
python3 tools/verify_release.py --repo . --archives /tmp/thesis-release-download \
  --output /tmp/raw-evidence.json
```

The verifier requires Python 3.10 or newer and the standard library. It reads
existing bytes, checks 920 accepted files, all 12 package checksum manifests,
scientific commit/tag reachability, derived campaign accounting, and optionally
all eleven raw archives and every member. It never extracts archives or runs
hardware, benchmarks, path search or canonical readout generation. Without
`--archives`, it explicitly reports raw evidence as **NOT CHECKED**.

The downloadable `repository.bundle` retains full main history and the scientific
tags. It can be cloned with `git clone repository.bundle artifact`; submodules
must still be fetched from their pinned upstream repositories. The release index
and SHA256SUMS cover the uploaded assets. GitHub's automatic source archives are
not the raw measurement archives.

## Evidence and source identities

[provenance.json](provenance.json) lists the original implementation, evaluator,
result and correction commits and all preserved scientific tags. Release utility
hardening is not the implementation used to execute the frozen measurements.
The original result SHA is `d886e3b7e04a4c3be4a6d4d463206b66f5c0c2a0`.
The correction is `cbd3817f0f775bbe1a1e1d7e5281333706d9aaa6`; its repository receipt
was published in `d6b6c980e18a6c0249834a3a3e5eb11433c4a96a` at
[evaluation/unified_v4/validation/reporting-20260912](../evaluation/unified_v4/validation/reporting-20260912/README.md).
The previously mentioned implementation/runs receipt path was not published.

The accepted final counts are 1,560 planned / 1,452 issued and successful / 108
not issued. UPMEM float32, int8 and NumPy each issued 276 slots; QuEST P8/P1 each
issued 312. There are 46 selected R paths and six no-admitted-candidate frontiers.
Physical UPMEM issues total 108 + 2,674 + 552 = 3,334 within the 3,406 ceiling.
The 72 unissued final physical allocations are a subset of the 108 unsupported
final slots. Int8 remains approximate and was not tuned against a post-hoc
quality threshold. No new physical measurements were made for the release.

The [raw archive index](raw-archives.json) binds eleven assets to their accepted
retention/digest records. The unified archive packages 8,288 regular files from
one verified retained copy; both original retained copies have identical hashes
and remain outside Git. They are separate directories/inodes on the same local
filesystem, not independent geographic backups. The public release provides an
additional retained location. The four path-study and six final-v1 archives keep
their existing compressed bytes. The new unified tarball preserves every source
file byte, uses sorted names, normalized owner/mode/mtime and gzip mtime zero.
[Per-file inventories](archive-files/) permit verification without extraction.

The raw unified archive contains the original execution-era readouts. Later
reporting corrections exist in the committed canonical package; both versions
are retained deliberately. Use committed corrected canonical readouts for
reporting. Do not overwrite the raw archive or rebuild its historical readout.

Two historical nested SHA256SUMS files name `accepted_evaluation_rows.json`, whose
accepted repository representation is `.json.gz`. The verifier hashes the
**decompressed** bytes only for those two declared paths. Both resolve to
40,235,178 bytes with SHA-256
`a3f94ca646c2a59c8a4989ef0c954bff6b3cbec39e8f5c6c02483678822dc01e`.
This is a representation exception, not a skipped checksum. Frozen manifests
remain unchanged.

## Rebuild the presentation and run software checks

[REPRODUCIBILITY.md](../REPRODUCIBILITY.md) gives the commands. Rendering uses
Python 3.13.15, [requirements.lock](../thesis/reporting/requirements.lock), Typst
0.13.1 and the [font/runtime fingerprint](rendering-environment.json). CI checks
the environment, rebuilds all 27 tracked outputs without changes and compiles
the review. Review PDF binary identity is not asserted across runs; its sources,
rendering environment and the distributed PDF digest are recorded.

[The audit](AUDIT.md) and [local validation receipts](validation/README.md) state
exact coverage and limitations. GitHub CI publishes separate software,
evaluation-contract and reporting receipts. SDK-dependent skips are disclosed;
a green hosted check does not claim physical qualification. The release validation
asset retains hosted receipts beyond the Actions retention period.

## Freeze and maintenance policy

The release uses a normal merge to preserve all audited ancestors and an annotated
tag. Main requires the three CI jobs and pull-request review flow; force-push and
branch deletion are disabled. Only main remains active after release cleanup.
The repository remains available for future documentation work. Immutable release
assets and the tagged revision remain the citation target; future corrections
need a new version, not replacement evidence or a moved tag.

Accepted packages, calibration/final rows, selections, paths and canonical CSVs
are immutable. A reporting task changes only its scripts and generated outputs.
Missing inputs fail visibly. Historical operator commands require their recorded
source checkout and are not release-reproduction instructions.

Original code uses MIT; original outputs use CC BY 4.0, subject to
[third-party exceptions](../THIRD_PARTY.md). No DOI or full-manuscript submission
status is claimed. This audit checks retained evidence and reproducibility; it
is not an independent rerun of hardware or an exhaustive legal/security review.
