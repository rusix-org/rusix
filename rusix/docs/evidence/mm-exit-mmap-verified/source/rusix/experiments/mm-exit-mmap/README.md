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

## Native teardown fixture (source reviewed, not executed)

`CONFIG_RUSIX_EXIT_MMAP_TEST` builds the same private-worker fixture for either
teardown implementation. Suite `rusix_exit_mmap` has three exact cases:

- `empty_final_users_retains_storage`: native `mm_alloc` plus `mmgrab`, final
  `mmput`, then zero users, empty tree and retained PGD/RSS storage. This MM was
  never adopted; its remaining count must be exactly one.
- `mapped_final_users_closes_before_file_put`: native private inode/file and
  `vm_mmap` construction; final users invoke close while both file references
  still exist, then drop the mapping reference. Final private `__fput_sync`
  invokes release after close. No freed descriptor is inspected.
- `fixed_replace_close_dummy_reset`: real `MAP_FIXED` replacement invokes the
  early close path and later descriptor removal. Close installs poison hooks;
  the native dummy reset must prevent a second callback. Ordinary `vm_munmap`
  alone does not exercise that early-close path.

Mapped modes record a positive remaining MM count, not exactly one:
`kthread_unuse_mm` and native scheduling may retain or lend lazy-TLB references.
Only the explicit observer `mmgrab` is dropped; no manual lazy-reference repair
or final storage-exhaustion claim is made. Tree emptiness is checked after exit,
not `map_count == 0`, which the baseline does not guarantee.

The controller waits at most ten seconds and releases its RAII reference before
KUnit assertions. Worker ownership covers completion-to-return; acknowledgement
is not a join. Timeout or uncertain cleanup retains fixture, MM/file and task
references required by possible callbacks. File callbacks use only private test
objects; no global fault knobs or production instrumentation are added.

Source review, formatting and seven strict inventory host regressions pass.
Required inventories are isolated three and combined 79 (nine BRD, 67 core,
three teardown); these are future runtime requirements, not passing kernel
results. Paired profiles, compilation and execution remain pending. Leading
XA_ZERO_ENTRY and committed-prefix allocation failures still need attributable
native failure tests; no artificial sentinel state is counted as coverage.
