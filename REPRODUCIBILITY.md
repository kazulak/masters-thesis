# Reproducibility and validation boundaries

The retained software, accepted experiment records, and new publication outputs
have different provenance. Verifying this repository must not silently launch
historical physical campaigns, refit the model, or regenerate accepted evidence.

## 1. Clone with history and pinned dependencies

```bash
git clone --recurse-submodules https://github.com/kazulak/masters-thesis.git
cd masters-thesis
```

Do not use a shallow clone: retained qualification checks test real ancestry.
For an existing shallow clone, fetch the missing history from this repository
before validation:

```bash
git fetch --unshallow origin
```

That command is needed only when `git rev-parse --is-shallow-repository` reports
`true`. Do not replace ancestry validation with a special case.

From repository root:

```bash
set -euo pipefail
git submodule update --init --recursive

test "$(git -C thesis/implementation/external/QuEST rev-parse HEAD)" = \
  9d7618d7263e3bfba433b88cf1eac0647f08fa0a
test "$(git -C thesis/implementation/external/SimplePIM rev-parse HEAD)" = \
  1d639c53532555f01e9f71d872e7712b166d6cba
test "$(git -C thesis/implementation/external/PID-Comm rev-parse HEAD)" = \
  cecc39e29e6576ced73b2041db6e357769a6531a

git merge-base --is-ancestor \
  c86b589d971ef241c5f42d0da33fc772dd9c2107 HEAD
git merge-base --is-ancestor \
  9fdecfe0c01c769ceb5b7410e1aa2d38a089dc87 HEAD
```

Historical scientific tags retain their original commits. A publication commit
must not be written into an old experiment's `source_sha`.

## 2. Install and run software checks

Use the repository's Python 3.10 development environment, not an inferred copy of
the historical physical environment:

```bash
set -euo pipefail
python3.10 -m venv thesis/.venv
PY="$(pwd)/thesis/.venv/bin/python"
"$PY" -m pip install --upgrade pip
"$PY" -m pip install -c thesis/implementation/ci/constraints.txt \
  -e './thesis/implementation[dev,path-search]'
"$PY" -m pip check
make -C thesis/implementation/native/quest_cpu
```

The QuEST build used by this repository produces
`thesis/implementation/native/quest_cpu/bin/quest_runner`. It is a CPU baseline
helper, not a UPMEM kernel or proof of a CPU-versus-UPMEM performance result.

Store validation receipts outside the checkout:

```bash
set -euo pipefail
RECEIPTS=$(mktemp -d "${TMPDIR:-/tmp}/masters-thesis-validation.XXXXXX")
{
  git rev-parse HEAD
  git rev-parse 'HEAD^{tree}'
  "$PY" --version
  "$PY" -m pip freeze
} > "$RECEIPTS/environment.txt"

unset UPMEM_ALLOW_PHYSICAL_HARDWARE
PYTEST_ADDOPTS="-ra --junitxml=$RECEIPTS/pytest.xml" \
  make -C thesis/implementation PYTHON="$PY" test \
  2>&1 | tee "$RECEIPTS/pytest.log"

"$PY" -m ruff check \
  thesis/implementation/src \
  thesis/implementation/tests \
  thesis/implementation/scripts \
  2>&1 | tee "$RECEIPTS/ruff.log"
printf 'Validation receipts: %s\n' "$RECEIPTS"
```

Retain `set -o pipefail`: a failing command must not appear successful merely
because `tee` succeeded. Do not delete receipts before recording their location
and the actual results.

SDK-dependent tests intentionally skip when the required SDK/compiler tools are
absent. Report **passed, failed, errors, skipped and skip reasons**. Do not call
2,489 collected tests “2,489 passed” unless that particular receipt says so.
The reviewed generic hosted CI run had 2,257 passes and 232 skips; a different
SDK-equipped environment can have a different pass/skip split.

