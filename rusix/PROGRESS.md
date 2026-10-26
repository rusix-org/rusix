# rusix progress

**Rust BRD passes the x86_64 block and ordinary-userspace ext4 contracts;
opt-in Rust completion entry points pass paired core and signal tests.**
Most of the kernel remains C. Linux 6.18.58 (`2926d88bb7fc`) is the behavioral
baseline. Hosted CI remains disabled; current verification runs locally.

Public development lives on `rusix/main`; the pinned foundation at
`e479bce68c45` preserves earlier history. No subsystem divergence point is declared.
[ADR 0002](docs/adr/0002.md) owns the target and
[Phase 1](docs/PHASE1.md) owns delivery gates.

| Check | Verified result |
| --- | --- |
| LTS provenance/math | Signed tag verified; all 24 required math cases pass on q35, zero skips. [Math](docs/evidence/math-q35/manifest.json), [provenance](docs/evidence/lts-baseline/manifest.json). |
| Storage parity | At `9d1c1ca5dd`, C/Rust each pass block6, ext4 userspace6, six parameter variants and partition5, including clipped reads/writes. Four byte-identical guest fixtures; configs differ only by BRD selection. [Evidence](docs/evidence/brd-q35/manifest.json). |
| Ordinary userspace | Pinned Debian shell/coreutils/e2fsprogs perform mkfs, buffered/direct I/O, fsync, rename/unlink, remount verification and offline fsck. [Fixture](tests/brd-ext4/README.md). |
| Core migration | At `afaedde2732b`, C/Rust each pass 21 core cases plus nine BRD cases, then 21 isolated core cases on q35/KVM SMP2. All fourteen completion entry points link exclusively; wait addresses remain in scheduler text. Zero skips and no compiler/objtool diagnostics. [Evidence](docs/evidence/completion-status/manifest.json). |

Rust implements BRD/store and bio/disk interfaces, conditional xarray
insertion/NOIO scope, and all fourteen completion.c entry points. The latter uses pinned stack waiters and scoped LKMM accesses while retaining C queue/scheduler primitives. Its
[migration record](experiments/completion/README.md) owns contracts, test inventory
and remaining boundaries. It remains off by default and restricted to builtins,
with known incompatible external counter-access drivers excluded.

Declared x86_64 server measurement at `7effedcbb1bf`: executable C
**5,753,281 bytes**, Rust **145,083**, assembly **45,104**, generated **28**,
linker/padding **2,107,049**, unknown **0**.
[Measurement](docs/evidence/lts-target/manifest.json). This predates the new core
slice, includes inherited Rust infrastructure, and is not a completion percentage
or server runtime result. That target selects Rust BRD and C completion.

Remaining Phase 1a work includes the provisional BRD invalid-parameter exception,
parameter adapters and review gates; [BRD.md](docs/BRD.md) owns those details.
For core work, continue queue ownership while preserving list/scheduler contracts.
Untimed signal paths, deadline races, forced diagnostic failure paths and scheduler
integration remain unfinished. arm64, modules, expanded fault stress
and performance budgets remain Phase 1b.

Failed attempts and warnings are retained: [wait bringup](docs/evidence/completion-wait-initial/manifest.json)
includes a test integer-conversion failure and a runtime-pass build with Rust
warnings, both resolved before the current clean pair. Earlier
[q35 bringup](docs/evidence/q35-bringup/manifest.json) retains configuration and
serial-diagnostic failures. Raw logs/binaries live in `linux-out/<run>`;
committed manifests record source/config/tool identities. See the
[verification index](docs/VERIFICATION.md) for historical evidence.

The latest pair verifies pending/enrolled interruption on dedicated threads,
token precedence over pending signals, killable waits ignoring nonfatal signals,
and competing try-wait consumers. A first test-only allocation-error conversion
failure is retained in the [status evidence](docs/evidence/completion-status/manifest.json).
[Core/ext4 integration](docs/evidence/completion-ext4/manifest.json) now passes
at `3df316f9971f`: both kernels use Rust BRD and byte-identical fixtures; only
completion selection differs. Each passes all nine block/ext4/parameter/partition
boots, with no compiler diagnostics. KUnit is disabled in those userspace guests.

At `6bc02bee8561`, four shared swait policies are also Rust. The instrumented
C/Rust pair each passes 35 combined cases (26 core + nine BRD), then 26 isolated
core cases with zero skips and no compiler diagnostics. BUG, lockdep/raw-lock
nesting, atomic-sleep and list checks are enabled.
[Debug evidence](docs/evidence/swait-debug/manifest.json).
The matching ordinary-userspace pair passes all nine boots each, with identical
fixtures and only the implementation option differing.
[Ext4 evidence](docs/evidence/swait-ext4/manifest.json) retains the initial fixture
staging failure as well as the successful retry.

Five outer swait wrappers are now translated, preserving full state-publication
barriers, careful lockless removal and detached-batch wake semantics. Three new
cases bring the required core inventory to 29. This is working code until its
own paired verification; the results above certify only
`6bc02bee8561`. Initializers, C list adapters, raw locks and scheduler dependencies
remain to migrate.
