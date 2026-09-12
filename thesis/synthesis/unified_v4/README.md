# Unified Final Evaluation v4 — Publication Synthesis

This directory contains deterministic publication figures and self-contained Typst tables for the Master's thesis.

All figures and tables read exclusively from canonical published evaluation results in:
`thesis/implementation/thesis_results/unified_final_v4/`

## Figure Inventory

| Figure | SVG | PNG | Description |
|---|---|---|---|
| **F1** | `figures/F1_tasklet_speedup.svg` | `figures/F1_tasklet_speedup.png` | 2×3 primary-family tasklet speedup (T1..T24) on 1 DPU, with ideal linear scaling and error bars. |
| **F2** | `figures/F2_dpu_speedup.svg` | `figures/F2_dpu_speedup.png` | 2×3 primary-family DPU speedup across D1..D64 at T8 and T24, showing scaling saturation beyond 16 DPUs. |
| **F3** | `figures/F3_ablation_scaling.svg` | `figures/F3_ablation_scaling.png` | 2×3 normalized runtime across cumulative stages A0..A4 (Base -> Tasklets -> DPUs -> Fusion -> DAG). |
| **F4** | `figures/F4_quantization_tradeoff.svg` | `figures/F4_quantization_tradeoff.png` | 2×3 physical quantization execution-cost ratios ($t_{\mathrm{f32}} / t_{\mathrm{int8}}$) at matched topology. |
| **F5** | `figures/F5_p6_transfer.svg` | `figures/F5_p6_transfer.png` | 2×2 forest plot of original P6 contrasts (G/F, F/R, R/U, G/U) with paired bootstrap intervals. |
| **F6** | `figures/F6_final_comparison.svg` | `figures/F6_final_comparison.png` | 2×3 LAST comparison width curves: selected UPMEM f32, UPMEM int8, QuEST CPU P8 and P1, with MRAM limit marker. |

## Table Inventory

| Table | File | Description |
|---|---|---|
| **T1** | `tables/T1_tasklet_speedup.typ` | Tasklet scaling (T1..T24) per primary family and geometric mean speedup. |
| **T2** | `tables/T2_dpu_speedup.typ` | DPU scaling (D1..D64) for T8 and T24 series per primary family and geometric mean. |
| **T3** | `tables/T3_ablation_cumulative.typ` | Cumulative architectural and optimization ablation (A0..A4) speedup and time reduction. |
| **T4** | `tables/T4_quantization_error_cost.typ` | Quantization execution speedup and numerical accuracy disclosure (relative L2, fidelity). |
| **T5** | `tables/T5_selection_winners.typ` | Deterministic topology selection winners (12 primary + 2 supplementary Stress). |
| **T6** | `tables/T6_cold_amortized_costs.typ` | Cold-start planning overhead versus steady execution times and amortized costs ($k=1, 10, 100$). |
| **T7** | `tables/T7_campaign_accounting.typ` | Complete campaign execution accounting, slot reconciliation, and archive verification. |

## Verification

To regenerate all figures, tables, and verify checksums:
```bash
python3 thesis/synthesis/unified_v4/build.py
sha256sum -c thesis/synthesis/unified_v4/SHA256SUMS
```