`UPMEM_REQUIRE_SDK_SIMULATOR=1` makes missing simulator prerequisites a failure
for tests that implement that gate. Use it only for a deliberately configured
SDK qualification environment. Normal hosted CI is not a physical UPMEM test.
Neither simulator success nor absence of detected races is proof of every
physical thread interleaving.

## 3. Software-only smoke

From repository root with `PY` set as above:

```bash
set -euo pipefail
RUNROOT=$(mktemp -d "${TMPDIR:-/tmp}/masters-thesis-smoke.XXXXXX")
make -C thesis/implementation PYTHON="$PY" plan \
  CONFIG=configs/tn_benchmark_reset.yml OUTPUT="$RUNROOT/plan"
make -C thesis/implementation PYTHON="$PY" run \
  CONFIG=configs/tn_benchmark_reset.yml OUTPUT="$RUNROOT/run"
make -C thesis/implementation PYTHON="$PY" verify INPUT="$RUNROOT/run"
make -C thesis/implementation PYTHON="$PY" report \
  INPUT="$RUNROOT/run" REPORT_OUTPUT="$RUNROOT/report"
printf 'Software smoke evidence: %s\n' "$RUNROOT"
```

This checks software operation and evidence flow. It does not supply a new
physical UPMEM performance comparison. A smoke report with zero eligible speedup
rows must remain zero, not be repurposed into a benchmark claim.

## 4. Verify the immutable P6 package

```bash
(
  set -e
  cd thesis/implementation/thesis_results/upmem_cost_guided_path_v1
  sha256sum -c SHA256SUMS
  python3 tools/test_p6_readout.py
)
```

The accepted compact package has 33 checksum entries and a five-test readout
unit suite at the recorded result version. Check actual output rather than
assuming counts. Do not regenerate checksums to conceal a changed file.

Checksum verification confirms integrity against the manifest; it is not a
cryptographic signature and does not itself validate experimental design.
Original physical archive digests can be independently recomputed only when
those archive bytes are available. Their identities are recorded in
`evidence_manifests/stage_archives.json`.

## 5. CI identity

A pull-request Actions workflow can check out GitHub's synthetic merge commit
rather than the contributor's branch HEAD. Record the actual checked-out commit
and tree, the event, and the relevant head commit separately. A tree-equivalent
run is useful validation, but it is not literally an exact-HEAD checkout.

The workflow retains `fetch-depth: 0`, reports checkout/environment identity,
and emits the actual pytest/JUnit counts including skips. Missing SDK tests
remain visible instead of being described as passed.

## 6. Physical and numerical evidence

Historical physical campaigns are frozen records. The retained P6 operator
script is not a general installation test. Do not launch it while validating
publication documentation or analysis code.

The recorded P6 environment used `safari-baguette1.ethz.ch`, UPMEM SDK 2023.1.0,
Python 3.10.12 and an explicitly selected rank, together with exact binary,
resource, affinity, governor and run identities. Those facts do not automatically
apply to a new machine or run. Earlier campaigns recorded their own environments.

Three different checks must stay distinct:

1. execution completed under the requested physical target and resource contract;
2. the result matched the declared numerical-policy replay;
3. the result met the declared full-precision accuracy criterion.

An approximate int8 result can satisfy the first two and fail the third. A
correct numerical result alone does not establish performance eligibility.

## 7. CPU comparisons and later result extraction

The historical sequential baseline contains a matched same-DAG NumPy/UPMEM
comparison under its own diagnostic conditions. P6 compares four UPMEM path
methods, not CPU against UPMEM. QuEST/Quimb adapter availability is not evidence
of a final matched CPU comparison.

The thesis-facing extraction layer has not been created by the repository audit.
Use the accepted result packages and their original analysis contracts; do not
invoke a nonexistent `publication/build_thesis_numbers.py` script. Plans and
operator records remain historical evidence, not authorization to tune completed
studies or silently add a benchmark campaign.
