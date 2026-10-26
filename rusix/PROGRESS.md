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
nesting and parameters. Compilation and runtime validation of this candidate are
pending; source review is complete, including cross-agent ownership review.

LTS local KUnit attempt `linux-out/lts-kunit-001` built and booted: 46 passed,
one intentionally disabled upstream demonstration test skipped. The strict gate
correctly rejected the run. Isolate the required math suites with the existing
KUnit suite filter without changing upstream tests or accepting skips. The fresh
C BRD six-case baseline is building in `linux-out/lts-brd-c-001`.
