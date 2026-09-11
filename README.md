# Master's thesis: tensor-network quantum-circuit simulation on UPMEM

This repository contains the research implementation and accepted evidence for a
Master's thesis on exact, untruncated tensor-network quantum-circuit simulation
with selected contraction work executed on physical UPMEM devices.

The execution-system study and the bounded P6 path-optimization campaign are
complete. The thesis-facing consolidation of all accepted results is separate
from those completed experiments. This repository does not currently provide a
`publication/build_thesis_numbers.py` command.

## Start here

- [Implementation and commands](thesis/implementation/README.md)
- [Architecture and numerical semantics](thesis/implementation/ARCHITECTURE.md)
- [Capability and evidence status](thesis/implementation/STATUS.md)
- [Research records](thesis/implementation/docs/README.md)
- [Accepted P6 readout](thesis/implementation/thesis_results/upmem_cost_guided_path_v1/readout/report.md)
- [Interpretation and limitations](thesis/implementation/docs/RESULTS_INTERPRETATION.md)
- [Reproducibility](REPRODUCIBILITY.md), [provenance](PROVENANCE.md), and [third-party software](THIRD_PARTY.md)

The [scoping literature review](thesis/Scoping%20Literature%20Review%20Thesis.pdf)
is retained as the literature basis. Historical plans remain at their recorded
paths; they are not instructions to resume a completed campaign.

## What is implemented

The pipeline lowers supported circuits to a tensor network and a complete
contraction path, constructs a `ContractionDAG`, and maps its contractions to
bounded batched matrix products for UPMEM execution.

The retained one-rank execution profile combines tasklet parallelism within a
DPU, tile parallelism across DPUs, and dependency-ready contractions on disjoint
DPU groups. It uses a WRAM-panel kernel, `packed_wave_v1` transport, a persistent
native host, `static_dag_waves_v1`, and `fused_when_admitted_v1` complex execution.
Intermediates return to the host; graph-wide DPU residency is not claimed.

Complex arithmetic is preserved through four real products:

$$
\Re(AB)=A_rB_r-A_iB_i,\qquad \Im(AB)=A_rB_i+A_iB_r.
$$

`split_complex_float32_v1` is the primary policy. UPMEM lacks a hardware
floating-point unit, but this implementation executes software float32 arithmetic
on the DPU. Host-side shared-scale int8 quantization is a separate approximate
policy, not a compulsory conversion for every UPMEM run. Exact/untruncated refers
to the contraction algorithm, not exact real-number arithmetic.

The outer-product specialization, bounded residency probe, and exact-slicing
experiments are retained as research outcomes, including rejected optimizations.
Implementation does not imply performance adoption.

## P6 result

P6 compares greedy (**G**), FLOP-guided selection (**F**), UPMEM reranking of the
F trace (**R**), and a separate UPMEM-guided adaptive search (**U**). The campaign
accepted 678 physical attempts within a ceiling of 768, with no retries or
replacement observations. All final selections were frozen before evaluation.

Across 12 evaluation circuit/topology cells, the primary session-inclusive R/U
ratio is **1.001343x**, with descriptive paired-block 95% bootstrap interval
**[0.994836, 1.008509]**. R and U select the same path in 8/12 cells. This does not
resolve an additional execution benefit from guided generation over reranking
under the tested 128-proposal protocol; it is not an equivalence test.

The overall session-inclusive F/U and G/U ratios are **1.040425x** and
**1.266508x**, respectively. These are aggregate improvements, not universal
wins. U is slower than G in four cells; the HS18 four-DPU cell has G/U = 0.687613x,
meaning U takes approximately 45.43% more session-inclusive time. The measured
session-opening median is substantially larger for that selected path. The
source tables and both positive and negative results must be reported together.

A ratio is numerator time divided by denominator time. Execution-time reduction
is `100 * (1 - 1/ratio)`, not `100 * (ratio - 1)`. Offline search cost is separate
from physical execution. The evaluation concerns new instances/sizes within six
represented families, not family-held-out or optimizer-seed population inference.

## Verify the software

Use a full Git clone with submodules. A shallow clone can fail legitimate source
ancestry checks.

```bash
git clone --recurse-submodules https://github.com/kazulak/masters-thesis.git
cd masters-thesis
python3.10 -m venv thesis/.venv
thesis/.venv/bin/python -m pip install --upgrade pip
thesis/.venv/bin/python -m pip install \
  -c thesis/implementation/ci/constraints.txt \
  -e './thesis/implementation[dev,path-search]'
make -C thesis/implementation/native/quest_cpu
PY="$(pwd)/thesis/.venv/bin/python"
PYTEST_ADDOPTS=-ra make -C thesis/implementation PYTHON="$PY" test
"$PY" -m ruff check thesis/implementation/src thesis/implementation/tests thesis/implementation/scripts
```

Tests requiring unavailable SDK tools may skip. Report passes, skips, failures,
and skip reasons separately; a green generic CI run is not physical qualification.
See [REPRODUCIBILITY.md](REPRODUCIBILITY.md) for evidence verification and the
software-only smoke workflow. Do not launch historical physical campaigns as a
repository check.

## Scientific identities

| Role | Original commit | Tag |
| --- | --- | --- |
| Frozen executor | `459935f586fdd16c82013838e6d27a12604c3093` | `thesis-upmem-kernel-schedule-system-v1` |
| P6 qualified software | `2beea27411c16e90ed76988613ddb00bcc09f942` | `thesis-upmem-cost-guided-software-v1` |
| P6 results | `8df2ebac61bacd08309ea490309be5a8dcb943b2` | `thesis-upmem-cost-guided-results-v1` |

The standalone tree descends from the polished original repository at
`9fdecfe0c01c769ceb5b7410e1aa2d38a089dc87`. Original ancestry and reachable
scientific tags are preserved. Publication commits never replace the original
source identities embedded in evidence.

## Claim boundary

No claim is made of universal CPU/GPU superiority, multi-rank scalability,
asynchronous transfer/compute overlap, energy efficiency, globally optimal paths,
or universal int8 accuracy. The earlier matched NumPy/UPMEM baseline is a
powersave-conditioned diagnostic, not a final optimized CPU comparison. CPU
references have distinct correctness, same-DAG, and external-workflow roles.

The committed P6 audit package contains accepted records, readout tables, and raw
archive identities. The archive hashes are not substitutes for the original
archive bytes. Full archive re-verification requires those retained files.

No new project-wide license is declared here. Third-party components retain
their upstream terms; see [THIRD_PARTY.md](THIRD_PARTY.md).
