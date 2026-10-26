# Publication record

The public [rusix-org/rusix](https://github.com/rusix-org/rusix) repository is a
GitHub-recognized fork of `torvalds/linux`. `origin` is the publishing remote;
`upstream` is Linux. Default branch: `rusix/main`.

The first source push completed on 2026-10-25 at
`5520dd71ea4637bca9e82761463c0df53f3feb46`. GitHub returned that branch identity,
public fork relationship and default branch. The published layer contained the
Rust square-root replacement, preserved upstream tests, comparison evidence and
contributor guidance. Publication is not runtime or production certification.

Readiness evidence:

- [C/Rust comparison](VERIFICATION.md): both matching kernels passed 26 cases.
- [Independent worktree reproduction](evidence/publication-check/manifest.json)
  at `9047da37a`: preflight, host/gate tests and fresh 26-case VM run passed,
  reusing the same host tools. Historical commands used the then-current layout.
- [Repository-native reproduction](evidence/repository-layout/manifest.json)
  subsequently removed parent-copy requirements.

Linux history, licensing and attribution are retained. The local original
checkout is shallow; the GitHub fork preserves public upstream ancestry.
A bounded review of 77 project-added historical blobs found no unexpected large
binaries or known credential-pattern matches; this was not a formal security or
license audit. The empty `rusix-empty-placeholder` repository contains no project
source. Current implementation/CI status belongs in [PROGRESS.md](../PROGRESS.md).
