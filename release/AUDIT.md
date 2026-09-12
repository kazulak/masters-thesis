# Repository audit and release disposition — 2026-09-12

The accepted science and corrected presentation passed the audit. Release changes
address reproducibility, defensive utilities, documentation and retention. No
hardware measurement, calibration row, final row, selection, path or canonical
CSV was altered. This is a research artifact release, not manuscript completion.

## Scope and baseline

The audited reporting head was `a2a5b534ccc562f0448e76912e144c0a3e6f7e96`, on top of
accepted evaluation merge `c7c6cac0b55bdff2f4c24b70397b36f89bedc45f`.
The audit covered source/branch/tag reachability, all accepted packages and
checksum manifests, both unified archive copies, ten historical raw tarballs,
accounting joins, rendering calculations and output, tests/CI, build dependencies,
current documentation, licensing and repository cleanup. See provenance.json for
source identities and validation/ for retained receipts.

The pre-change suites passed 2,697 distinct tests: implementation 2,489; unified
87; final-v1 40; reporting 13; old synthesis 51; old unified publication 7; path
readout 5; native CPU 5. The initial prerequisite-limited run and successful full
implementation rerun are both retained. This is local software/simulator evidence,
not a new hardware qualification or an independently reproduced campaign.

## Findings and implemented remedies

| Finding | Evidence / consequence | Release remedy |
| --- | --- | --- |
| Stale root navigation | Earlier path study described as the final dataset | Unified-v4 is explicitly authoritative; historical studies remain scoped |
| Two publication systems | Obsolete intermediate CSVs, 54 old diagnostic plots, superseded v4 assets | Current reporting retained; 199 obsolete synthesis files removed, two historical README pointers kept |
| Missing current hosted receipts | Prior correction receipt was local, original cited path absent | Published correction receipt retained at its actual evaluation/validation path; CI now retains source identities, logs and JUnit for three jobs |
| CI omitted newer contracts/reporting | Main CI previously covered implementation and older path audit | Added final-v1, unified-v4, release verifier, path and reporting checks; deterministic rebuild and Typst review |
| Bootstrap omitted path extras | Generic environment could omit declared path-search dependencies | Install `.[dev,path-search]`, covered by existing bootstrap tests |
| Invalid accuracy scalars | NaN/nonfinite/negative or malformed metrics could evade normal comparisons | Reject them before unchanged declared tolerances; valid boundary and invalid-scalar regressions |
| Historical archive extractor trusted types | Path checks alone did not reject links and special members | Validate complete member list, types, root, duplicates and file/parent conflicts before extraction; reject reused destinations |
| Table validation overconstrained bootstrap | A percentile interval need not contain the point estimate | Require finite positive estimate/endpoints and ordered interval only; accepted numbers unchanged |
| Rendering environment incomplete | Top-level versions alone omitted transitive packages/font bytes | Exact Python/package lock, FreeType/font fingerprint and pinned Typst archive |
| Raw evidence only locally retained | Repository digests alone could not provide archive bytes | Eleven public raw assets, outer hashes and complete member inventories, streaming verification without extraction |
| Missing project licensing/citation | Reuse terms unclear | MIT original code, CC BY 4.0 original outputs, explicit upstream exceptions/notices, CFF citation |
| Multiple active branches/worktrees | Clean freeze required preserving user work and historical SHAs | Private full Git/work backup first; normal merge, scientific tags retained, cleanup only after release verification |

The release verifier reads evidence only and performs no repairs. The narrow
qualification/extraction fixes are present-day defensive utilities, not the source
used for the completed physical campaign. Readout and numerical thresholds are
unchanged. Later plotting tasks may not touch the evidence or execution layers.

## Scientific and retention checks

All 920 accepted files match their pre-release hashes. All 12 package checksum
manifests verify, including the two explicitly documented decompressed-JSON
representations. Forty-five cited superproject commits remain reachable from main
or fourteen preserved scientific tags. No cited historical source is lost by branch
cleanup; no Git corruption was found. Uncited dangling objects were privately backed
up with the Git common directory before cleanup.

Unified archive A and B each contain 8,288 files and 1,191,884,829 payload bytes;
relative paths and SHA-256 hashes match, with zero shared file inodes. Both copies
are on the same local filesystem, so the audit does not call them geographically
independent backups. All ten original path/historical tarballs match their accepted
outer hashes, sizes and member hashes. The newly packaged unified archive preserves
all source bytes. Raw archives retain original execution-era readouts; committed
corrected canonical readouts govern current reporting.

Accounting was independently derived from manifest/row/path status and reason:
1,560 planned; 1,452 successful issues; 108 unsupported unissued slots; route issues
276/276/276/312/312; 46 selected R paths and six no-admitted-candidate outcomes;
108 + 2,674 + 552 = 3,334 physical issues ≤ 3,406. The 72 unissued UPMEM allocations
are not failures. The matched DAG routes stop at admission frontiers while QuEST
retains valid maximum-width endpoints. Archive count is 8,288 per retained copy.

Independent reporting checks matched all calibration/final medians and raw MADs,
resource selections, bootstrap aggregates/endpoints and final timing/CPU ratios.
The 27 generated files rebuild byte-identically; the 22-page review was inspected
at thesis width and checked for text clipping. F1/F2 whiskers describe dispersion
with fixed denominators; path intervals are descriptive paired-block bootstrap
intervals for the fixed circuits and seed schedule. An interval spanning one is
not an equivalence test. Int8 remains approximate. Launch/wait timing is not pure
DPU arithmetic, and saturation alone does not identify a dominant cause.

## Validation after remedies

The current retained suites pass **2,660 tests**, with no failures/errors/skips in
the final local runs: 2,503 implementation + 89 unified + 40 final-v1 + 14 reporting
+ 4 verifier + 5 path-readout + 5 native CPU. The old synthesis suites (58 tests)
were retired with their implementation after passing the baseline audit. New
regressions account for the remaining count change. The combined-process import
collision encountered during release checks is retained and documented; historical
standalone evaluation suites run separately in CI and the documented commands.

Ruff, both pip checks, deterministic reporting rebuild, review compilation and
full compact/raw verification pass. See validation/README.md for exact sources,
logs and scope. Hosted results must be read from their own actual commit/tree and
JUnit records; skipped SDK tests are not passes. Post-merge receipts are included
in the release assets so the validation trail survives Actions retention expiry.

## Limits and release gates

A bounded payload scan covered 19,063 files / 2,652,954,484 bytes plus nested gzip
content. It found no credential markers, SDK native binaries, archive traversal or
link members in the intended raw assets. This is not an exhaustive secret/security
or legal audit. Original licenses and upstream notices remain authoritative.

Most primary correctness references are analytic descriptions; four Stress NumPy
reference arrays are retained, not every output statevector. Historical prose can
use earlier terminology and claim scopes; it remains unchanged and must be read
at its recorded source. Reporting captions supply current timing and inference
limits. These restrictions do not imply missing measurements in the declared
campaign. The full manuscript, DOI assignment and an institutional archival deposit
are outside this release.

Publish only after the normal-merge candidate passes all three hosted jobs. Check
the actual merged commit again, retain the review and validation, upload all assets
to a draft, verify downloaded bytes, then publish the immutable tagged release.
Protect main and remove merged branches only after historical reachability and
private backups are confirmed. Do not move the tag or replace frozen evidence.
