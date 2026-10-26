# rusix progress

**Rust BRD passes x86_64 block and ordinary-userspace ext4 contracts;
all fourteen completion entry points and all ten swait.c entry points have verified
opt-in Rust implementations; twenty-three generic wait and ten bit-wait entries now pass parity too.** Most of the kernel remains C. Linux 6.18.58
(`2926d88bb7fc`) is the behavioral baseline. Hosted CI remains disabled;
verification runs locally. No subsystem divergence point is declared.

Public development lives on `rusix/main`. [ADR 0002](docs/adr/0002.md) owns the
target; [Phase 1](docs/PHASE1.md) owns delivery gates.

| Check | Verified result |
| --- | --- |
| LTS provenance/math | Signed tag verified; all 24 required math cases pass on q35, zero skips. [Math](docs/evidence/math-q35/manifest.json), [provenance](docs/evidence/lts-baseline/manifest.json). |
| Storage parity | At `9d1c1ca5dd`, C/Rust BRD each pass block6, ext4 userspace6, six parameter variants and partition5. Four identical guest fixtures; configs differ only by BRD selection. [Evidence](docs/evidence/brd-q35/manifest.json). |
| Core and shared queue policy | At `5234e2809e9b`, C/Rust debug and plain pairs each pass 70 combined (61 core + nine BRD), then 61 isolated core on q35/KVM SMP2. All 14 completion, 10 swait, 23 generic wait and 10 bit-wait definitions link exclusively. Zero skips or compiler/objtool diagnostics. [Evidence](docs/evidence/wait-locked/manifest.json). |
| Ordinary-userspace integration | Same source, Rust BRD in both; only core selection differs. Both pass nine block/ext4/parameter/partition boots, including six filesystem, four poll/epoll and two blocking eventfd/timerfd read cases. Identical fixtures; no compiler diagnostics. [Evidence](docs/evidence/wait-locked-ext4/manifest.json). |

Rust implements BRD/store and bio/disk interfaces, conditional xarray insertion,
NOIO scope, completion/swait policy and generic wait initialization, enrollment,
prepare/finish, removal, callback traversal, WOKEN handshake, locked interruptible
iterations and bit-wait policy.
The [core migration record](experiments/completion/README.md) owns storage,
locking/lifetime contracts, test inventory and remaining C boundaries. Selection
remains default-off and builtin-only; known incompatible counter-access drivers
are excluded.

The declared x86_64 server selects the verified Rust core. At `5234e2809e9b`,
it and the derived C-core comparison each pass six ext4, four poll/epoll and two
blocking eventfd/timerfd read cases on q35/KVM SMP2. Resolved configs differ only
by core selection; fixtures, container and VM parameters match. Both complete
without compiler/objtool diagnostics. [Evidence](docs/evidence/wait-locked-server/manifest.json).

Same-build executable contributions for the Rust-core server: C **5,747,110
bytes**, Rust **152,114**, assembly **45,104**, generated **28**, linker/padding
**2,107,085**, unknown **0**; total **8,051,441**. Its C-core comparison contains
C **5,753,409** and Rust **145,083**, total **8,050,673**, also zero unknown bytes.
C decreases by 6,299 bytes and Rust increases by 7,031. This includes inherited
Rust support; linked bytes are not a completion percentage. Networking is
configured but not runtime-tested here; ext4 runs on BRD, not virtio block.
[Local commands](ci/README.md) reproduce the target and derived comparison;
hosted execution stays disabled.

The two locked interruptible iterations now pass four dedicated-worker cases
and the blocking userspace consumers above. A process-context watchdog preserves
the ordinary-lock IRQ contract; sampled blocked-state evidence does not prove
all wake races. [Migration contract](experiments/wait-locked/README.md).

[ADR 0003](docs/adr/0003.md)'s selected BRD correction is verified at
`ff6ac4a5d732`: nonpositive max_part becomes 1 and values above 256 clamp before
rounding. The separately selected generated patched-C oracle and Rust BRD each
pass 29 boots: 26 parameter variants, block, ext4/consumer integration and
partitions. Identical fixtures exercise preallocated and on-demand disks,
geometry and I/O. The same source passes 70 combined KUnit cases (nine BRD +
61 core), then 61 isolated core cases. [Evidence](docs/evidence/brd-parameter-fix/manifest.json).
The imported patch is an upstream proposal; acceptance/merge is unverified.
Pristine Linux C and historical evidence remain intact. Parameter storage and
metadata remain C-owned, and the lock adapters still execute C in this checkpoint.

Next transfer bit-wait table ownership and BRD parameter metadata into Rust as
separate changes; their development branches have no verified runtime result yet.
The [bit-wait record](experiments/wait-bit/README.md) and
[generic wait record](experiments/wait/README.md) own their contracts.
Standalone untimed bit_wait/io scheduling, stop/park, repeated latch races,
socket/futex consumer integration and POLLFREE races remain unverified.
Forced diagnostic failures, detached-batch races, untimed signal paths, deadline
races and broader IRQ coverage remain open. arm64, modules, expanded fault stress
and performance budgets remain Phase 1b. Phase 1a still needs parameter adapters
removed and review gates completed; [BRD.md](docs/BRD.md).

Failures are retained, including the [bit-wait FFI type mismatch](docs/evidence/wait-bit/manifest.json),
the [wake pointer-conversion compile error](docs/evidence/wait-wake/manifest.json),
the [plain-profile configuration refusal](docs/evidence/swait-init/manifest.json)
(EXPERT forces DEBUG_KERNEL; corrected before compilation), [wait bringup](docs/evidence/completion-wait-initial/manifest.json),
[status test compilation](docs/evidence/completion-status/manifest.json),
[q35 bringup](docs/evidence/q35-bringup/manifest.json) and the initial
[swait/ext4 fixture staging refusal](docs/evidence/swait-ext4/manifest.json).
Raw logs/binaries remain in `linux-out/<run>`; manifests record source/config/tool
identities and hashes. [Verification index](docs/VERIFICATION.md) preserves earlier
milestones without attributing their results to newer source.

Bit/variable wait-table ownership and six new tests are implemented and reviewed
on `rusix/wait-bit-owner`; ten host gate suites pass.
The [ownership contract](experiments/wait-owner/README.md) records the intended
storage and ordering boundaries. Kernel builds and runtime results remain pending.
