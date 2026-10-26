# LTS integration worktree

Branch `rusix/lts-6.18` starts at signed Linux 6.18.58,
`2926d88bb7fc4608fd942453d929c39e4e5ec006`. The tag signature verifies against
kernel.org's documented Greg Kroah-Hartman fingerprint. Published `rusix/main`
remains the previously verified source until integration checks pass.

Project tooling and the Rust square-root port were replayed without importing
newer upstream Makefiles. Original LTS square-root implementation/tests match the
previous engineering source byte-for-byte. BRD differs in legacy parameter parsing;
the same six-case probe must be rerun. Removed the unavailable newer
`FUTEX_ROBUST_UNLOCK` optimization from the server fragment.

Current work: build/verify this LTS baseline in a separate worktree while the
Rust BRD implementation is developed here. Local tests only; hosted CI remains
disabled. See [ADR 0002](docs/adr/0002.md), [BRD design](docs/BRD.md), and
[prior evidence](docs/evidence/container-verification/manifest.json).

Implemented candidate: approximately 1,200 lines of Rust across BRD driver/store
and bio/disk abstractions, plus conditional xarray insertion and synchronous NOIO
scope. Nine new in-kernel tests cover store lifetime, insertion ownership, NOIO
nesting and parameters. Targeted compilation passes in the pinned container after correcting a queue-field
width, cleanup captures, and encoding nonzero minor spacing. The full kernel builds and passes all six unchanged VM contract cases; source
review includes independent ownership review.

LTS local KUnit attempt `linux-out/lts-kunit-001` built and booted: 46 passed,
one intentionally disabled upstream demonstration test skipped. The strict gate
correctly rejected the run. Isolate the required math suites with the existing
KUnit suite filter without changing upstream tests or accepting skips. The filtered replay passed all 24 required math cases. The fresh C BRD
baseline passed all six cases in `linux-out/lts-brd-c-001`.
[Recorded LTS evidence](docs/evidence/lts-baseline/manifest.json) keeps both the
unfiltered failure and passing scoped replay.

Candidate `f1bf14f5c` is frozen in a separate worktree for compilation. The early
[completion experiment](experiments/completion/README.md) identifies C layout,
IRQ, cancellation and scheduler obligations; five host ownership-model tests pass.
It is groundwork for the post-BRD kernel spike, not kernel-runtime evidence.

The first full Rust BRD build at `aa6da498a` passed all six unchanged cases in
`linux-out/lts-brd-rust-001`; [evidence](docs/evidence/brd-rust-initial/manifest.json)
records the linked Rust submission symbol and absence of C submission.
Targeted compile attempts (including failures and an eliminated objtool warning)
are retained in `linux-out/lts-brd-rust-dev/logs/attempts.json`.

The ordinary ext4 fixture has a static Rust PID1 and pinned Debian utilities.
Its image builds with an exact package inventory, and Rust 1.85.1 produces a
static x86_64 init. Six ordered filesystem cases and a strict runner are ready;
guest execution remains pending. The separate BRD ownership KUnit profile has
nine required cases; its acceptance-gate regression tests pass, kernel run pending.

The [initial C/Rust comparison](docs/evidence/brd-rust-initial/comparison.json)
uses byte-identical probe executables and the same tool image. Resolved configs
differ only by Rust BRD selection; both run the six cases without skipped tests.
