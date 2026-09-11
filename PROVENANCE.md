# Provenance

This repository is the standalone Master's thesis research artifact derived from:

```text
https://github.com/kazulak/Masters
```

## Publication source

The standalone current tree was prepared from:

```text
repository:
kazulak/Masters

branch:
main

polished source commit:
9fdecfe0c01c769ceb5b7410e1aa2d38a089dc87
```

Unlike a file-only export, this repository intentionally preserves the original Git ancestry required by historical provenance checks.

The current standalone tree removes unrelated coursework/monorepo material, but historical commits remain in Git ancestry.

This preserves the semantic meaning of recorded source commits such as:

```text
c86b589d971ef241c5f42d0da33fc772dd9c2107
```

and allows existing ancestry guards to continue verifying that historical preparation sources precede the current repository state.

## Frozen scientific identities

The following original commit identities remain authoritative:

### Final composed UPMEM executor

```text
459935f586fdd16c82013838e6d27a12604c3093
tag:
thesis-upmem-kernel-schedule-system-v1
```

### P6 qualified software/controller

```text
2beea27411c16e90ed76988613ddb00bcc09f942
tag:
thesis-upmem-cost-guided-software-v1
```

### P6 accepted result/audit package

```text
8df2ebac61bacd08309ea490309be5a8dcb943b2
tag:
thesis-upmem-cost-guided-results-v1
```

The corresponding reachable `thesis-*` tags are retained at their exact original commits.

They are never moved to the standalone publication commit.

## Tags intentionally not imported

Original:

```text
archive/*
```

tags are not published in this standalone repository.

Those tags preserve intentionally divergent historical branch tips and remain available in:

```text
kazulak/Masters
```

They are not required for execution/evidence provenance of the final accepted thesis system.

## Current-tree inclusion policy

The standalone tip contains:

```text
README.md
PROVENANCE.md
REPRODUCIBILITY.md
THIRD_PARTY.md
.github/
.gitignore
.gitmodules
thesis/
```

Within `thesis/`, the complete active implementation, documentation, tracked results, SLR PDF, research plans, and P6 operational runbook are retained.

## Current-tree exclusions

The standalone tip excludes exactly:

```text
thesis/legacy/
thesis/common.mk
```

and all unrelated top-level university/coursework material.

Those files remain available in the preserved historical ancestry and in the original `kazulak/Masters` repository.

## Path preservation

The `thesis/` prefix is intentionally retained because research scripts and accepted records use paths such as:

```text
thesis/implementation/...
thesis/upmem-system-and-path-optimization-plan-v2.md
```

Do not flatten this repository.

## Embedded evidence identities

Accepted evidence keeps its original:

```text
source_sha
execution_source
binary hashes
problem/plan identities
environment identity
experiment/run/session/sample identities
archive hashes
```

Do not rewrite any of those values to the standalone publication commit.

## Publication commit

The cleanup/publication commit added after:

```text
9fdecfe0c01c769ceb5b7410e1aa2d38a089dc87
```

changes repository presentation and standalone metadata only.

It does not redefine the source of historical physical measurements.
