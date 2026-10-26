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

### Address-space construction candidate

This separate branch adds Rust sequencing for complete `mm_alloc` and shared
`mm_init`, including inherited flags and six allocation rollback stages. The
original C bodies and export placement are preserved. Root and independent
source review, literal source reconstruction, formatting and diff checks pass.
The source now includes matching C/Rust MM profiles (Rust task construction
on both), strict source/preprocessor/linked-object selection gates and five
userspace cases covering COW, parent unmap, repeated exec and MDWE inheritance.
Independent fixture review and 40 host gate cases pass; fixture sources are
recorded before compilation and checked again afterward. Local input hashes
and logs are in `linux-out/mm-construction-host-001`. The MM kernel has not been compiled or booted; guest compilation is recorded below. Actual linked selection,
paired VM behavior and attributable allocation failures remain unverified. Early boot and
PGD/per-CPU counter observers prohibit exclusive whole-mm references.
[Ownership contract and remaining C](experiments/mm-construction/README.md).

### Address-space release candidate

This separate branch translates `mmput`, `mmput_async`, their shared final-user
sequence and `__mmdrop` into Rust. The final-user and final-storage stages remain
distinct; asynchronous callers retain workqueue deferral and the original atomic
barriers. Original C bodies reconstruct byte-for-byte. Root and independent
source reviews, formatting and diff checks pass; exact inputs are recorded in
`linux-out/mm-release-source-001`. No release kernel has been compiled or booted.
Paired profiles and source/preprocessor/object/callback selection gates are
implemented. Four real-MM KUnit cases cover nonfinal users, retained storage,
atomic-context asynchronous release and fresh exec-style storage drop. Root
and independent reviews pass; 20 host scripts (203 cases), formatting and shell
checks pass with exact inputs in `linux-out/mm-release-tooling-host-002`.
Required runtime gates are 80 combined, 67 core and four release cases. All
release kernel builds and VM runs remain pending; unsupported callback relocation
forms fail closed until reviewed against actual compiled objects.
[Release contract and remaining C](experiments/mm-release/README.md).

### Constructor verification tooling update

Pinned static fixture compilation passed for all five binaries: fault init,
controller and worker at `15c7e563fa4b`, and MM init and probe at `0fd31f0fde17`.
`linux-out/constructor-fixtures-compile-002` records compiler commands, static
ELF checks and source identities; the earlier compile failure remains in `001`.
No fixture was executed and this establishes no kernel, VM or fault-calibration
result. The reviewed archive payload/path fix from `0af2d8b944b2` is inherited
here, including real thin/regular archive regression tests; it does not change
constructor policy.

The earlier 45/46 host run retained the construction-only gate
rejection of release additions. A separate release gate now reconstructs all
three migrations while preserving the strict historical constructor gate; the
203-case run above passes.
Logs and exact inputs: `linux-out/constructor-archive-propagation-host-001/linux-mm-release`.

### Task constructor pointer-ABI diagnostic fix

Historical task source `0af2d8b944b2` passes all five C userspace cases and
postchecks. Its Rust build emitted 36 `improper_ctypes` warnings for GNU empty
`sched_statistics` nested in `task_struct`, then was stopped (137); no Rust
guest ran. `linux-out/task-construction-warnings-evidence` retains these results.
This branch inherits the exact reviewed task declaration annotation from
`eec5ae3ecd7b`: a local pointer-only FFI lint exception, with no policy, layout,
configuration or global warning-gate change. These historical results do not
verify this branch's kernel; fresh build and runtime checks remain pending.

The MM constructor's manual extern block has the same narrowly scoped exception
after review of its typed aggregate pointers and `c_int`/`c_ulong` values, including
four declarations carrying `task_struct` pointers. This is an audited consequence
of the observed task diagnostic, not a claim of MM compilation. MM release's
extern block is unchanged; no blanket suppression was added.

### Fork MM copy candidate

This branch adds default-off Rust `dup_mm`/`copy_mm` sequencing and rollback,
requiring the existing Rust MM construction/release options. Shared-MM users
references, null-MM kernel-thread handling and partial-duplication cleanup retain
the original ordering, including uprobe unlock asymmetry. C mapping duplication
and typed foreign/subsystem operations remain explicit unfinished dependencies.
Original C restoration, formatting and source checks are recorded in
`linux-out/mm-copy-source-001`; no MM-copy kernel has been compiled or booted.
Next establish actual linked selection and paired copy/share/failure coverage.
[Ownership and remaining C](experiments/mm-copy/README.md).

