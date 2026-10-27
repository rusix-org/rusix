# Partial task construction transaction

Status: kernel source candidate, **not compiled or runtime-verified**. Reference:
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

## Required evidence before promotion

- Prove selected Rust transaction and C primitive objects in the actual linked
  kernel, and absence of the original C transaction body in the selected path.
- Run matched C/Rust kernels with the same SMP and debugging options through
  ordinary fork/clone, exec/wait and vfork, parent/child stack isolation, affinity
  and seccomp consumers. Record exact resolved selector exclusions.
- Exercise task/stack allocation failures with attributable fault injection,
  disarmed before logging; check parent survival and repeated create/reap.
  Generic ENOMEM alone does not prove which rollback stage executed.
- Separate synthetic unsupported-branch checks from actual x86 execution.
  Never free an artificial partially constructed child using free_task merely
  because its usage count happens to be one.

Source and dispatch-tool review, unchanged-oracle comparison, formatting and
15 host gate scripts (166 cases) pass. The Rust PID1 and five-case C probe
compile as static binaries using the pinned ext4 container; neither was run.
The guest contract is in [tests](../../tests/task-construction/README.md).
Paired kernel compilation, runtime gates and attributable allocation failures
remain pending. Local records: `linux-out/task-construction-host-002` and
`linux-out/task-construction-guest-compile-001`; these are not VM evidence.
