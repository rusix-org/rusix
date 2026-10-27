# Address-space release transaction

Source implementation only: no candidate kernel compilation or runtime evidence.
`CONFIG_RUSIX_MM_RELEASE_RUST` defaults off and requires the Rust constructor,
therefore inheriting its built-in x86_64/MMU/non-RT exclusions. The original C
bodies and three export sites remain in `kernel/fork.c` for paired comparison.

Rust implements `mmput`, `mmput_async` with its private work callback, the shared
final-user sequence, and `__mmdrop`. Final users trigger address-space cleanup;
final `mm_count` triggers storage destruction. The user transition's implicit
storage reference survives until its last `mmdrop`. No whole-MM reference,
layout ownership, safe destructor or generalized lifetime claim is introduced.

Ordering matches the baseline: khugepaged exits before mappings; executable,
mmlist, binfmt, LRU and private-futex cleanup precede the final storage drop.
Final storage destruction preserves lazy-TLB cleanup, PGD/id/context/notifiers,
checks, namespace/PASID/CID/RSS release, then slab free. The fresh-exec stack-VMA
failure path directly calls `mmdrop` while `mm_users` remains one: only the
final-user sequence asserts zero users, never the final storage destructor.

Atomic/RCU callers may use `mmput_async`; no sleepable cleanup occurs inline.
The work callback owns the final-user transition and may free its own embedded
work storage. Scheduling performs no MM access after `schedule_work` returns.
Existing C `mmdrop_async` and non-RT scheduler drops dispatch to the selected
`__mmdrop`; x86 softirq destruction remains forbidden by the existing callers.

## Executing C boundary

`mm_release_impl.h` supplies typed access/atomic, workqueue, list-lock and
individual subsystem operations. It is included after the constructor header,
reusing its six pgd/id/context/cid/futex/slab release primitives. Rust performs
all transaction order and user-count/list/binfmt branches; no C finish-all helper
exists. The existing inline `mmdrop` remains a primitive, including its full
atomic decrement barrier required by membarrier and final-call dispatch. Shared
fields remain accessed through C; no Rust loads or references race C observers.
Each original WARN_ON_ONCE retains a separate expansion; canonical INIT_WORK
retains its static lockdep key and textual `&mm->async_put_work` name.

These adapters remain unfinished C until their individual subsystem, allocation,
architecture and memory-model contracts migrate. Replacing their synchronization
or changing teardown semantics is separate work, not part of this translation.

## Required evidence

Paired profiles must differ only in release selection with Rust construction on
both. Prove three public definitions, the selected async callback and dispatch,
original C body preservation, object/archive selection and unchanged constructor.
Retain ordinary COW/fork/exec/exit consumers. Add focused final/nonfinal user
references, a retained storage reference after final users, real async cleanup,
and attributable post-construction exec/duplication failure cases. Successful
ordinary exits alone do not establish those branches or absence of leaks.