MM-copy preprocessing and object/linked proof tooling is implemented, including
archive payload hashes and callback section metadata, but has not inspected a
compiled MM-copy kernel. Twelve copy-selection and eight historical release
gate tests pass; the historical release checker still rejects the additional
copy insertion. Shared-MM guest fixtures and independent source review are complete; compilation
and VM execution remain pending.
Separately, source `00c4ef1c1903` passed all five C/Rust MM-construction VM cases;
its 307-record evidence archive and 25 raw artifact hashes passed independent
audit. That ancestor result does not verify this MM-copy candidate.

The candidate now includes exact C/Rust build routing and three guarded ordinary
consumers: true CLONE_VM write/exit, CLONE_VM followed by exec detachment, and
private-fork COW. The shared child uses a separate guarded stack and raw syscalls;
parent storage is reclaimed only after reap. Root and independent review cover
the source/proof/fixture contracts. All 22 host scripts (229 cases) pass with
unchanged inputs in `linux-out/mm-copy-host-001`. These checks do not establish
compiled or runtime behavior. The branch also inherits the reviewed release
callback-ELF proof fix and the pinned `mtree_empty` fixture correction.

At source `b5bb24438c365a8279dee6b33095853377c3ba55`, the MM-copy PID1 and
probe compiled as static x86-64 ELFs in the pinned image with no diagnostics.
Root and independent inspection bound source/binary hashes and verified the
shared child's emitted code contains inline syscalls, without libc/helper calls
or TLS accesses. Both binaries remain non-executable files on the host.
[Compile evidence](docs/evidence/mm-copy-fixtures/manifest.json) records this
limited result; neither binary nor the MM-copy kernel has been run.

### Mapping duplication candidate

This branch adds default-off Rust policy for the complete MMU `dup_mmap`
transaction, including lock sequencing, per-VMA resource stages, publication and
partial-map failure markers. A canonical C stack wrapper adds no allocation;
foreign layout and individual subsystem primitives remain explicit unfinished C.
Source restoration and formatting checks are recorded in
`linux-out/mm-dup-mmap-source-001`. No kernel compilation or VM verification has
run for this slice. Next establish compiled selection and paired mapping/failure
coverage. [Contract and remaining C](experiments/dup-mmap/README.md).

Root and independent production review found no policy/ABI/lifetime discrepancy;
removing only the selector wrapper restores the baseline `mm/mmap.c` byte-for-byte.
The strict saved-Clang parser now explicitly supports `mm/mmap` as well as
`kernel/fork`. Four new rejection tests and ten existing parser/selection cases
pass; actual retained pinned compiler records parse correctly, with the fork
argv unchanged (`linux-out/mm-mmap-command-host-001`). No compiler was invoked
by that check. Seven-case mapping fixtures are being prepared separately;
ordinary consumers will not certify partial-allocation rollback.

### Mapping duplication verification pipeline

The candidate now has paired profiles, both fork and mmap preprocessing, actual
archive/object/linked selection proofs, local build routing and seven guarded
userspace consumers. Root and independent source review cover production, proof
and fixture contracts. All 25 host scripts (254 cases) pass with unchanged inputs
in `linux-out/dup-mmap-host-001`. The initramfs supplies a private `/work` mount
point; tests cover DONTFORK, WIPEONFORK through two generations, file mappings and
the existing shared-MM/exec/COW cases. No candidate kernel or guest has run.

The release build at `42318e69e5f2` established a nested GNU empty-type lint
through `mm_struct` pointers. This branch carries its reviewed pointer-only
extern annotation and the same narrowly scoped declaration annotation for the
new mapping policy: aggregate values cross only as raw pointers, while scalars
retain C types. Rust policy and global warning gates are unchanged. Actual clean
compilation remains required, as does attributable partial-allocation rollback.

At `e758dac059466f4db1552913a94be1a94a618546`, both seven-case guest binaries
compiled cleanly as static x86-64 ELFs. Root and independent audits checked
source/binary hashes, non-executable host modes and the shared child's emitted
code (inline syscalls, no helper calls or TLS access). The
[compile evidence](docs/evidence/dup-mmap-fixtures/manifest.json) contains 20 text
records. No guest binary or mapping-duplication candidate kernel was executed.
