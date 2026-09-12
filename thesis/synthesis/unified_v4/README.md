# Unified Final Evaluation v4 — Publication Synthesis

This directory contains deterministic publication figures and self-contained Typst tables for the Master's thesis.

All figures and tables read exclusively from canonical published evaluation results in:
`thesis/implementation/thesis_results/unified_final_v4/`

## Figure Inventory

| Figure | SVG | PNG | Description |
|---|---|---|---|
| **F1** | `figures/F1_tasklet_speedup.svg` | `figures/F1_tasklet_speedup.png` | 2×3 primary-family tasklet speedup (T1..T24) on 1 DPU, with ideal linear scaling and error bars. |
| **F2** | `figures/F2_dpu_speedup.svg` | `figures/F2_dpu_speedup.png` | 2×3 primary-family DPU speedup across D1..D64 at T8 and T24, showing scaling saturation beyond 16 DPUs. |
| **F3** | `figures/F3_ablation_scaling.svg` | `figures/F3_ablation_scaling.png` | 2×3 normalized runtime across A0..A4: D1/T1, D1/T8, D4/T8, complex launch fusion / four-product fusion, then static-DAG scheduling. |
| **F4** | `figures/F4_quantization_tradeoff.svg` | `figures/F4_quantization_tradeoff.png` | 2×3 physical quantization execution-cost ratios ($t_{\mathrm{f32}} / t_{\mathrm{int8}}$) at matched topology. |
| **F5** | `figures/F5_p6_transfer.svg` | `figures/F5_p6_transfer.png` | 2×2 forest plot of original P6 contrasts (G/F, F/R, R/U, G/U) with paired bootstrap intervals. |
| **F6** | `figures/F6_final_comparison.svg` | `figures/F6_final_comparison.png` | 2×3 LAST comparison width curves: selected UPMEM f32, UPMEM int8, QuEST CPU P8 and P1, with an axis-relative R-path admission frontier; QuEST continues through the largest widths. |

## Table Inventory

| Table | File | Description |
|---|---|---|
| **T1** | `tables/T1_tasklet_speedup.typ` | Tasklet scaling (T1..T24) per primary family and geometric mean speedup. |
| **T2** | `tables/T2_dpu_speedup.typ` | DPU scaling (D1..D64) for T8 and T24 series per primary family and geometric mean. |
| **T3** | `tables/T3_ablation_cumulative.typ` | Cumulative architectural and optimization ablation (A0..A4) speedup and time reduction. |
| **T4** | `tables/T4_quantization_error_cost.typ` | Quantization execution speedup and numerical accuracy disclosure (relative L2, fidelity). |
| **T5** | `tables/T5_selection_winners.typ` | Deterministic topology selection winners (12 primary + 2 supplementary Stress). |
| **T6** | `tables/T6_cold_amortized_costs.typ` | One-time final R-path preparation/search cost, cached-path job-to-state time, and derived cost estimates ($k=1, 10, 100$); no-path execution costs are unavailable. |
| **T7** | `tables/T7_campaign_accounting.typ` | Complete campaign execution accounting, slot reconciliation, and archive verification. |

One-rank DPU scaling saturated after D16, with lower aggregate speedup at D32 and D64.
The executor is host-mediated. Attribution to H2D/D2H, launches, host work or scheduling
requires separate measured evidence; the scaling curve alone does not establish a dominant cause.

The original published evidence commit is `d886e3b7e04a4c3be4a6d4d463206b66f5c0c2a0`.
`readout/accounting.json` reconciles route/status/reason counts against frozen manifests and paths.
Neither this generator nor the corrected readout reruns a hardware measurement or campaign path search.

## Verification

Run the dedicated generator regressions:
```bash
python3 -m unittest discover -s thesis/synthesis/unified_v4/tests -v
```

To regenerate all figures, tables, and verify checksums:
```bash
python3 thesis/synthesis/unified_v4/build.py
(cd thesis/synthesis/unified_v4 && sha256sum -c SHA256SUMS)
```

For isolated rebuilds use `--output /new/directory` and optionally
`--readout /new/readout-directory`; `--canonical` selects the frozen evidence directory.
The output contains figures, tables, this README, and relative checksum entries.
Compile each self-contained table in a landscape A4 proof with 12 mm margins for inspection.
