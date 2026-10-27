# Mapping teardown transaction

Source-only, default-off candidate. `CONFIG_RUSIX_EXIT_MMAP_RUST` requires the
Rust VMA lifecycle and inherits its builtin x86_64 target restrictions. No
candidate compilation, linked-selection proof or runtime results exist yet.
The prerequisite VMA candidate is also awaiting its paired runtime gates;
the pristine upstream 16-case C userspace harness is separate evidence.

## Policy and lifetime

Rust owns the complete `exit_mmap` transaction, `remove_vma` and common
`vma_close` policy. The inline close bridge also reaches munmap cleanup and
failed `copy_vma` cleanup; it does not alter non-MMU selection. Original C bodies
in `mm/mmap.c`, `mm/vma.c` and `mm/internal.h` remain byte-preserved under
deselection. No layout change or safe exclusive MM/VMA reference is introduced.

The C `exit_mmap` entry retains final-address stack iterator and uninitialized
TLB-gather storage. Only the nonempty path initializes the gather. Notifier
release precedes read locking; architecture/cache hooks, unmap, read unlock,
OOM_SKIP, write lock, maple RCU clearing, page-table release and gather finish
retain their original order. Both reads of the first VMA's end are preserved.
Empty and leading-sentinel paths skip gather, count assertion and trace.

The Rust loop accounts pages using native unsigned wrapping arithmetic, detaches
and removes each descriptor, then advances using the retained maple iterator.
It never reads a removed descriptor. NULL and XA_ZERO_ENTRY are checked before
field access. The map-count assertion and trace precede tree destruction; write
unlock precedes uncharging. `MMF_UNSTABLE` does not bypass cleanup, and map_count
is not reset.

Close checks nullable ops and callback separately, invokes the exact C callback
ABI, then installs dummy ops only when it called a hook. Callers retain the live
descriptor and callback resources throughout; close may mutate fields but cannot
free the descriptor. File and policy reads occur after close. Ordinary `fput`
semantics remain asynchronous where applicable. Selected `vm_area_free` is the
last descriptor operation. This is not a generic Rust destructor.

## Remaining C and evidence gates

There are 26 teardown primitives, seven close/resource primitives and one
readonly native VM_ACCOUNT constant. Foreign accesses retain their original
plain C semantics and caller exclusion. C still owns maple iteration/storage,
locks, notifier/architecture/cache hooks, TLB gathering, unmap/page-table/rmap
operations, OOM flags, detach, scheduling, BUG/trace, accounting, file and policy
release. The context-only entry and close inline bridge also remain C. Remove
these boundaries with the corresponding Rust storage, memory-model, page-table
and resource-lifetime implementations; this slice does not complete MM.

Before promotion, add exact composable source restoration and actual emitted
selection proofs. The existing dup_mmap whole-file oracle must still reject this
new source until it recognizes only these reviewed guards; do not weaken it.
Preprocessing must bind both new primitive headers and the common inline bridge.
Check callback ABI/CFI and actual calls from merge/copy cleanup, not just symbols.

Run paired ordinary lifecycle consumers plus exec/exit with populated private
and closed/unlinked shared mappings. Retained-MM tests must cover empty and
mapped final-user teardown without assuming map_count becomes zero. Attributable
duplication failures must distinguish leading sentinel and committed-prefix
cleanup. Exact close/file-reference observations and lifetime/concurrency gates
remain required. Returning successfully or passing userspace reads alone proves
neither exact accounting refunds nor all deferred physical reclamation.
