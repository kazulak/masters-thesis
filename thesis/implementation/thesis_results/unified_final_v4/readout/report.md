# Unified Evaluation v4 Corrected Readout Receipt

Original published result commit: `d886e3b7e04a4c3be4a6d4d463206b66f5c0c2a0`
Base commit: `683194cf4895420898297095a0d92e83c282b355`
Implementation commit: `f6b570a98a610d41b5b16401a42ce12a94042d38`
Evaluator commit: `73e415abac7bcac3609693d4eb378b57bf5a42ec`
Run ID: `unified-v4-20260912T041549Z-73e415abac7b`

Protocol SHA-256: `4acdada0dd2aa7840a79cd18d0b0303dad7393f5b7d7e9e7884beb6d50558c6f`
Manifest SHA-256: `98cd0dc2ca6d5b9d34ff3496004193265d6d1f146627763bc7248235c091364c`
Selection SHA-256: `a1b8ba879d353490c51bc43051ff7ef8ff0c1dc74490d8ee592d6b6e00a5add1`
Final Manifest SHA-256: `7c106a45779a465c51cd4ad41cc17e8587236c4fd9d365315dc0a334d06a0bfb`

## Slot accounting

Calibration: 2674 planned, 2674 issued, 2674 successful; 714 duplicate slots avoided.

| Final route | Planned | Issued | Successful | Not issued |
| --- | ---: | ---: | ---: | ---: |
| upmem_f32 | 312 | 276 | 276 | 36 |
| upmem_int8 | 312 | 276 | 276 | 36 |
| numpy_f32_p1 | 312 | 276 | 276 | 36 |
| quest32_p8 | 312 | 312 | 312 | 0 |
| quest32_p1 | 312 | 312 | 312 | 0 |
| Total | 1560 | 1452 | 1452 | 108 |

## R-path admission outcomes

52 searches, 6656 proposals, 46 selected R paths, 6 no-selected-R-path outcomes.

The following cases have `no_selected_R_path` / `no_admitted_candidate`: `bb84_n26`, `bv_n26`, `edc_n25`, `hs_n26`, `qrng_n26`, `xor_n26`.

The two UPMEM routes and NumPy same-DAG require the shared R path. Their unsupported slots were never issued. QuEST remains executable. These are planning/admission frontiers, not physical execution failures.

## Physical campaign and retention

108 qualification + 2674 calibration + 552 final = **3334 physical issues**, within the 3406 ceiling. 72 allocated physical final slots were not issued.

Qualification used 54 configurations, each replayed twice. The frozen retention receipt records two verified copies of 8288 files. This readout joins raw disk receipts; it does not itself assert a new dual-archive byte comparison.

## Selection and timing definitions

Topology winners: 14. Rule: greedy calibration, blocks 1..5, min median then D then T; no quality tuning for int8.

R-path preparation/search is a one-time offline cost. Cached-path job-to-state runs from the preloaded circuit specification to an owned contiguous complete statevector with the path available. Estimated per-call cost is search/k + cached job-to-state for k=1,10,100. These are derived estimates, not separately measured cold executions. No-path cases retain search time and have no executable cached-path cost.

One-rank DPU scaling saturated after D16, with lower aggregate speedup at D32 and D64. This observation alone does not attribute dominance to a communication mechanism.
