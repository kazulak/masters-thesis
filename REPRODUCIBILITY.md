# Reproduce and verify

For the frozen research artifact, check out `thesis-artifact-v1.0.0` after cloning.
Start with the [release verifier and raw archive instructions](release/README.md).
Verification is read-only; it does not regenerate accepted evidence. The canonical
final dataset is [unified-v4](thesis/implementation/thesis_results/unified_final_v4/README.md).
The supporting path study and historical packages retain their own source identities.

## Software checks

Use a full-history clone; provenance tests require original commits, not just files.
The commands below use Python 3.10 and do not authorize a physical campaign.

```bash
git clone --recurse-submodules https://github.com/kazulak/masters-thesis.git
cd masters-thesis
set -euo pipefail
python3.10 -m venv thesis/.venv
PY="$PWD/thesis/.venv/bin/python"
"$PY" -m pip install -c thesis/implementation/ci/constraints.txt \
  -e './thesis/implementation[dev,path-search]'
"$PY" -m pip check
make -C thesis/implementation/native/quest_cpu
mkdir -p "$HOME/evidence"
OUT=$(mktemp -d "$HOME/evidence/masters-thesis-check.XXXXXX")
git rev-parse HEAD 'HEAD^{tree}' > "$OUT/source.txt"
"$PY" -m pip freeze > "$OUT/packages.txt"
unset UPMEM_ALLOW_PHYSICAL_HARDWARE
PYTEST_ADDOPTS="-ra --junitxml=$OUT/pytest.xml" \
  make -C thesis/implementation PYTHON="$PY" test 2>&1 | tee "$OUT/pytest.log"
"$PY" -m ruff check thesis/implementation/{src,tests,scripts}
"$PY" -m ruff check thesis/reporting tools
"$PY" -m pytest evaluation/final_v1/tests --junitxml="$OUT/final-v1.xml"
"$PY" -m pytest evaluation/unified_v4/tests --junitxml="$OUT/unified-v4.xml"
"$PY" -m pytest tools/tests --junitxml="$OUT/release-verifier.xml"
"$PY" -m pytest thesis/implementation/native/quest_cpu/tests --junitxml="$OUT/native-cpu.xml"
"$PY" -m pytest thesis/implementation/thesis_results/upmem_cost_guided_path_v1/tools/test_p6_readout.py \
  --junitxml="$OUT/path-readout.xml"
"$PY" tools/verify_release.py --repo . --output "$OUT/compact-evidence.json"
```

Report passes, failures, errors **and skips** from each run. Hosted CI can skip
SDK-dependent tests; this is not physical qualification. Preserve full history
in Actions (`fetch-depth: 0`). Submodule commits are pinned by Git; do not update them
as part of verification.
Run evaluation suites in separate Python processes as shown: the historical
standalone modules share import names such as `readout` and cannot be safely
collected together in a single pytest process.

## Software smoke and frozen evidence

Continue in the same shell:

```bash
make -C thesis/implementation PYTHON="$PY" plan \
  CONFIG=configs/tn_benchmark_reset.yml OUTPUT="$OUT/plan"
make -C thesis/implementation PYTHON="$PY" run \
  CONFIG=configs/tn_benchmark_reset.yml OUTPUT="$OUT/run"
make -C thesis/implementation PYTHON="$PY" verify INPUT="$OUT/run"
make -C thesis/implementation PYTHON="$PY" report \
  INPUT="$OUT/run" REPORT_OUTPUT="$OUT/report"
(cd thesis/implementation/thesis_results/upmem_cost_guided_path_v1 && \
  sha256sum -c SHA256SUMS && "$PY" tools/test_p6_readout.py)
```

Manifests use `evidence_manifest_v2`, samples `evidence_sample_v4`, sessions
`evidence_session_v1`, and reports `evidence_report_v5`. Keep execution success,
same-policy numerical replay and full-precision accuracy as separate predicates.
Do not regenerate accepted records or checksums while verifying them.

## Source identities

The repository descends from `kazulak/Masters@9fdecfe0c01c769ceb5b7410e1aa2d38a089dc87`.
Original scientific tags retain these exact commits:

| Tag | Commit |
| --- | --- |
| `thesis-upmem-kernel-schedule-system-v1` | `459935f586fdd16c82013838e6d27a12604c3093` |
| `thesis-upmem-cost-guided-software-v1` | `2beea27411c16e90ed76988613ddb00bcc09f942` |
| `thesis-upmem-cost-guided-results-v1` | `8df2ebac61bacd08309ea490309be5a8dcb943b2` |

A later documentation commit is not the execution source of those measurements.
Paths in old metadata may name deleted guidance; resolve them at the recorded
historical commit. Do not rewrite frozen metadata to describe the current tree.

Original raw stage archives are retained separately. Committed digests and accepted
rows support inspection but do not substitute for the archive bytes. See
[results](thesis/implementation/RESULTS.md) for evidence and timing boundaries and
the [release archive index](release/raw-archives.json) for the eleven public assets.

## Presentation only

Use a separate Python 3.13.15 environment. The implementation environment uses
Python 3.10; do not replace its dependency constraints with the rendering lock.

```bash
python3.13 -m venv /tmp/thesis-rendering
REPORT_PY=/tmp/thesis-rendering/bin/python
"$REPORT_PY" -m pip install -r thesis/reporting/requirements.lock
"$REPORT_PY" -m pip check
"$REPORT_PY" tools/check_rendering_environment.py
"$REPORT_PY" -Werror::ResourceWarning -m unittest discover -s thesis/reporting/tests -v
"$REPORT_PY" -Werror::ResourceWarning thesis/reporting/build_all.py
git diff --exit-code -- thesis/reporting/generated
typst compile --root . thesis/reporting/review.typ /tmp/thesis-reporting-review.pdf
```

Use Typst 0.13.1 and the DejaVu font bytes recorded in
[rendering-environment.json](release/rendering-environment.json). The CI workflow
pins the Typst download by SHA-256. Environment mismatches fail explicitly; a
different font/runtime may render differently without changing scientific values.
There are 27 final SVG/PNG/Typst outputs. The review PDF is not a full manuscript.

## Validation receipts

The [release audit](release/AUDIT.md) and [local logs](release/validation/README.md)
distinguish full local simulator/software coverage from hosted CI's SDK skips.
CI retains JUnit, logs, source identities and environments for all three jobs;
the release validation asset preserves the hosted receipts beyond their retention
period. Historical receipt counts describe their recorded source revisions only.

## Historical physical utilities

From `thesis/implementation`, `make sequential-conformance` checks the historical
contract and `make sequential-baseline` displays qualifier help. Physical qualification
uses `PHYSICAL_CONFIG=` and explicit `--allow-physical` opt-in; do not use it for ordinary
repository verification. Old freeze/operator scripts remain source-bound utilities,
not commands to re-execute completed campaigns on today's HEAD. A new physical run
requires its own declared configuration and run identity.
