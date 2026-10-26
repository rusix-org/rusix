# rusix progress

**Phase 1a: C and Rust BRD pass the x86_64 block and ordinary-userspace ext4
contracts on the declared q35 VM.** Most of the kernel remains C. The integration branch
`rusix/lts-6.18` uses signed Linux 6.18.58 (`2926d88bb7fc`); its verified
source and delivery gates are recorded below. Hosted CI
is disabled; all current tests run locally.

Implemented: approximately 1,200 lines of Rust across BRD driver/store and
bio/disk interfaces, plus conditional xarray insertion and synchronous NOIO
scope. [BRD.md](docs/BRD.md) owns contracts, remaining C boundaries and the
provisional invalid-parameter exception. No subsystem divergence point is declared.

| Check | Result and evidence |
| --- | --- |
| LTS provenance and math | Signed tag verified. All 24 required math cases pass on q35, zero skips. [Current math evidence](docs/evidence/math-q35/manifest.json); [baseline provenance and initial failure](docs/evidence/lts-baseline/manifest.json). |
| C/Rust storage parity | Both pass block6, ordinary ext4 userspace6, six parameter variants and partition5, including clipped reads/writes. Same source, image and four byte-identical guest fixtures; resolved configs differ only by BRD selection. [q35 evidence](docs/evidence/brd-q35/manifest.json). |
| Rust selection | Full kernel at `aa6da498a` links Rust submission and excludes C BRD submission. [Evidence](docs/evidence/brd-rust-initial/manifest.json). |
| Ownership and policy | Nine in-kernel tests pass, zero skips: insertion ownership, discard lifetime/accounting, NOIO nesting and parameters. [Evidence](docs/evidence/brd-ownership/manifest.json). |
| Ordinary userspace | Pinned Debian shell/coreutils/e2fsprogs perform mkfs, buffered/direct I/O, fsync, rename/unlink, remount verification and offline fsck. [Fixture](tests/brd-ext4/README.md), [tool provenance](docs/evidence/ext4-fixture/manifest.json). |
| Early core scouting | Five original-C behavior tests and one Rust-owned/C-visible layout test pass in the kernel. [Kernel evidence](docs/evidence/completion-kernel/manifest.json). Five host ownership-model tests also pass. [Experiment](experiments/completion/README.md). |

Declared x86_64 server measurement at `7effedcbb1bf`: executable C
**5,753,281 bytes**, Rust **145,083**, assembly **45,104**, generated **28**,
linker/padding **2,107,049**, unknown **0**.
[Full target measurement](docs/evidence/lts-target/manifest.json).
This includes inherited Rust infrastructure and is not a completion percentage;
it establishes build/link composition, not server runtime. Rust BRD and legacy
block-autoload are selected; experimental Rust completion is not.

Latest storage comparison: `9d1c1ca5dd`, local `lts-ext4-c-006` and
`lts-ext4-rust-006`, nine q35 boots per implementation. Prior configuration,
diagnostic-matcher and serial-interleaving failures remain in the
[bringup archive](docs/evidence/q35-bringup/manifest.json). Guest markers now
use atomic kernel log records; acceptance still requires exact ordered cases.

Opt-in Rust `complete()` now builds and passes the same nine core cases as C
on q35 at `7effedcbb1bf`; each also passes all nine BRD ownership cases. Linked
archive/object/symbol checks prove exclusive selection, and neither build reports
compiler/objtool diagnostics. [Paired core evidence](docs/evidence/completion-paired/manifest.json).
Default selection remains off: IRQ-context checks, broader integration and the
rest of completion/wait-queue/scheduler ownership remain unfinished.

Next: resolve the remaining Phase 1a parameter/adapter and review gates; extend
core IRQ-context and integration coverage. arm64, module lifetime, expanded fault/concurrency stress and
performance budgets remain Phase 1b.
See [ADR 0002](docs/adr/0002.md) and [delivery gates](docs/PHASE1.md).

Local raw outputs live under `linux-out/`: `lts-kunit-001`, `lts-brd-c-001`,
`lts-brd-rust-001`, `lts-brd-kunit-001`, and `lts-ext4-c-001`. Initial compiler
failures and the eliminated objtool warning remain in
`lts-brd-rust-dev/logs/attempts.json`; linked evidence preserves failed VM/gate
attempts alongside passes. Historical engineering results remain attributed to
their original commits in the [verification index](docs/VERIFICATION.md).
