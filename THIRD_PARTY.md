# Licensing and third-party material

Original project code, build scripts and tests use the [MIT License](LICENSE).
Original research data, prose, figures, table outputs and review PDF use
[Creative Commons Attribution 4.0 International](LICENSE-DATA). Attribution should
identify Tomasz Kazulak, this repository, the release version and any modifications;
[CITATION.cff](CITATION.cff) supplies the artifact citation.

These grants apply only to original material the author can license. Third-party
software, quotations, figures, benchmark material and bundled upstream notices
retain their existing terms. They are not relicensed by the root licenses.
Git history retains the notices and provenance of historical source snapshots.

| Component | Pinned upstream source | Terms and retained notice |
| --- | --- | --- |
| QuEST | `9d7618d7263e3bfba433b88cf1eac0647f08fa0a` | [MIT](release/licenses/QuEST.txt) |
| SimplePIM | `1d639c53532555f01e9f71d872e7712b166d6cba` | [MIT](release/licenses/SimplePIM.txt) |
| PID-Comm | `cecc39e29e6576ced73b2041db6e357769a6531a` | [BSD 3-Clause](release/licenses/PID-Comm.txt) |
| QASMBench | `357b942396d5c2b7cbc1c229c585a6ef5ccaebac` | [Battelle license](release/licenses/QASMBench-LICENSE.txt) and [notice](release/licenses/QASMBench-NOTICE.txt) |

The first three are Git submodules in `thesis/implementation/external/`.
QASMBench is the cited reference for the HS workload construction; the pinned
LICENSE and NOTICE are retained without replacing them with a generic label.
Third-party sources cited by the literature review retain their rights.

The UPMEM SDK is an externally installed dependency and is not bundled in the
release assets. It requires its own upstream terms. Python packages, Typst,
DejaVu fonts and system tooling retain their upstream licenses; the release
records versions and font hashes, not ownership of those dependencies.
