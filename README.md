# Master's Thesis — UPMEM Tensor-Network Quantum-Circuit Simulation

This repository is the standalone research artifact for the Master's thesis:

**Accelerating Tensor Network Contraction for Quantum Circuit Simulation Using Processing-in-Memory Architectures**

Poznań University of Technology  
Computer Science — Distributed and Cloud Systems

## Research status

The implementation research phase is complete and frozen.

The work studies exact, untruncated tensor-network quantum-circuit simulation on UPMEM Processing-in-Memory hardware, including:

- exact circuit-to-tensor-network lowering;
- complete contraction-path replay;
- physical UPMEM execution;
- tasklet and multi-DPU parallelism;
- static DAG-wave scheduling;
- launch-fused complex execution;
- numerical-policy characterization;
- bounded slicing/residency experiments;
- physically calibrated UPMEM-aware contraction-path selection.

The final path-optimization campaign executed 678 physical attempts within a preregistered ceiling of 768, with zero retries and zero replacement observations.

## Main final result

The final P6 study compares:

- **G** — deterministic greedy contraction path;
- **F** — FLOP-selected path from bounded cotengra search;
- **R** — UPMEM-aware reranking of the same conventional search trace;
- **U** — separate adaptive search in which the UPMEM launch-aware score influences candidate generation.

The primary held-out R/U comparison on session-inclusive physical execution was:

```text
R/U = 1.0013425605931643x

descriptive paired-block 95% interval:
[0.9948355448727421, 1.0085087497299605]

same selected path:
8 / 12 evaluation cells
```

Under the tested 128-proposal search protocol, the experiment therefore does not resolve an additional physical execution benefit from UPMEM-guided adaptive candidate generation beyond UPMEM-aware reranking.

Hardware-aware selection itself remains useful:

```text
F/R session-inclusive overall:
1.0390296080428785x

F/U session-inclusive overall:
1.040424568249768x

F/U session-inclusive, 4 DPU:
1.0818412974163845x

G/U session-inclusive overall:
1.2665079983332086x
```

Search time is an offline planning cost and is reported separately from physical execution.

## Repository layout

```text
thesis/
  README.md
  Scoping Literature Review Thesis.pdf
  upmem-system-and-path-optimization-plan.md
  upmem-system-and-path-optimization-plan-v2.md
  upmem-path-search-operational-runbook-v1.md

  implementation/
    README.md
    STATUS.md
    ARCHITECTURE.md

    src/
    native/
    configs/
    scripts/
    tests/
    docs/
    external/
    thesis_results/
```

The active implementation is:

```text
thesis/implementation/
```

The final P6 audit package is:

```text
thesis/implementation/thesis_results/upmem_cost_guided_path_v1/
```

The scoping literature review that motivates the architecture and research questions is retained at:

```text
thesis/Scoping Literature Review Thesis.pdf
```

## Scientific provenance

This standalone repository preserves the original Git ancestry of the thesis work developed in:

```text
https://github.com/kazulak/Masters
```

The standalone publication tree was prepared from:

```text
kazulak/Masters
main@9fdecfe0c01c769ceb5b7410e1aa2d38a089dc87
```

The current tree contains only the thesis/publication artifact, while the retained Git ancestry preserves historical experiment source commits required by repository provenance checks.

The original `kazulak/Masters` repository remains the authoritative wider university-monorepo and archive-history source.

Original frozen scientific identities:

```text
final UPMEM executor:
459935f586fdd16c82013838e6d27a12604c3093
tag:
thesis-upmem-kernel-schedule-system-v1

P6 qualified software:
2beea27411c16e90ed76988613ddb00bcc09f942
tag:
thesis-upmem-cost-guided-software-v1

P6 accepted result package:
8df2ebac61bacd08309ea490309be5a8dcb943b2
tag:
thesis-upmem-cost-guided-results-v1
```

Reachable `thesis-*` scientific milestone tags are preserved at their exact original commits in this standalone repository.

The original `archive/*` tags for intentionally divergent historical branches remain only in `kazulak/Masters`.

The standalone publication/cleanup commit is not a replacement for historical physical-experiment `source_sha` values.


## Setup

Clone with submodules:

```bash
git clone --recurse-submodules   https://github.com/kazulak/masters-thesis.git

cd masters-thesis
```

If already cloned without submodules:

```bash
git submodule update --init --recursive
```

Create a Python 3.10 environment:

```bash
python3.10 -m venv thesis/.venv

thesis/.venv/bin/python -m pip install --upgrade pip

thesis/.venv/bin/python -m pip install   -c thesis/implementation/ci/constraints.txt   -e './thesis/implementation[dev,path-search]'
```

Run the software suite:

```bash
make -C thesis/implementation   PYTHON=../.venv/bin/python   test

thesis/.venv/bin/python -m ruff check   thesis/implementation/src   thesis/implementation/tests   thesis/implementation/scripts
```

Verify the frozen P6 audit package:

```bash
cd thesis/implementation/thesis_results/upmem_cost_guided_path_v1

sha256sum -c SHA256SUMS
python3 tools/test_p6_readout.py
```

See `REPRODUCIBILITY.md` for the complete standalone verification procedure.

## Physical execution boundary

The accepted physical experiments are historical frozen research records.

Normal validation of this repository must **not** rerun the historical UPMEM campaigns.

A new hardware execution would have a new run/environment identity and is a replication study, not the original accepted observation set.

The historical P6 operator script is retained inside the audit package for provenance. It is bound to the original `kazulak/Masters` source/tag graph and is not a normal standalone-repository command.

## Scope limits

The final thesis implementation does not claim:

* multi-rank scaling;
* asynchronous host/DPU overlap;
* energy efficiency;
* universal int8 accuracy;
* arbitrary graph-wide DPU residency;
* automatic heterogeneous CPU/GPU/UPMEM placement;
* globally optimal contraction paths;
* universal UPMEM superiority over CPU/GPU simulation.

Results are limited to the recorded workloads, numeric policies, topologies, timing scopes, and hardware environment.

## License and third-party software

No new project-wide open-source license is declared for this standalone snapshot.

Third-party dependencies remain under their own upstream licenses and are referenced as Git submodules.

See:

```text
THIRD_PARTY.md
```

for details.
