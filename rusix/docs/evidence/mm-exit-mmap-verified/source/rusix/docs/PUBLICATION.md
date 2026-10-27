# Publication record

The public [rusix-org/rusix](https://github.com/rusix-org/rusix) repository is a
GitHub-recognized fork of `torvalds/linux`. Publish only to `origin`, branch
`rusix/main`; `upstream` is the Linux reference. Retain Linux history, licensing
and attribution. Hosted CI activation follows the [local-only policy](../ci/README.md).

The first source push was verified on 2026-10-25 at
`5520dd71ea4637bca9e82761463c0df53f3feb46`: Rust square root, preserved upstream
tests, comparison evidence and contributor guidance. Historical
[worktree reproduction](evidence/publication-check/manifest.json) and
[repository-native reproduction](evidence/repository-layout/manifest.json)
record the initial build/test checks. A bounded review of 77 project-added blobs
found no unexpected binaries or known credential patterns; it was not a formal
security/license audit.

The signed Linux 6.18.58 transition preserves earlier published history as a merge
parent. Subsequent verified checkpoints include Rust BRD and completion/swait
core policy. [PROGRESS.md](../PROGRESS.md) owns current source identities, evidence,
remaining delivery gates and C dependencies. [Verification](VERIFICATION.md)
retains historical outcomes. Publication alone is not runtime certification.
