# rusix progress

**Phase 1a: C and Rust BRD pass the x86_64 block and ordinary-userspace ext4
contracts on the initial i440fx fixture.** Most of the kernel remains C. The integration branch
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
| Ordinary userspace/ext4 | Pinned fixture image, static Rust supervisor, ordinary Debian utilities, deterministic staging and strict gate implemented. C and Rust each pass all six filesystem cases using an identical initramfs and source commit. [Paired evidence](docs/evidence/brd-ext4/manifest.json). [Fixture](tests/brd-ext4/README.md), [tool evidence](docs/evidence/ext4-fixture/manifest.json). |
| Early core scouting | Five original-C behavior tests and one Rust-owned/C-visible layout test pass in the kernel. [Kernel evidence](docs/evidence/completion-kernel/manifest.json). Five host ownership-model tests also pass. [Experiment](experiments/completion/README.md). |

Last completed LTS x86_64 server measurement at `57820ea1ec`: executable
C **5,753,137 bytes**, Rust **145,083**, assembly **45,104**, generated **28**,
linker/padding **2,107,065**, unknown **0**. Raw report:
`linux-out/lts-server-002/logs/languages.json`. This includes inherited Rust
infrastructure and is not a completion percentage; it establishes build/link
composition, not server runtime. The newly enabled legacy block-autoload option
requires an updated measurement.

Current validation: the first q35 replay exposed ACPI initialization errors and
an on-demand device failure from missing PCI/legacy block-autoload configuration.
Its otherwise passing block/ext4 markers are insufficient for acceptance. The
failed attempt remains in `lts-ext4-c-002`; corrected configs and gates now reject
ACPI diagnostics. A fresh recorded C replay is running before the matching Rust
replay. Next: finish those paired parameter/on-demand probes, rerun core tests on
q35, record the updated server measurement, and review remaining Phase 1a gaps
before publishing the baseline transition. arm64, module lifetime, expanded
fault/concurrency stress and performance budgets remain Phase 1b.
See [ADR 0002](docs/adr/0002.md) and [delivery gates](docs/PHASE1.md).

Local raw outputs live under `linux-out/`: `lts-kunit-001`, `lts-brd-c-001`,
`lts-brd-rust-001`, `lts-brd-kunit-001`, and `lts-ext4-c-001`. Initial compiler
failures and the eliminated objtool warning remain in
`lts-brd-rust-dev/logs/attempts.json`; linked evidence preserves failed VM/gate
attempts alongside passes. Historical engineering results remain attributed to
their original commits in the [verification index](docs/VERIFICATION.md).
