# VMA descriptor lifecycle candidate

Source candidate based on `9cf27ef36d1d58cb65bd866d9f046ed2e56b045a` and pinned
Linux 6.18.58 `mm/vma_init.c`. Uncompiled and unverified. The upstream 16-case C
VMA baseline runner is prepared but unrun; preceding MM-copy and dup_mmap paired
runtime verification also remains pending. This is neither a subsystem divergence
nor permission to promote before baseline and paired verification.

`CONFIG_RUSIX_VMA_LIFECYCLE_RUST` defaults off and requires the existing Rust MM
stack, x86_64/MMU, PER_VMA_LOCK and !NUMA/!NUMA_BALANCING. Rust owns the sole
permanent cache pointer, fresh allocation initialization order, selective VMA
copy order, PFN tracking acquisition/failure/release decisions and detached-free
order. All original C bodies remain under the alternate selector, including the
source directly included by `tools/testing/vma/vma.c`.

The C `vma_state_init` entry retains canonical `__init` attributes and boot call
site; its only action dispatches to Rust init-section code. A C cache-constructor
primitive preserves name, native size, freeptr offset, sheaf capacity 32 and
HWCACHE_ALIGN|PANIC|TYPESAFE_BY_RCU|ACCOUNT flags. Rust publishes the resulting
pointer once during boot before allocation; no cache teardown or second pointer
owner exists. Neither a null-cache recovery nor a new fallible init path is added.

SLAB_TYPESAFE_BY_RCU postpones slab-page reclamation, not object reuse. Therefore
Rust never makes a whole-VMA reference, including to newly allocated storage.
Canonical C operations retain the original memset, field accesses, representation
copies and explicit `data_race(memcpy)` of shared linkage. Copied file, policy,
userfault, anon-vma and ops pointers remain borrowed. Callers acquire those
resources and publish the VMA later; descriptor free must not release them.

The non-NULL PFN context path checks canonical REFCOUNT_MAX, acquires its kref,
and stores the pointer. Saturation frees only slab storage before lock/list/name
initialization. Detached free asserts the caller's detach/drain obligation,
releases NUMA/name state, puts and clears PFN tracking, then frees slab storage
with no later access. PFN tracking remains active on x86 even with PAT disabled.
Original generic anon-name handling retains its saturation fallback: allocation
may return NULL without failing descriptor duplication.

There are 36 named typed C primitives plus one readonly refcount constant.
They retain slab construction/allocation/free; field/representation operations;
original exclusive-writer assertions; the original translation unit's
`vma_lock_init` static lockdep key/name; list init; optional name/NUMA operations;
and canonical PFN kref access/destructor. These are executing C, not completed
Rust infrastructure. Remove them as slab, shared-field/lock primitives and
reference-owning resources gain reviewed Rust interfaces. The C init entry may
be removed after exact initialization attributes/placement are proved in Rust.
No new layout or generic Drop API is introduced. Allocator instrumentation sees
adapter call sites; emitted provenance must be recorded rather than represented
as the old instruction addresses.

Required next gates: original C byte preservation; upstream VMA tests; paired
actual preprocessing/object/archive/linked ownership of the three public Rust
entries, init dispatch and sole cache storage; exact init lifetime and lockdep
class checks; real fresh/dup/free fixtures including non-NULL and saturated PFN
contexts without device mappings; optional name-enabled coverage; ordinary
fork/advice/file cases plus mprotect split and mremap consumers; attributable
allocation failures and bounded object-reuse stress. Ordinary success alone
cannot prove PFN rollback, reference balance, RCU/ABA correctness or leak freedom.
