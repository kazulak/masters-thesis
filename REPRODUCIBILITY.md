# Reproducibility

This repository separates three kinds of reproducibility:

1. software verification;
2. compact accepted-evidence verification;
3. historical physical-experiment replication.

They are not the same operation.

## 1. Software verification

Clone recursively:

```bash
git clone --recurse-submodules   https://github.com/kazulak/masters-thesis.git

cd masters-thesis
```

Create a Python 3.10 environment:

```bash
python3.10 -m venv thesis/.venv

thesis/.venv/bin/python -m pip install --upgrade pip

thesis/.venv/bin/python -m pip install   -c thesis/implementation/ci/constraints.txt   -e './thesis/implementation[dev,path-search]'
```

Build the QuEST CPU helper:

```bash
make -C thesis/implementation/native/quest_cpu
```

Run the full implementation test suite:

```bash
make -C thesis/implementation   PYTHON=../.venv/bin/python   test
```

Run Ruff:

```bash
thesis/.venv/bin/python -m ruff check   thesis/implementation/src   thesis/implementation/tests   thesis/implementation/scripts
```

## 2. Software smoke workflow

Create a software-only deterministic plan:

```bash
make -C thesis/implementation   PYTHON=../.venv/bin/python   plan   CONFIG=configs/tn_benchmark_reset.yml   OUTPUT=runs/standalone-plan
```

Run the software benchmark routes:

```bash
make -C thesis/implementation   PYTHON=../.venv/bin/python   run   CONFIG=configs/tn_benchmark_reset.yml   OUTPUT=runs/standalone-run
```

Verify:

```bash
make -C thesis/implementation   PYTHON=../.venv/bin/python   verify   INPUT=runs/standalone-run
```

Report:

```bash
make -C thesis/implementation   PYTHON=../.venv/bin/python   report   INPUT=runs/standalone-run   REPORT_OUTPUT=runs/standalone-report
```

These are software verification commands, not physical UPMEM benchmarks.

## 3. Verify the frozen P6 audit package

```bash
cd thesis/implementation/thesis_results/upmem_cost_guided_path_v1

sha256sum -c SHA256SUMS

python3 tools/test_p6_readout.py
```

The checksum command must report every tracked package file as `OK`.

The synthetic readout tests must pass.

Do not regenerate the accepted P6 package merely because it is being verified.

## 4. Verify submodule pins

From repository root:

```bash
test "$(git -C thesis/implementation/external/QuEST rev-parse HEAD)"   = "9d7618d7263e3bfba433b88cf1eac0647f08fa0a"

test "$(git -C thesis/implementation/external/SimplePIM rev-parse HEAD)"   = "1d639c53532555f01e9f71d872e7712b166d6cba"

test "$(git -C thesis/implementation/external/PID-Comm rev-parse HEAD)"   = "cecc39e29e6576ced73b2041db6e357769a6531a"
```

## 5. Physical UPMEM experiments

The accepted physical campaigns are frozen historical research records.

Do not treat:

```text
pytest
SDK simulator
software smoke runs
```

as reproductions of physical UPMEM performance.

The P6 physical campaign originally used:

```text
host:
safari-baguette1.ethz.ch

UPMEM SDK:
2023.1.0

Python:
3.10.12

rank:
/dev/dpu_rank1
```

along with exact native binaries, source identities, resource locks, CPU/governor records, and once-only evidence controls.

A new hardware run is a replication experiment with a new run/environment identity.

## 6. Historical P6 operator script

The file:

```text
thesis/implementation/thesis_results/upmem_cost_guided_path_v1/tools/p6_operator.sh
```

is retained as audit/provenance material.

It is bound to the original `kazulak/Masters` Git source/tag graph and historical physical environment.

It is **not** part of normal standalone-repository verification and should not be invoked simply to test this repository.

## 7. Final thesis calculations

Final thesis-facing result tables and calculations are deliberately not generated in Chunk 2.

They will be generated in a separate later chunk after this standalone repository has passed clean-clone verification.
