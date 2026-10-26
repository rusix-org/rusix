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

The LTS transition adopts signed Linux 6.18.58 and preserves the earlier main
as a merge parent. Its verified implementation at `7effedcbb1bf` builds with the
pinned container, passes 24 math cases on q35, and passes paired C/Rust completion
checks. [Paired q35 storage](evidence/brd-q35/manifest.json) at `9d1c1ca5dd`
verifies BRD, ext4, parameters and partitions; subsequent implementation changes
only correct the opt-in completion FFI type. [Current target inventory](evidence/lts-target/manifest.json)
records linked C/Rust contributions. Phase 1a remains in progress and hosted CI
remains disabled; see the progress ledger for unfinished gates.

The next core checkpoint translates all fourteen completion.c entry points.
[Core/signal parity](evidence/completion-status/manifest.json) verifies 21 cases
per implementation; [ordinary ext4 integration](evidence/completion-ext4/manifest.json)
verifies matching Rust-BRD kernels differing only in completion selection.
The option stays experimental/default-off, with C queue/scheduler dependencies
and configuration bounds recorded in the migration record. Hosted execution
remains disabled; this checkpoint adds local integration profiles only.
