# Third-party software

No project-wide license is added by this documentation cleanup. Each external
component retains its upstream license and attribution requirements.

The Git submodules under `thesis/implementation/external/` are pinned to:

| Component | Commit | Role |
| --- | --- | --- |
| [QuEST](https://github.com/quest-kit/QuEST) | `9d7618d7263e3bfba433b88cf1eac0647f08fa0a` | Full-state reference |
| [SimplePIM](https://github.com/CMU-SAFARI/SimplePIM) | `1d639c53532555f01e9f71d872e7712b166d6cba` | Bounded initialization/management support |
| [PID-Comm](https://github.com/AIS-SNU/PID-Comm) | `cecc39e29e6576ced73b2041db6e357769a6531a` | Retained reference, not the final communication provider |

Consult each pinned upstream license. The UPMEM SDK is an external system dependency;
Python dependencies retain their respective terms. This repository does not relicense them.
