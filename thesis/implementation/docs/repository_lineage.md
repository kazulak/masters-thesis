# Scientific Repository Lineage

This standalone repository preserves the original Git ancestry of the thesis work from:

```text
https://github.com/kazulak/Masters
```

The standalone current tree is a publication cleanup descendant of:

```text
9fdecfe0c01c769ceb5b7410e1aa2d38a089dc87
```

## Frozen scientific identities

| Role                             | Commit                                     | Tag                                      |
| -------------------------------- | ------------------------------------------ | ---------------------------------------- |
| Final composed UPMEM executor    | `459935f586fdd16c82013838e6d27a12604c3093` | `thesis-upmem-kernel-schedule-system-v1` |
| P6 qualified software/controller | `2beea27411c16e90ed76988613ddb00bcc09f942` | `thesis-upmem-cost-guided-software-v1`   |
| P6 accepted result/audit package | `8df2ebac61bacd08309ea490309be5a8dcb943b2` | `thesis-upmem-cost-guided-results-v1`    |

These tags remain attached to their original commits.

The standalone publication commit is not a scientific source rewrite.

## Historical ancestry

Older preparation and qualification commits remain real ancestors of the standalone `main`.

This is intentional because several retained provenance checks validate relationships using:

```bash
git merge-base --is-ancestor <historical-source> HEAD
```

The repository must not special-case those checks merely because it has been republished.

## Archive history

The original repository's `archive/*` tags preserve intentionally divergent historical branch tips.

They remain in `kazulak/Masters` and are not imported into the standalone publication repository.

## Current tree

The current standalone tree contains only thesis/publication material.

Historical unrelated university material may still be visible when inspecting old Git commits because original ancestry is intentionally preserved.

## Evidence rule

Never replace embedded historical source SHAs with the current standalone `HEAD`.

Scientific evidence is bound to the source under which it was created, not to the latest documentation/package commit.
