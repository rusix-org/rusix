# Bit and variable wait-table ownership

Verified at `ae62f42b6f585fcbcdcff84e0763412609f36ccd`: C/Rust debug and
plain pairs each pass 76 combined cases (67 core + nine BRD), then 67 isolated
core cases. Both ordinary-userspace implementations pass 29 boots each; both
declared server implementations pass twelve userspace cases each.
[Debug evidence](../../docs/evidence/wait-owner-debug/manifest.json),
[plain evidence](../../docs/evidence/wait-owner-plain/manifest.json),
[ext4/storage evidence](../../docs/evidence/wait-owner-ext4/manifest.json),
[server evidence](../../docs/evidence/wait-owner-server/manifest.json).
Final builds and boots have no compiler, objtool or runtime diagnostics.
The reference remains Linux 6.18.58 `kernel/sched/wait_bit.c`; no subsystem
divergence is declared.

Rust owns the permanent 256-head table, its shared lockdep key and boot
initialization, hash lookup, variable-entry construction and bit/variable wake
dispatch. Seven additional named definitions bring this file's selected inventory
to seventeen, with its fifteen existing exports unchanged. Original C bodies
remain available under the comparison selector.

## Ownership and ordering

An aligned, type-only C shell carries the configured array alignment through
bindgen. Rust owns its `Opaque` storage. Only the whole array is cacheline aligned;
head stride remains the C structure size. Raw pointers preserve C-visible layout
without introducing Rust references to concurrently accessed queue state.

The existing single boot call initializes every head before publication, without
allocation or scheduling. The initializer is cold init text; the table, shared
lockdep key and exact queue name survive init memory reclamation. In non-lockdep
configurations the empty key need not have distinct storage. Tests must never
reinitialize these globally shared queues or assume they are empty.

Hashing retains unsigned pointer arithmetic and signed-bit conversion for the
currently selected x86_64 configuration; architecture hash overrides are rejected.
Wake dispatch retains the marked active-list check, synchronous stack key,
TASK_NORMAL and exclusive wake budget one. Callers still supply condition
publication and the original full-barrier protocol. The variable callback does
not read bitmap memory and never accesses an entry after autoremove.

Variable entries are initialized at their final address, including current task,
flags, key, callback and self-links. Existing membership must already be removed;
no initialized self-linked object may be moved. Padding is not a test contract.

## Gates and remaining boundaries

Selection checks prove all seventeen definitions in the selected object and linked
image, retain the eight scheduler sections, and establish table size/alignment,
permanent writable storage and init-text placement. Lockdep key storage checks
apply only when lockdep is configured. Pinned Clang builds do not enable GCC
latent-entropy or stack-depth instrumentation; changed instrumentation requires
another init-attribute audit.

Tests compare hashing with the original C helpers, inspect all heads without
altering unrelated waiters, and exercise constructor semantics and colliding
variable waiters. Six new cases bring the required inventory to 67 core tests
(76 with BRD). Collision observations establish distinct predicates and delivery;
they do not exclude a spurious wake followed by re-enrollment. Direct callback
probes separately test key filtering. Worker deadlines, retained task/fixture
ownership and bounded controller waits contain failures; the VM watchdog remains the last bound on a
stuck kernel. The completed matrix above covers debug/plain C/Rust pairs,
ordinary userspace and the declared server without expanding those race claims.

Raw locks, lockdep, marked-list access, bit atomics, task state/scheduling and
remaining caller structures still execute C. Removing table ownership from C
does not remove those dependencies. arm64, PREEMPT_RT, table redesign and broader
wake-race stress remain separate work.

The first C-comparison build at `c962147e88f1` was stopped on an objtool
warning in a test helper; no VM tests ran. The warning exposed ordinary panic
assertions outside the KUnit macro's scope. KUnit assertions, checked arithmetic
and fallible indexing resolved it in the final builds. The interrupted attempt
remains in the [initial failure archive](../../docs/evidence/wait-owner-initial/manifest.json).
Cancellation also exposed an EXIT-only status trap recording zero while Docker
exited 143; explicit signal traps now preserve failure. A local trap probe
verified statuses 0, 7, 143 and 130.
