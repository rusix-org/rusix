# rusix progress

**Rust BRD passes x86_64 block and ordinary-userspace ext4 contracts;
all fourteen completion entry points and all ten swait.c entry points have verified
opt-in Rust implementations; twenty-three generic wait and seventeen bit-wait entries pass parity, with the shared wait table owned by Rust.** Most of the kernel remains C. Linux 6.18.58
(`2926d88bb7fc`) is the behavioral baseline. Hosted CI remains disabled;
verification runs locally. No subsystem divergence point is declared.

Public development lives on `rusix/main`. [ADR 0002](docs/adr/0002.md) owns the
target; [Phase 1](docs/PHASE1.md) owns delivery gates.

| Check | Verified result |
| --- | --- |
| LTS provenance/math | Signed tag verified; all 24 required math cases pass on q35, zero skips. [Math](docs/evidence/math-q35/manifest.json), [provenance](docs/evidence/lts-baseline/manifest.json). |
| Storage parity | At `9d1c1ca5dd`, C/Rust BRD each pass block6, ext4 userspace6, six parameter variants and partition5. Four identical guest fixtures; configs differ only by BRD selection. [Evidence](docs/evidence/brd-q35/manifest.json). |
| Core and wait-table ownership | At `ae62f42b6f58`, C/Rust debug and plain pairs each pass 76 combined (67 core + nine BRD), then 67 isolated core on q35/KVM SMP2. All 14 completion, 10 swait, 23 generic wait and 17 bit-wait definitions link exclusively. Table placement/alignment and init lifetime are checked. Zero skips or compiler/objtool diagnostics. [Debug](docs/evidence/wait-owner-debug/manifest.json), [plain](docs/evidence/wait-owner-plain/manifest.json). |
| Ordinary-userspace integration | Same source, Rust BRD in both; only core selection differs. Both pass 29 boots: 26 approved parameter variants, block, ext4/consumers and partitions. The ext4 run covers six filesystem, four poll/epoll and two blocking eventfd/timerfd read cases. Identical fixtures; no compiler diagnostics. [Evidence](docs/evidence/wait-owner-ext4/manifest.json). |

Rust implements BRD/store and bio/disk interfaces, conditional xarray insertion,
NOIO scope, completion/swait policy and generic wait initialization, enrollment,
prepare/finish, removal, callback traversal, WOKEN handshake, locked interruptible
iterations, bit-wait policy and the permanent bit/variable wait table.
The [core migration record](experiments/completion/README.md) owns storage,
locking/lifetime contracts, test inventory and remaining C boundaries. Selection
remains default-off and builtin-only; known incompatible counter-access drivers
are excluded.

The declared x86_64 server selects the verified Rust core. At `ae62f42b6f58`,
it and the derived C-core comparison each pass six ext4, four poll/epoll and two
blocking eventfd/timerfd read cases on q35/KVM SMP2. Resolved configs differ only
by core selection; fixtures, container and VM parameters match. Both complete
without compiler/objtool diagnostics. [Evidence](docs/evidence/wait-owner-server/manifest.json).

Same-build executable contributions for the Rust-core server: C **5,746,278
bytes**, Rust **152,850**, assembly **45,104**, generated **28**, linker/padding
**2,107,053**, unknown **0**; total **8,051,313**. Its C-core comparison contains
C **5,753,409** and Rust **145,115**, total **8,050,737**, also zero unknown bytes.
C decreases by 7,131 bytes and Rust increases by 7,735. This includes inherited
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
Pristine Linux C and historical evidence remain intact.

At `a39d03eb165b`, Rust also owns the three BRD parameter scalars, parameter
records, module information and legacy setup metadata. The BRD-specific C
adapter object and lock wrappers are unlinked. Fixed C and Rust each pass
32 boots: 29 parameter variants (including duplicate assignments), block,
ext4/consumer integration and partitions. Exact sysfs names/modes and numeric
getters are checked. The same source passes 76 combined and 67 isolated core
cases, with object and linked-kernel metadata proofs.
[Evidence](docs/evidence/brd-parameter-owner/manifest.json).
A separate SYSFS=n kernel retains debug/core settings, removes parameter-lock
calls from BRD, and passes ownership checks plus the same 76/67 KUnit cases.
[Supplemental evidence](docs/evidence/brd-parameter-owner-nosysfs/manifest.json).
Generic parameter parsers/getters, mutexes and block/page services remain C.

