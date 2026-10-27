# rusix progress

**Rust BRD passes x86_64 block and ordinary-userspace ext4 contracts;
all fourteen completion entry points and all ten swait.c entry points have verified
opt-in Rust implementations; twenty-three generic wait and seventeen bit-wait entries pass parity, with the shared wait table owned by Rust.** Most of the kernel remains C. Linux 6.18.58
(`2926d88bb7fc`) is the behavioral baseline. Hosted CI remains disabled;
verification runs locally. No subsystem divergence point is declared.

Public development lives on `rusix/main`. [ADR 0002](docs/adr/0002.md) owns the
target; [Phase 1](docs/PHASE1.md) owns delivery gates.

Task-fault attempt `003` at `0fd8196feea0` passes the complete local C/Rust
diagnostic matrix and pinned postchecks. Each side records 18 attempts: one
successful uninjected control, one attributable task-slab allocation failure,
one attributable order-2 stack failure, and 15 uninjected sweep controls.
Both failures return ENOMEM; the stack failure matches task allocation/free
identity, and disarmed retries succeed. Actual linked ELF/return PCs, runtime
kallsyms, kernel notes, all 98 captures per side and fixture/tool identities are
bound to the running kernels; configs differ only by the constructor selector.
[Verified evidence](docs/evidence/task-fault-003/manifest.json) retains 970 text
records (22 losslessly compressed), raw binary hashes and exact source snapshots.
This verifies those two constructor failure paths in diagnostic x86_64 profiles,
not general allocation failure or complete task/MM behavior. Earlier
[calibration failure](docs/evidence/task-fault-initial/manifest.json),
[cleanup failure](docs/evidence/task-fault-capture-failure/manifest.json) and
[compile-only checks](docs/evidence/task-fault-harness-fix/manifest.json) remain
separately attributed. The [fixture contract](tests/task-construction-faults/README.md)
records the attribution and cleanup requirements.

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

### Task construction candidate

This separate branch translates the complete private `dup_task_struct` sequence
into Rust: task/stack acquisition, staged rollback, ordered initialization and
handoff to C `copy_process`. The original C body is preserved. Source review,
formatting and 15 host gate scripts (166 cases) pass. The five-case userspace
probe and Rust PID1 compile as static binaries in the pinned container; neither
was executed. Matching C/Rust profiles, actual dispatch/linked selection proof
and the bounded guest runner are ready for kernel verification. No candidate
kernel has been compiled or booted. Attributable allocation-failure tests remain
required. [Contract and remaining C boundaries](experiments/task-construction/README.md).

### Task-construction allocation failures (unverified pipeline)

On `rusix/task-construction-faults`, production policy remains the frozen `8fd3`
constructor. Separate diagnostic configs, guarded static-Rust controller/C raw
fork worker, PID1, actual-ELF calibration generator and bounded VM runner are
implemented. Thirteen synthetic parser regressions and eleven discovery/transport
regressions pass; no fault kernel or guest execution is verified. Diagnostic
routing preserves ordinary task gates. Root and independent source reviews pass;
a combined 46-case host run and exact input hashes are retained in
`linux-out/task-fault-combined-host-001`. Actual compiled-site discovery, event
schema calibration and paired runtime attribution remain pending. Capture
completion alone is not failure-test PASS. The
[fixture contract](tests/task-construction-faults/README.md) distinguishes intended
slab/stack attribution from unobserved parent-stack accesses and broader cleanup.

Pinned fixture compile check at `a2d0eef199fa` retained a failure in
`linux-out/constructor-fixtures-compile-001`: the fault PID1 compiled as static
ELF, then Rust 1.85 rejected the controller with E0282 on its untyped BTreeMap.
Worker and MM fixtures were not reached. The controller now declares
`BTreeMap<String, String>` explicitly; formatting and the 13 trace/11 pipeline
host cases pass. The successful compiler retry is recorded below; the original failed output is
unchanged. This is a fixture type fix, not kernel or runtime evidence.

### Constructor verification tooling update

Pinned static fixture compilation passed for all five binaries: fault init,
controller and worker at `15c7e563fa4b`, and MM init and probe at `0fd31f0fde17`.
`linux-out/constructor-fixtures-compile-002` records compiler commands, static
ELF checks and source identities; the earlier compile failure remains in `001`.
No fixture was executed and this establishes no kernel, VM or fault-calibration
result. The reviewed archive payload/path fix from `0af2d8b944b2` is inherited
here, including real thin/regular archive regression tests; it does not change
constructor policy.

All 52 archive, selection, guest-gate and fault-gate host cases pass.
Logs and exact inputs: `linux-out/constructor-archive-propagation-host-001/linux-task-faults`.

### Task constructor pointer-ABI diagnostic fix

Historical task source `0af2d8b944b2` passes all five C userspace cases and
postchecks. Its Rust build emitted 36 `improper_ctypes` warnings for GNU empty
`sched_statistics` nested in `task_struct`, then was stopped (137); no Rust
guest ran. `linux-out/task-construction-warnings-evidence` retains these results.
This branch inherits the exact reviewed task declaration annotation from
`eec5ae3ecd7b`: a local pointer-only FFI lint exception, with no policy, layout,
configuration or global warning-gate change. These historical results do not
verify this branch's kernel; fresh build and runtime checks remain pending.

### Diagnostic profile and ELF remapping correction

Pinned `allnoconfig` resolution reproduced the missing FTRACE dependency: both
old fragments resolved KPROBE_EVENTS=n. Both corrected fragments retain every
requested setting, including FTRACE, KRETPROBES and ORC unwinding, and differ
only by the task-construction selector. Commands, inputs and four resolved
configs are retained in `linux-out/task-fault-config-001`; this is configuration
evidence, not a diagnostic kernel build.

Calibration now permits only the exact ELF filename heading to follow an
explicit path remap; file format, instruction text and all artifact hashes remain
checked. Wrong, duplicate or moved headings are rejected. All 54 focused archive,
selection, ordinary guest, fault trace and pipeline host cases pass. Diagnostic
postchecks are prepared to use the same pinned LLVM image as the build, avoiding
host LLVM format drift. Paired fault-kernel builds and runtime attribution remain
pending. Separately, historical task source `eec5ae3ecd7b` passed both five-case
ordinary VM runs; that result does not certify these diagnostic configurations.

The calibration corrections at `c59986edf695` scope symbol uniqueness to the
actual constructor/callees, check numeric call targets, and parse instruction
pairs without storing the complete kernel listing. All 32 focused host tests
pass. The complete generator and independent ELF recheck pass against the
retained C kernel with pinned tools under the same 2 GiB limit that killed the
previous parser. [Fix evidence](docs/evidence/task-fault-calibration-fix/manifest.json)
preserves both attempts. This verifies calibration only; a fresh paired fault
matrix remains required. No guest or allocation-failure coverage is claimed.
