# Thesis synthesis

Deterministic publication calculations from `8ead323f1a8700d0457d6b509ce92f3d56e441e2`.
The implementation, measurements and original P6 statistics remain unchanged.

Use a **separate Python ≥3.11 environment**. Do not update the research environment.

```sh
python -m pip install -r thesis/synthesis/requirements.txt
python -m unittest discover -s thesis/synthesis/tests -v
python thesis/synthesis/build.py --repo .
python thesis/synthesis/verify.py --repo .
```

The build reads pinned Git objects, verifies both accepted package manifests, and
checks all final-campaign medians, MADs, coverage and paired-bootstrap intervals
against the recorded measurement CSV. It does not run a simulator, access ETH,
refit P6, select new width-study resources, or restore deleted documents.

`generated/` contains canonical CSVs, Typst tables, SVG/PNG figures, source hashes,
verification results, a claim ledger and one short results summary. Every figure
and table has an indexed caption, dataset and selection. SVG is the vector format
for Typst; PNG is for inspection. Examples:

```typst
#include "synthesis/generated/tables/accounting.typ"
#figure(image("synthesis/generated/figures/t_hs_n18_speedup.svg"),
  caption: [HS18 tasklet scaling; descriptive paired-block intervals.])
```

Adjust only the manuscript-relative include path. Table fragments need no package.
`generated/gallery.typ` compiles all tables for layout inspection:

```sh
python thesis/synthesis/verify.py --repo . --typst typst \
  --typst-proof /path/outside/generated/table-proof.pdf
```

Output must not already exist. `verify.py` rebuilds independently in temporary
storage and requires identical artifacts. Byte identity is guaranteed only for an
identical Python/NumPy/Matplotlib/FreeType/font environment; its fingerprints are
recorded. Cross-environment numerical verification and binary figure equality are
not interchangeable.

## Interpretation

Prepared-call time is primary for resource studies; job-to-state time is primary
for CPU comparisons. Ratios are numerator/denominator, and time reduction is
`100*(1-1/ratio)`. Warmups never enter summaries. Unsupported points are retained.
Historical studies are not pooled with the final campaign. P6 intervals are
imported unchanged, and method aliases are not independent observations. Numerical
quantization CSVs describe software characterization, not physical speed.
Historical chat-context transcriptions remain explicitly marked as unverified
numeric context. No global optimum, SOTA victory, causal bottleneck attribution,
statistical equivalence, or universal int8 quality claim is inferred.

Tests contain a full-shape **synthetic** campaign and small, attributed real-data
fixtures. They do not replace the mandatory full frozen-source build and verify.