The [wait-table ownership record](experiments/wait-owner/README.md) covers the
new storage boundary and six collision/constructor tests. Next verify the
implemented RCU callback-list and sync policy translations; their development
branches have no kernel/runtime verification yet.
The [bit-wait record](experiments/wait-bit/README.md) and
[generic wait record](experiments/wait/README.md) own their contracts.
Standalone untimed bit_wait/io scheduling, stop/park, repeated latch races,
socket/futex consumer integration and POLLFREE races remain unverified.
Forced diagnostic failures, detached-batch races, untimed signal paths, deadline
races and broader IRQ coverage remain open. arm64, modules, expanded fault stress
and performance budgets remain Phase 1b. The [BRD review](docs/BRD.md) records
the scoped lifecycle and unsafe-boundary disposition; Phase 1a has no declared
subsystem divergence point yet.

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

The first ownership build at `c962147e88f1` was stopped before VM execution on a
test-helper objtool warning. [Evidence](docs/evidence/wait-owner-initial/manifest.json)
retains that failure. KUnit-scoped assertions and checked arithmetic removed the
warning in all eight completed builds at `ae62f42b6f58`. Signal traps now preserve
cancellation failure; a local probe verified exit statuses 0, 7, 143 and 130.

The initial parameter-owner build at `2048c42d9096` failed before VM execution
on a generated field name and three unnecessary-unsafe warnings. The corrected
`a39d03eb165b` builds have no compiler/objtool diagnostics.
[Retained failure](docs/evidence/brd-parameter-owner-initial/manifest.json).

RCU callback-list policy translates all 25 definitions on `rusix/rcu-callback-lists`.
Ten new cases cover literal list transitions and real RCU/SRCU consumers; the
strict gates require 86 combined or ten isolated RCU cases. Fourteen host gate
scripts pass; kernel compilation and C/Rust VM parity remain unexecuted.
The [contract](experiments/rcu-lists/README.md) records shared C access/order
primitives and the subsequent storage-ownership work.

### RCU-list production integration tooling (development)

Added explicit ext4/server C/Rust RCU-list profiles with Rust BRD/core on both
sides and fixtures disabled, production selection checks, guest proof validation,
and exact ancestry/change-boundary verification for retaining older KUnit evidence
under its original source identity. Kernel policy, KUnit fixtures and existing
configuration fragments are unchanged. See the [migration record](experiments/rcu-lists/README.md#production-integration-profiles).
Host regressions and independent source review are the current verification
scope; these new profiles have not been built or booted. Next freeze the reviewed
tooling revision, run serial paired integration guests and refresh the declared
server language inventory before considering promotion.

### Tree RCU callback-batch transaction (development)

On `rusix/rcu-batch`, the default-off Rust implementation now owns extraction,
pinned detached-chain dispatch, budget decisions and reinsertion/accounting.
Callback heads are not accessed after invocation; total counts remain retained
until commit. C keeps per-CPU storage and typed access/IRQ/BH/clock/debug
primitives. The original C production function bodies remain intact; test-only hooks are
separate from the policy.
The [contract](experiments/rcu-batch/CONTRACT.md) owns the boundary and removal path.

Seven cases cover private-descriptor accounting/time boundaries, real retained
callback consumers and a real tasklet count-budget exit. The seventh fixture
uses two DONE callbacks and one PENDING callback, checks partial reinsertion
before pending work, and includes a self-freeing first callback. Paired local
debug/plain profiles require 93 combined, 67 isolated core, ten list and seven
batch cases. The fixture baseline `6f240ef01d`
has 17 passing host scripts plus syntax/diff checks, recorded locally in
`linux-out/rcu-batch-baseline-host-001/manifest.json`. The later production
translation has independent source review and format/diff/input-hash records in
`linux-out/rcu-batch-source-review-001`; it has **not been compiled or booted**.
A fresh run of all 17 host scripts (172 cases), formatting and shell checks also
passes at production snapshot `fdc12796e743`; `linux-out/rcu-batch-host-001/manifest.json`
records its exact inputs. Kernel and runtime gates remain pending.

Next freeze the reviewed implementation, run C before Rust debug/plain pairs,
prove linked selection and exercise ordinary filesystem/server consumers.
The seventh-fixture source has independent review; a fresh host record in
`linux-out/rcu-batch-budget-host-001/manifest.json` covers all 17 scripts,
formatting, shell checks and complete input hashes. Partial-budget runtime
verification, explicit `rcutree.use_softirq=0` callback-thread runs and CPU-hotplug
coverage remain pending; neither mode is silently excluded from
production policy. No full RCU ownership or subsystem divergence is declared.

The initial batch matrix at `0dd58fb714be` passed all 93 combined, 67 core,
ten list and seven batch cases on the C debug kernel. Rust debug compilation
then failed on ten calls to eight list APIs absent from the public bindgen
header; no Rust guest or plain pair ran. The 174-record failure archive remains
`linux-out/rcu-batch-initial-evidence`. Explicit declarations now match the
private canonical C header without changing policy. Host checks pass; a fresh
paired matrix is required before claiming Rust runtime verification.
