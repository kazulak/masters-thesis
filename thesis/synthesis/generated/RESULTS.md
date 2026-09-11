# Thesis synthesis

Frozen evidence is unchanged. All final-campaign summaries were checked against its measurement CSV.
Ratios are numerator time / denominator time; values above one favour the denominator.
Final campaign intervals reproduce the existing paired-block calculation; P6 intervals are imported.

## Accounting

| Suite | Cells | Attempts | Warmups | Measured success | Measured unsupported |
|---|---:|---:|---:|---:|---:|
| T | 48 | 288 | 48 | 240 | 0 |
| D | 28 | 168 | 28 | 140 | 0 |
| A | 15 | 120 | 15 | 105 | 0 |
| W | 144 | 864 | 144 | 690 | 30 |

## Findings

- **T-hs_n18-None:** Lowest observed prepared-call median at 12 tasklets; endpoint speedup 1.9049x. Descriptive minimum median in measured grid; not an independent optimum confirmation.
- **T-stress_n16_l2-None:** Lowest observed prepared-call median at 18 tasklets; endpoint speedup 3.3851x. Descriptive minimum median in measured grid; not an independent optimum confirmation.
- **D-hs_n18-8:** Lowest observed prepared-call median at 4 DPUs; endpoint speedup 1.1296x. Descriptive minimum median in measured grid; not an independent optimum confirmation.
- **D-hs_n18-24:** Lowest observed prepared-call median at 4 DPUs; endpoint speedup 1.0972x. Descriptive minimum median in measured grid; not an independent optimum confirmation.
- **D-stress_n16_l2-8:** Lowest observed prepared-call median at 16 DPUs; endpoint speedup 1.6114x. Descriptive minimum median in measured grid; not an independent optimum confirmation.
- **D-stress_n16_l2-24:** Lowest observed prepared-call median at 16 DPUs; endpoint speedup 1.4725x. Descriptive minimum median in measured grid; not an independent optimum confirmation.
- **A-edc_n17-matched_combined_executor:** matched_combined_executor: baseline/alternative 8.9854x; descriptive interval [8.9719, 9.0772]. Matched final-source cell. Interval is not an equivalence test; A0 already uses the panel kernel.
- **A-hs_n18-matched_combined_executor:** matched_combined_executor: baseline/alternative 3.7843x; descriptive interval [3.7739, 3.8814]. Matched final-source cell. Interval is not an equivalence test; A0 already uses the panel kernel.
- **A-stress_n16_l2-matched_combined_executor:** matched_combined_executor: baseline/alternative 6.2520x; descriptive interval [6.1966, 6.3208]. Matched final-source cell. Interval is not an equivalence test; A0 already uses the panel kernel.
- **CPU-bb84:** UPMEM had lower median job-to-state time than QuEST P8 at 0/7 mutually qualified widths. Fixed greedy D64/T24 UPMEM; QuEST is a conventional reference, not a proven SOTA optimum. Missing UPMEM points excluded from ratios, not coverage.
- **CPU-bv:** UPMEM had lower median job-to-state time than QuEST P8 at 0/7 mutually qualified widths. Fixed greedy D64/T24 UPMEM; QuEST is a conventional reference, not a proven SOTA optimum. Missing UPMEM points excluded from ratios, not coverage.
- **CPU-edc:** UPMEM had lower median job-to-state time than QuEST P8 at 0/7 mutually qualified widths. Fixed greedy D64/T24 UPMEM; QuEST is a conventional reference, not a proven SOTA optimum. Missing UPMEM points excluded from ratios, not coverage.
- **CPU-hs:** UPMEM had lower median job-to-state time than QuEST P8 at 0/7 mutually qualified widths. Fixed greedy D64/T24 UPMEM; QuEST is a conventional reference, not a proven SOTA optimum. Missing UPMEM points excluded from ratios, not coverage.
- **CPU-qrng:** UPMEM had lower median job-to-state time than QuEST P8 at 0/7 mutually qualified widths. Fixed greedy D64/T24 UPMEM; QuEST is a conventional reference, not a proven SOTA optimum. Missing UPMEM points excluded from ratios, not coverage.
- **CPU-xor:** UPMEM had lower median job-to-state time than QuEST P8 at 0/7 mutually qualified widths. Fixed greedy D64/T24 UPMEM; QuEST is a conventional reference, not a proven SOTA optimum. Missing UPMEM points excluded from ratios, not coverage.
- **P6-R/U:** Accepted family-balanced R/U: 1.001343x. Original P6 only; no pooling with new campaign. R/U near one does not establish equivalence or justify retroactive method rejection.
- **P6-F/U:** Accepted family-balanced F/U: 1.040425x. Original P6 only; no pooling with new campaign. R/U near one does not establish equivalence or justify retroactive method rejection.
- **P6-G/U:** Accepted family-balanced G/U: 1.266508x. Original P6 only; no pooling with new campaign. R/U near one does not establish equivalence or justify retroactive method rejection.
- **P6-F/R:** Accepted family-balanced F/R: 1.039030x. Original P6 only; no pooling with new campaign. R/U near one does not establish equivalence or justify retroactive method rejection.
- **P6-G/R:** Accepted family-balanced G/R: 1.264810x. Original P6 only; no pooling with new campaign. R/U near one does not establish equivalence or justify retroactive method rejection.
- **P6-G/F:** Accepted family-balanced G/F: 1.217299x. Original P6 only; no pooling with new campaign. R/U near one does not establish equivalence or justify retroactive method rejection.
- **P6-regressions:** U was slower than G in 4/12 cells; worst G/U=0.687613x (45.43% more time for U). Original inclusive measurement; not proof of an arithmetic slowdown or a causal attribution to one function.

## Historical and numerical evidence

The 32-entry mechanism ledger preserves positive, negative, mixed and exploratory findings.
Historical narrative transcriptions are not reconstructed observations. Entries marked as chat-context transcriptions remain unverified numeric context.
Quantization plots use the software-characterization CSV, not new physical measurements. Physical int8 replay and topology findings remain historical.

## Use

Use FIGURES.csv and TABLES.csv for captions, source datasets and limitations. SVG is the vector format for Typst; PNG is for inspection.
Typst fragments use local formatting and require no third-party Typst package. Include tables from tables/*.typ; gallery.typ is a standalone inspection document.
Source references and per-input hashes are in PROVENANCE.json. Full observation receipts and original native archives are not revalidated by this synthesis.
No GPU, energy, new circuit, new benchmark, path search, threshold change or model refit is included.
