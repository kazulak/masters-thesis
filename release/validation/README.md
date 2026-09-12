# Retained local release validation

These are local receipts, not GitHub-hosted results. `local-results.json` identifies
2,660 passing tests on the release-preparation working tree based on `a2a5b534`.
[tested-source.sha256](tested-source.sha256) identifies the tested Python sources
and all 27 unchanged presentation outputs; it avoids attributing a working-tree
run to an untested future commit. From the repository root, check it with:

    sha256sum -c release/validation/tested-source.sha256

| Suite | Passed | Receipt |
| --- | ---: | --- |
| Implementation | 2,503 | implementation.log / implementation.xml |
| Final-v1 contracts | 40 | final_v1.log / final_v1.xml |
| Unified-v4 contracts | 89 | unified_v4.log / unified_v4.xml |
| Release verifier | 4 | verifier.log / verifier.xml |
| Path readout | 5 | path-readout.log / path-readout.xml |
| Native CPU | 5 | native-cpu.log / native-cpu.xml |
| Reporting | 14 | reporting-tests.log |
| **Total** | **2,660** | **0 failures, errors or skips in these final runs** |

Subtests are not counted as additional distinct test methods. Implementation tests
used Python 3.10.12, initialized pinned submodules, the native CPU runner and SDK
2025.1.0 simulator. Physical opt-in was explicitly unset. Reporting used the exact
release environment fingerprint. Ruff passed for implementation src/tests/scripts,
reporting and tools; both Python environments passed pip check. All 19 reporting
scripts rebuilt the 27 tracked outputs byte-identically. Typst 0.13.1 compiled the
22-page review; no extracted word bounds lay outside a page. The independent
scientific/visual audit of the unchanged outputs is summarized in ../AUDIT.md.

The accepted correction's published historical receipt still verifies; see
correction-receipt.log. Its 2,679 count is a different, explicitly recorded revision
and suite selection. Current counts must not be substituted into that frozen receipt.

`evidence-before-commit.json` records full compact and eleven-archive verification
before commit. Its source_commit/tree fields describe the Git base, while the
working-tree verifier and inventories are identified by this validation package.
Post-merge verification and actual hosted run identities are retained in the
release validation asset. CI JUnit records disclose skips separately.

Earlier unsuccessful attempts are deliberately retained:

- `audit-full-pytest.*`: the original audit attempt in an uninitialized/restricted
  checkout (2,324 passed, 32 failed, 133 errors). This was a prerequisite-limited
  run, not the final test result. `audit-complete-pytest.*` then passed all 2,489
  pre-fix implementation tests with initialized prerequisites. The corresponding
  `audit-source-environment.json` verifies byte-identical audited implementation
  source across those checkouts.
- `contracts.*`: a combined multi-suite pytest invocation loaded the historical
  final-v1 `readout` module into unified-v4 tests (128 passed, 29 failed). The
  standalone suites use colliding import names. The documented commands and CI
  isolate them in separate processes; all final per-suite receipts above pass.

Neither prerequisite correction nor test-process isolation changed evidence or
reran physical hardware. SHA256SUMS covers every other file in this directory.
