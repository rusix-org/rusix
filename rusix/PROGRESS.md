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
| Ownership and policy | Nine in-kernel BRD cases pass, zero skips: insertion ownership, discard lifetime/accounting, NOIO nesting and parameters. [Current evidence](docs/evidence/completion-paired/manifest.json). |
| Ordinary userspace | Pinned Debian shell/coreutils/e2fsprogs perform mkfs, buffered/direct I/O, fsync, rename/unlink, remount verification and offline fsck. [Fixture](tests/brd-ext4/README.md), [tool provenance](docs/evidence/ext4-fixture/manifest.json). |
| Core migration | Opt-in Rust `complete()` and C each pass nine q35 cases: behavior, Rust-owned/C-visible layout, worker handoff, token conservation and timeout cleanup. Linked object/symbol checks prove exclusive selection. [Paired evidence](docs/evidence/completion-paired/manifest.json), [remaining core boundary](experiments/completion/README.md). |

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

The paired core builds at `7effedcbb1bf` report no compiler/objtool diagnostics.
Rust completion remains off by default: IRQ-context checks, broader integration
and the rest of completion/wait-queue/scheduler ownership remain unfinished.

On `rusix/completion-broadcast`, Rust now also implements `complete_all()`.
C and Rust each pass ten core cases plus nine BRD cases at `abec6b9cd125`,
with exclusive symbol selection and no compiler/objtool diagnostics. The new
broadcast case observes two queued waiters and requires prompt wakeup, then
checks late waits. [Paired evidence](docs/evidence/completion-broadcast/manifest.json).
The queue-inspection helper is KUnit-only and excluded from the server target.

Next: migrate current-CPU signaling and the common wait engine, then the
lockless counter checks; resolve the remaining Phase 1a parameter/adapter and review gates; extend
core IRQ-context and integration coverage. arm64, module lifetime, expanded fault/concurrency stress and
performance budgets remain Phase 1b.
See [ADR 0002](docs/adr/0002.md) and [delivery gates](docs/PHASE1.md).

Full local logs and binaries live under `linux-out/<run>`; committed manifests
record source/config/tool identities and retained failures. Historical results
remain attributed to their commits in the [verification index](docs/VERIFICATION.md).

Rust `complete_on_current_cpu()` now also passes its paired local gates at
`7b78a56b5aa8`: 12 core cases and nine BRD cases per implementation, then 12
isolated core cases, zero skips and no compiler/objtool diagnostics. All three
signaling symbols are verified in their selected defining object and kernel.
[Current-CPU evidence](docs/evidence/completion-current-cpu/manifest.json).
Queued wakeup tests now bound total elapsed time before the worker deadline,
closing a false-pass possibility under a delayed producer. The next production
slice is the common blocking wait engine and its nine entry points.
