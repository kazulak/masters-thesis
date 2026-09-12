# Master's thesis: quantum simulation on UPMEM

Research code for deterministic full-statevector quantum-circuit simulation through
exact, untruncated tensor-network contraction on UPMEM Processing-in-Memory hardware.
The completed experiments cover tasklet, multi-DPU and DAG parallelism, host/runtime
optimizations, complex arithmetic, optional int8 quantization and hardware-aware paths.

| Start here | Contents |
| --- | --- |
| [Architecture](thesis/implementation/ARCHITECTURE.md) | Final system and numerical policies |
| [Final evidence](thesis/implementation/thesis_results/unified_final_v4/README.md) | Frozen six-family calibration and final CPU/UPMEM comparison |
| [Reporting](thesis/reporting/README.md) | Five main figures, five main tables, and appendix detail |
| [Release and audit](release/README.md) | Raw archives, provenance, verification and artifact scope |
| [Results](thesis/implementation/RESULTS.md) | Current findings and historical mechanism studies |
| [Reproduce](REPRODUCIBILITY.md) | Installation, tests and provenance |
| [Implementation](thesis/implementation/README.md) | Code layout and commands |

The final unified campaign issued **3,334 physical UPMEM executions** within its
3,406 ceiling. Its 52 path searches selected 46 paths and recorded six declared
admission frontiers. The final five-route comparison contains 1,452 successful
issued slots and 108 unsupported, unissued slots. No hardware rerun is needed.

The supporting path-selection study accepted 678 physical attempts in a separate
campaign. Hardware-aware reranking improved aggregate execution over FLOP
selection; adaptive search showed no resolved additional benefit over reranking.
These are scoped results, not a claim of universal CPU/GPU superiority.

The release `thesis-artifact-v1.0.0` freezes the **research artifact**, including
accepted evidence and the reporting review PDF. It is not a completed thesis
manuscript. Evidence is immutable; plotting and table scripts read it directly.

The [scoping literature review](thesis/Scoping%20Literature%20Review%20Thesis.pdf)
provides the research background. Git history preserves the original development;
agent plans are not part of the current tree. Original code is [MIT licensed](LICENSE);
original documentation, data and figures are [CC BY 4.0](LICENSE-DATA).
See [third-party terms and exceptions](THIRD_PARTY.md) and [citation metadata](CITATION.cff).
