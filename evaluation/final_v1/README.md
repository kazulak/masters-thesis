# Final evaluation v1

A separate, bounded final measurement campaign importing the thesis implementation at
`f6b570a98a610d41b5b16401a42ce12a94042d38` without modifying it.

`scope.json` fixes workloads, resource grids, repetitions, limits and quality rules.
`tools/` implements generation, qualification, collection, readout and archive checks.
`native/` contains only a gate-stream bridge to pinned QuEST and a one-rank inventory tool.
`historical_results.csv` labels transcribed earlier findings; original P6 data are not refitted.

Run the delivery tests with `python3 -m unittest discover -s tests -v`.
These are not physical qualification. The external evaluation protocol and operator commands
require real QuEST, SDK and hardware qualification before performance collection.

No GPU, energy, multi-rank, new kernel or new quantizer is introduced.
