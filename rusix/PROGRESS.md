# rusix progress

**Phase 1a: Rust BRD works in the x86_64 block-contract VM; ordinary ext4
verification is running.** Most of the kernel remains C. The integration branch
`rusix/lts-6.18` uses signed Linux 6.18.58 (`2926d88bb7fc`); published main
remains on its previously verified source pending transition checks. Hosted CI
is disabled; all current tests run locally.

Implemented: approximately 1,200 lines of Rust across BRD driver/store and
bio/disk interfaces, plus conditional xarray insertion and synchronous NOIO
scope. [BRD.md](docs/BRD.md) owns contracts, remaining C boundaries and the
provisional invalid-parameter exception. No subsystem divergence point is declared.

| Check | Result and evidence |
| --- | --- |
| LTS provenance and math | Signed tag verified; 24 required math cases pass. An initial unfiltered run correctly failed on an intentionally skipped upstream demonstration test. [Evidence](docs/evidence/lts-baseline/manifest.json). |
| C/Rust BRD block contract | Six cases pass on each implementation. Identical probe ELF/tool image; configurations differ only by Rust selection. [Comparison](docs/evidence/brd-rust-initial/comparison.json). |
| Rust selection | Full kernel at `aa6da498a` links Rust submission and excludes C BRD submission. [Evidence](docs/evidence/brd-rust-initial/manifest.json). |
| Ownership and policy | Nine in-kernel tests pass, zero skips: insertion ownership, discard lifetime/accounting, NOIO nesting and parameters. [Evidence](docs/evidence/brd-ownership/manifest.json). |
| Ordinary userspace/ext4 | Pinned fixture image, static Rust supervisor, ordinary Debian utilities, deterministic staging and strict gate implemented. C baseline kernel is building; paired guest results pending. [Fixture](tests/brd-ext4/README.md), [tool evidence](docs/evidence/ext4-fixture/manifest.json). |
| Early core scouting | Completion boundary/ownership experiment and five host tests pass, including pinned Rust 1.85.1. Five original-C kernel contract tests are written, execution pending. [Experiment](experiments/completion/README.md). |

Last completed declared-target measurement: x86_64 server configuration at
engineering source `4dd0b2c9f`, executable C **5,993,765 bytes**, Rust **151,830
bytes**, unknown **0**. This predates the LTS transition and Rust BRD; rerunning
the selected Rust LTS server profile is pending. Counts include inherited Rust
infrastructure and are not a completion percentage.
[Full measurement](docs/evidence/container-verification/manifest.json).

Next: finish paired ext4 execution, run completion baseline kernel tests, measure
the LTS server target, review remaining Phase 1a gaps, then publish the explicit
baseline transition while preserving main history. arm64, module lifetime,
expanded fault/concurrency stress and performance budgets remain Phase 1b.
See [ADR 0002](docs/adr/0002.md) and [delivery gates](docs/PHASE1.md).

Local raw outputs live under `linux-out/`: `lts-kunit-001`, `lts-brd-c-001`,
`lts-brd-rust-001`, `lts-brd-kunit-001`, and `lts-ext4-c-001`. Initial compiler
failures and the eliminated objtool warning remain in
`lts-brd-rust-dev/logs/attempts.json`; linked evidence preserves failed VM/gate
attempts alongside passes. Historical engineering results remain attributed to
their original commits in the [verification index](docs/VERIFICATION.md).
