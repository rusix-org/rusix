# Partial task construction transaction

Status: paired C/Rust kernels at `eec5ae3ecd7b` pass five ordinary userspace
cases with actual linked-selection proof. [Evidence](../../docs/evidence/task-construction/manifest.json). Reference:
Linux 6.18.58 `kernel/fork.c:dup_task_struct` at
`2926d88bb7fc4608fd942453d929c39e4e5ec006`. No subsystem divergence is declared.

`CONFIG_RUSIX_TASK_CONSTRUCTION_RUST` replaces this complete private transaction:
node selection, task allocation, architecture copy, stack acquisition and
accounting, staged rollback, ordered child initialization, affinity-pointer
selection and handoff. The original C body remains the unselected oracle.
Rust's only entry is `rusix_dup_task_struct`, called by the original private C
entry. It is not exported to modules or exposed as a safe Rust task API.

## Ownership and errors

`copy_process` calls with current and a NUMA node in sleeping process context.
Current remains alive. C access primitives preserve the parent's original
access semantics; no Rust references overlay mutable foreign storage. The task
slab allocation is address-stable and unpublished throughout this transaction.

| Acquired stage | Error cleanup |
| --- | --- |
| Task slab only; architecture copy failed | Free slab only. |
| Architecture copied; new stack allocation failed | Free slab only. Copied stack pointers can still alias the parent. The allocator cleans its own failed acquisitions. |
| New stack acquired and accounted; SCS preparation failed | Unaccount stack, free stack, then free slab in that order. |

All failures return NULL; `copy_process` already selected `-ENOMEM`. Generic
`free_task`, Task/ARef drops or later copy_process unwind paths are invalid for
these early stages. Stack free may defer reclamation through an embedded RCU
head; it encodes the required metadata before task slab release.

The remainder preserves baseline order, including clearing the copied seccomp
filter before later construction cleanup, stack/refcount initialization,
canary, affinity, transient pointers and configured subsystem fields.
`dup_user_cpus_ptr` intentionally remains best effort: its return value is
ignored, it first clears the copied pointer, and its internal parent lock and
allocation rules remain unchanged. There is no failing transaction branch after
SCS succeeds, though best-effort affinity allocation can fail.

The result is still a partially initialized child. x86 architecture copy retains
`arch_task_struct_size` and `memcpy_and_pad`; FPU state is initialized later by
`copy_thread`/`fpu_clone`. Later resource acquisition, failure cleanup,
scheduler initialization and publication remain in C `copy_process`.

## Remaining C and initial configuration

`task_construction_impl.h` is included only by fork.c. It exposes typed primitive
operations for private slab/stack allocators, architecture copy, accounting/SCS,
thread flags, reference counts, affinity access, canonical subsystem initializers
and tightly related scalar/bitfield reset families. There is no C finish-child
policy helper. Rust retains branching and ordering. Canonical C configuration
guards preserve optional fields without inventing layouts or bindgen constants.
These adapters, stack/page/slab ownership, task layout and all later lifecycle
stages remain unfinished C work.

The default-off selector initially requires built-in x86_64,
THREAD_INFO_IN_TASK and non-RT; it excludes VMAP_STACK, SCS, KASAN, KMSAN, KCSAN
and memory allocation profiling. In particular VMAP stack allocation passes
`__builtin_return_address(0)` to `__vmalloc_node`; expanding to it requires a
reviewed caller-provenance design. Ordinary-page stack and slab allocation use
the retained canonical C allocator sites. Diagnostic call stacks include the
new boundary; instruction-address identity is not a compatibility claim.
The SCS rollback translation is preserved but cannot be exercised in this
initial configuration. Architecture copy likewise always succeeds on x86.

Adapter removal requires Rust ownership of allocator/stack resources, thread
flags/refcounts and the corresponding subsystem initialization interfaces. This
transaction deliberately precedes wider copy_process rollback/publication work;
it is not a claim that Rust owns live tasks or the task_struct allocation layout.

## Verified scope and remaining promotion gates

The matched C/Rust pair at `eec5ae3ecd7b` proves exclusive compiled selection and
passes fork/private-state isolation, exec/wait, vfork/exec, affinity and seccomp
consumers. The [guest contract](../../tests/task-construction/README.md) owns the
five literal cases; [progress](../../PROGRESS.md) owns results and failed attempts.
This does not establish complete fork compatibility or live-task/layout ownership.

Before promotion, exercise task/stack allocation failures with attributable
fault injection disarmed before logging, checking parent survival and retry.
Generic ENOMEM does not identify a rollback stage. Ordinary ext4/server
integration, broader clone/thread and failure/concurrency cases remain pending.
Keep synthetic unsupported-branch checks separate from actual x86 execution;
never free an artificial partial child merely because its usage count is one.
