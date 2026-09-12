# Published local validation receipt

This package publishes the local software-validation evidence for reporting
correction commit [`cbd3817f0f775bbe1a1e1d7e5281333706d9aaa6`](https://github.com/kazulak/masters-thesis/commit/cbd3817f0f775bbe1a1e1d7e5281333706d9aaa6).
It is a **local validation receipt, not a GitHub-hosted CI run**. The later commit
adding this directory only publishes the receipt and its verification instructions.

The previously linked
`thesis/implementation/runs/unified-v4-reporting-validation-20260912/README.md`
was local-only: `thesis/implementation/.gitignore` excludes `runs*/`. It was absent
from the pushed tree. This tracked directory is the published replacement.

## Test results and the rerun

The retained records support **2,679 distinct tests resolved passing across several
commands**, including a targeted rerun. They do not describe a single initially
green test invocation.

| Validation | Initial result | Resolution / evidence |
| --- | ---: | --- |
| Implementation suite | 2,488 passed; 1 failed | [Original JUnit](implementation-tests.xml) and [log](implementation-tests.log) |
| Targeted implementation rerun | 1 passed | [Rerun JUnit](durable-archive-test.xml) and [log](durable-archive-test.log); same failed test identity |
| Final-v1 evaluation | 40 passed | [Log](final-v1-tests.log) |
| Unified-v4 evaluation | 87 passed | [Log](unified-v4-tests.log) |
| Legacy synthesis | 51 passed | [Log](legacy-synthesis-tests.log) |
| Unified-v4 publication | 7 passed | [Log](final-publication-tests.log) |
| Frozen P6 readout | 5 passed | [Log](p6-tests.log) |

The initial implementation failure was
`tests.test_cost_guided_archive_copies::test_two_copies_are_extracted_verified_and_not_same_inode`.
That test intentionally rejects archive paths under `/tmp`, where the isolated
correction checkout was located. It passed on the same correction commit in the
durable `masters-thesis-unified-v4` worktree. The original failure remains in the
published records. The rerun replaces that test's outcome when counting distinct
tests; it does not add a 2,680th test. There were no skipped tests or test errors.

[CORRECTION_AUDIT.json](CORRECTION_AUDIT.json) is the original local receipt,
copied byte-for-byte. Its reviewed source hashes identify the audited reporting
code. Its commit and publication-status fields describe that historical audit,
not the branch head after this receipt is added. The original logs and JUnit
files are also unchanged. [lint.log](lint.log)
records the successful configured Ruff checks.

## Hosted CI status

GitHub reported zero workflow runs, zero check runs and zero commit statuses for
`cbd3817f…` when this package was published. The combined-status endpoint returned
`pending` with zero statuses; that is not a successful CI result or evidence of a
queued workflow. [HOSTED_CI_STATUS.json](HOSTED_CI_STATUS.json) records the observation
time and API sources.

The existing workflow triggers on pushes to `main` and pull requests, not ordinary
pushes to `evaluation/unified-final-v4`. Publishing this receipt does not alter CI
triggers or create a hosted test result. The 2,679-test claim is supported by the
published local records above.

## Verify and reproduce

From the repository root, using Python 3.10 or newer:

```sh
python3 evaluation/unified_v4/validation/reporting-20260912/verify.py
(cd evaluation/unified_v4/validation/reporting-20260912 && sha256sum -c SHA256SUMS)
```

The verifier checks the package hashes, checks the recorded source hashes against
the audited Git commit, parses both JUnit files, reconciles the exact failed/rerun
test identity, and checks all five additional suite summaries. It performs no
hardware execution, workload measurement or path search. The audited commit must
be available in the local Git history. These checks establish consistency of the
published local records; they are not an independent hosted rerun.

To rerun the suites, use the implementation environment described in
[REPRODUCIBILITY.md](../../../../REPRODUCIBILITY.md) and the separate publication
environment pinned by `thesis/synthesis/requirements.txt`. Use a durable checkout
outside `/tmp`, `/run` and `/dev/shm` for the implementation suite:

```sh
make -C thesis/implementation PYTHON="$IMPLEMENTATION_PYTHON" test
"$IMPLEMENTATION_PYTHON" -m unittest discover -s evaluation/final_v1/tests -v
"$IMPLEMENTATION_PYTHON" -m unittest discover -s evaluation/unified_v4/tests -v
"$PUBLICATION_PYTHON" -m unittest discover -s thesis/synthesis/tests -v
"$PUBLICATION_PYTHON" -m unittest discover -s thesis/synthesis/unified_v4/tests -v
(cd thesis/implementation/thesis_results/upmem_cost_guided_path_v1 && \
  "$IMPLEMENTATION_PYTHON" tools/test_p6_readout.py)
```

## Evidence boundaries

The correction receipt also records the independently reviewed 46 selected R paths,
six no-path outcomes, 3,334 physical issues and 8,288 files in each archive. It
records identical independent readout/publication rebuilds and unchanged frozen
inputs. The corresponding build logs and [archive summary](archive-audit.json)
are included here.

The full archive inventory and rendered inspection proofs remain in the original
local validation directory; they are not included in this compact package. The
receipt records the archive inventory's SHA-256. Verifying the retained archive
bytes requires access to those archives. Publishing these local records performs
no new hardware measurements or campaign path searches and does not merge the
evaluation branch into `main`.
