# Address-space construction transaction

Status: paired x86_64 kernels passed five ordinary userspace cases at
`00c4ef1c190349a671a2a72ce4736c6bfb58210e`. Allocation-failure and wider integration
coverage remain pending. [Evidence](../../docs/evidence/mm-construction/manifest.json). Reference:
Linux 6.18.58 `kernel/fork.c:mm_alloc/mm_init` at
`2926d88bb7fc4608fd942453d929c39e4e5ec006`. No subsystem divergence is declared.
The default-off `RUSIX_MM_CONSTRUCTION_RUST` selects the complete Rust allocation,
initialization and staged rollback transaction; both original C bodies remain
oracles. `mm_alloc` retains its original `EXPORT_SYMBOL_IF_KUNIT` site exactly
once. Private `rusix_mm_init` is called through the original C shim by dup_mm.

## Two input states and ownership

mm_alloc acquires mm_cachep storage and zeroes exactly sizeof(mm_struct). dup_mm
instead copies that fixed prefix from oldmm and passes the copied user_ns pointer.
The shared initializer must not zero the latter input or mistake copied resource
pointers for new ownership. Neither path constructs a safe Rust Mm reference.

mm_cache_init creates a variable-sized slab allocation: fixed prefix plus CPU
mask and optional CID masks, aligned to ARCH_MIN_MMSTRUCT_ALIGN. Initializers
work at the final address. x86 poking_init calls mm_alloc after mm_core_init and
maple-tree initialization but before sched_init and IRQ enablement; the Rust path
adds no heap allocation, might_sleep check, module-init requirement or panic.

Successful PGD construction links ptdesc->pt_mm into the global pgd_list under
pgd_lock. Successful RSS initialization registers embedded counters under the
CPU-hotplug counter lock. These C observers exist before mm_init returns, so
construction is not exclusive whole-mm ownership. Raw pointer stages describe
cleanup responsibility; C primitives preserve actual field access semantics.

## Sequence and rollback

Rust preserves maple initialization and external lock association; users/count
references; seqcount and mmap lock; mmlist selflink; page-table accounting;
map/locked/pinned/RSS state; page-table and argument locks; CPU mask; AIO, owner,
PASID, executable pointer, notifiers, TLB state, huge-PMD, uprobes and hugetlb
initialization. It then clears flags, branches on current->mm (not p->mm), and
implements the MDWE no-inherit/legacy flag masking before default VMA flags.
Canonical readonly C constants supply bitmap masks, never guessed numbers.

Six acquisition steps follow. Every error becomes NULL, with these exact unwind
operations before the slab is released:

| Failed step | Cleanup |
| --- | --- |
| Futex initialization | Slab only |
| PGD allocation | Futex, slab |
| MM ID allocation | PGD, futex, slab |
| Architecture context | MM ID, PGD, futex, slab |
| MM CID allocation | Context, MM ID, PGD, futex, slab |
| RSS counter allocation | CID, context, MM ID, PGD, futex, slab |

Failed PGD allocation unwinds internally; its copied/transient mm->pgd must not
be freed again. Failed counter initialization owns no counters and needs no
counter destructor. No stage invokes mmput/mmdrop, and no failing path releases
a user_ns reference: get_user_ns occurs only after every acquisition succeeds,
followed by LRU initialization. Later dup_mmap, task publication, exec commit and
normal mmput/mmdrop remain C and require the completed lifetime contract.

## C boundaries and scope

`mm_construction_impl.h` is included inside fork.c to retain private slab/PGD/ID
access. Small typed primitives preserve canonical lock/refcount/bitmap/layout,
architecture and subsystem operations. mmap_init_lock remains at its existing
C site; other initializer expressions retain their argument spelling and one
per-site static lockdep key, including the RSS counter family. New wrapper
frames change diagnostic instruction addresses; no numerical caller-PC identity
is claimed. Allocation profiling is excluded. There is no C finish-all helper;
Rust owns policy ordering, inheritance branches and every cleanup decision.

The initial selector requires builtin x86_64/MMU/SMP and excludes RT, sanitizers,
allocation profiling, MEMCG, MM_ID, SCHED_MM_CID, LRU_GEN, huge pages, LDT, pkeys
and paravirtualization. These exclusions are absent/disabled in the inspected
resolved server002 configuration. It retains target PER_VMA_LOCK,
FUTEX_PRIVATE_HASH, HOTPLUG_CPU, AIO, PTI and broadcast-TLB support. The optional
canonical primitive branches remain source-visible but unverified. x86 context
initialization and this futex initializer return zero, so their error edges
cannot be claimed covered by ordinary x86 runs.

Remaining work includes Rust slab/PGD/per-CPU resource ownership, architecture
context, lock/atomic/bitmap primitives, namespace references and subsystem hooks,
then dup_mmap and full copy_process/exec/destruction transactions. This slice
reduces executing construction policy; it does not establish Rust mm storage
ownership or complete the memory subsystem.

## Verification and remaining coverage

Actual preprocessing, archive payloads and linked symbols prove selection, with
the original C restored exactly. Both kernels passed anonymous COW, child mapping
lifetime after parent unmap, 32 fork/exec/reap iterations and both MDWE inheritance
cases with matching fixtures. No compiler or objtool diagnostics were reported.
CLONE_VM contrast, explicit private futex consumers and broader ordinary
ext4/server integration still require execution.
Fault cases must attribute actual mm_struct, PGD and RSS per-CPU allocation
failures to built callsites, preserve parent state and succeed on retry. A page
fault sweep need not reach a cached per-CPU allocator; ENOMEM alone is not stage
proof. Optional lifecycle profiles and synthetic error branches require separate
evidence. The five successful consumer cases do not prove allocation-failure paths.
