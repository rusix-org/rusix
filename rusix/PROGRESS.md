# rusix progress

**Rust BRD passes the x86_64 block and ordinary-userspace ext4 contracts;
opt-in Rust completion signaling and blocking waits pass paired core tests.**
Most of the kernel remains C. Linux 6.18.58 (`2926d88bb7fc`) is the behavioral
baseline. Hosted CI remains disabled; current verification runs locally.

The published foundation is `rusix/main` at `e479bce68c45`. Additional core work
is committed on `rusix/completion-broadcast`, not yet published. No subsystem
divergence point is declared. [ADR 0002](docs/adr/0002.md) owns the target and
[Phase 1](docs/PHASE1.md) owns delivery gates.

| Check | Verified result |
| --- | --- |
| LTS provenance/math | Signed tag verified; all 24 required math cases pass on q35, zero skips. [Math](docs/evidence/math-q35/manifest.json), [provenance](docs/evidence/lts-baseline/manifest.json). |
| Storage parity | At `9d1c1ca5dd`, C/Rust each pass block6, ext4 userspace6, six parameter variants and partition5, including clipped reads/writes. Four byte-identical guest fixtures; configs differ only by BRD selection. [Evidence](docs/evidence/brd-q35/manifest.json). |
| Ordinary userspace | Pinned Debian shell/coreutils/e2fsprogs perform mkfs, buffered/direct I/O, fsync, rename/unlink, remount verification and offline fsck. [Fixture](tests/brd-ext4/README.md). |
| Core migration | At `db842fffa766`, C/Rust each pass 16 core cases plus nine BRD cases, then 16 isolated core cases on q35/KVM SMP2. Three signaling and nine wait entry points link exclusively; wait addresses remain in scheduler text. Zero skips and no compiler/objtool diagnostics. [Evidence](docs/evidence/completion-wait/manifest.json). |

Implemented Rust includes approximately 1,200 lines across BRD/store and bio/disk
interfaces, conditional xarray insertion/NOIO scope, and completion signaling
and blocking wait policy. The latter uses pinned stack waiters and scoped LKMM
accesses while retaining C queue/scheduler primitives. Its
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
For core work, next verify dedicated-thread signal handling, then migrate
try-wait/status operations together after the counter-access audit. IRQ/debug
instrumentation, deadline races, selected-core ext4 integration, queue ownership
and scheduler integration remain unfinished. arm64, modules, expanded fault stress
and performance budgets remain Phase 1b.

Failed attempts and warnings are retained: [wait bringup](docs/evidence/completion-wait-initial/manifest.json)
includes a test integer-conversion failure and a runtime-pass build with Rust
warnings, both resolved before the current clean pair. Earlier
[q35 bringup](docs/evidence/q35-bringup/manifest.json) retains configuration and
serial-diagnostic failures. Raw logs/binaries live in `linux-out/<run>`;
committed manifests record source/config/tool identities. See the
[verification index](docs/VERIFICATION.md) for historical evidence.

Current working slice: Rust now supplies the remaining `try_wait_for_completion`
and `completion_done` entry points, preserving their lockless checks and locked
synchronization. Four dedicated-thread signal cases and a competing-consumer
case bring the strict core inventory to 21. Signal tests verify pending/enrolled
interruption, token precedence and nonfatal-signal timeout behavior. Paired
build/runtime verification is pending; the 16-case archive predates this slice.

The first status/signal comparison at `9018753694a5` stopped in the new
consumer test: its explicit spawn-failure branch needed `AllocError` converted
to the kernel `Error`. The cleanup broadcast is preserved and the conversion
is fixed. Failed logs remain in `linux-out/lts-completion-status-c-001`;
no runtime result was produced for that source.
