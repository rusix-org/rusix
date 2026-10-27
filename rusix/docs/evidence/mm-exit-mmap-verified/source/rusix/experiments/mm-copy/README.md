# Fork MM copy transaction

Source candidate only; no compilation or runtime evidence. This slice translates
complete `dup_mm` and `copy_mm` policy from the pinned `kernel/fork.c`, using the
existing Rust MM constructor and release transactions. The default-off
`RUSIX_MM_COPY_RUST` option inherits their built-in x86_64 target restrictions.
Original C bodies remain byte-exact behind one selection guard.

## Ownership and order

`copy_process` owns the unpublished child task. Counter reset and clearing both
MM pointers precede reading current's MM. A kernel-thread parent returns success
with both pointers null; scheduler lazy-TLB acquisition remains unchanged.
`CLONE_VM` takes one **users** reference with `mmget`, not a storage-only `mmgrab`.
The private-copy path repeats the original `current->mm` read. Only successful
acquisition publishes both child pointers and calls the scheduler CID hook.
Existing downstream `bad_fork_cleanup_mm` owns failure cleanup after that handoff.
All duplication failures still normalize to `-ENOMEM` at `copy_mm`.

A fresh slab receives the fixed-size parent descriptor copy. Those copied
resource pointers are borrowed, not newly owned. Shared `mm_init` resets fields
and acquires resources in stages; on its failure it already frees the slab, so
`dup_mm` performs no second cleanup. On success, `dup_mmap` retains its canonical
partial-map construction and `XA_ZERO_ENTRY` sentinel protocol. Failure clears
the unacquired binfmt pointer and owner before `mmput`; it never individually
frees borrowed parent VMAs.

Uprobe ordering is asymmetric by design: a failed `dup_mmap` retains its read
lock through `mmput`, then unlocks; successful mapping duplication unlocks before
high-water updates and module acquisition. A later module-get failure uses the
same MM cleanup but does not unlock twice. No MM access follows `mmput`, which
may free the descriptor. The child/current lifetime and existing subsystem locks
permit these operations; raw pointers do not grant whole-MM exclusivity.

## Remaining C and required proof

Rust owns branches, operation order, acquisition decisions and rollback.
`mm_copy_impl.h` retains typed plain field access/copy, counter initialization,
canonical reference/uprobes/module/CID operations, and the entire `dup_mmap`
subsystem boundary. Existing constructor/release adapters remain reused. The
read-only CLONE_VM value comes from the canonical C header. The local FFI lint
exception covers only reviewed pointer/scalar declarations, as required for
GNU empty C structures nested in `task_struct`; no by-value aggregate crosses.
These operations are unfinished C, not a subsystem divergence declaration.

Next prove linked bridge/object selection and real C/Rust behavior: ordinary
fork/COW/exec, shared-MM clone publication, kernel-thread null-MM copying, child
counter/reference accounting, downstream fork rollback and attributable partial
mapping failures with parent survival/retry. Host source reconstruction is not
compiled selection or failure-path execution. Migration of VMA duplication and
its maple-tree/page-table ownership is subsequent work with separate contracts.
