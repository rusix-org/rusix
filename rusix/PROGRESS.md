# rusix progress

**Rust BRD passes x86_64 block and ordinary-userspace ext4 contracts;
all fourteen completion entry points and all ten swait.c entry points have verified
opt-in Rust implementations; twenty-three generic wait and seventeen bit-wait entries pass parity, with the shared wait table owned by Rust. All 25 RCU callback-list policy definitions
now pass paired KUnit and userspace/server integration checks.** Most of the kernel remains C. Linux 6.18.58
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

The declared x86_64 server selects the verified Rust core. The historical
`ae62f42b6f58` C/Rust **core** comparison and its language measurements remain in
[their original evidence](docs/evidence/wait-owner-server/manifest.json).

The latest measured server pair, at `1fdb7a7707ac`, keeps Rust BRD/core on both
sides and changes only RCU-list selection. Both pass six ext4, four poll/epoll and
two blocking eventfd/timerfd cases with matching fixtures, tools and VM parameters.
These explicit verification profiles do not change the declared server default.
[Current server evidence](docs/evidence/rcu-list-server/manifest.json).

| RCU-list selection | Executable C bytes | Executable Rust bytes | Total executable-section bytes |
| --- | ---: | ---: | ---: |
| C | 5,746,223 | 152,872 | 8,051,313 |
| Rust | 5,744,423 | 157,351 | 8,053,937 |

Both same-build inventories have zero unknown bytes. Totals also include assembly,
generated code and linker/padding; this is compilation-unit attribution, not a
rewrite completion percentage. Networking is configured but not runtime-tested;
ext4 runs on BRD, not virtio block. [Local commands](ci/README.md) own execution.

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
new storage boundary and six collision/constructor tests. The verified
[RCU-list checkpoint](experiments/rcu-lists/README.md) advances the core migration.
Sync, per-CPU/batch ownership and task-lifecycle candidates remain separate
unpublished work; their evidence is not part of this checkpoint.
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

### Verified RCU callback-list checkpoint

At `c4e7efcf22b6`, all four C/Rust debug/plain kernels pass 86 combined cases
(nine BRD, 67 core, ten RCU lists), then 67 isolated core and ten isolated list
cases. The ten cases include literal list transitions and real RCU/SRCU consumers.
All 25 policy definitions link exclusively to the selected implementation.
[Debug](docs/evidence/rcu-list-debug/manifest.json),
[plain](docs/evidence/rcu-list-plain/manifest.json).

Fresh integration at `1fdb7a7707ac` passes 32 boots per ext4 profile: 29 parameter
variants, block, partitions and ext4/consumer tests. Both server profiles pass the
12 consumers and language measurement above. Only the RCU selector differs within
each pair; Rust BRD/core remain selected and test fixtures are disabled.
[Ext4](docs/evidence/rcu-list-ext4/manifest.json),
[server](docs/evidence/rcu-list-server/manifest.json).

The continuity proof preserves the original `c4e7efcf22b6` KUnit attribution:
kernel/fixture sources and those KUnit configurations are unchanged by the
reviewed integration-tooling updates. It does not relabel KUnit as a `1fdb` run
or assert identical linked images. The [migration record](experiments/rcu-lists/README.md)
owns remaining C access/order primitives, storage and subsequent ownership work.

The initial `a536e5425997` server C attempt stopped after compilation but before
boot because the ELF ownership gate rejected valid repeated
`__patchable_function_entries` sections. The [failed attempt](docs/evidence/rcu-list-server-initial/manifest.json)
is retained separately; section-index parsing fixed the tooling, and fresh
`1fdb` runs supplied the successful integration evidence. NOCB, actual hotplug
stress, broader ordering stress and performance remain unverified.
