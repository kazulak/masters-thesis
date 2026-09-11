# Master's thesis: quantum simulation on UPMEM

Research code for deterministic full-statevector quantum-circuit simulation through
exact, untruncated tensor-network contraction on UPMEM Processing-in-Memory hardware.
The completed experiments cover tasklet, multi-DPU and DAG parallelism, host/runtime
optimizations, complex arithmetic, optional int8 quantization and hardware-aware paths.

| Start here | Contents |
| --- | --- |
| [Architecture](thesis/implementation/ARCHITECTURE.md) | Final system and numerical policies |
| [Results](thesis/implementation/RESULTS.md) | Findings, negative results and evidence sources |
| [Reproduce](REPRODUCIBILITY.md) | Installation, tests and provenance |
| [Implementation](thesis/implementation/README.md) | Code layout and commands |

The final path study accepted **678 physical attempts**. Hardware-aware selection
improved aggregate execution over FLOP selection; adaptive generation showed no
resolved additional benefit over reranking. These are workload-specific results,
not a claim of universal CPU/GPU superiority.

The [scoping literature review](thesis/Scoping%20Literature%20Review%20Thesis.pdf)
provides the research background. Git history preserves the original development;
agent plans are not part of the current tree. See [third-party terms](THIRD_PARTY.md).
