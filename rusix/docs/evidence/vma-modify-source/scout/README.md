# Next MM policy migration scout

Recommendation: migrate the complete VMA range-modification and splitting transaction,
including its shared prepare/complete protocol, after the current teardown/copy-VMA
gates. This removes real mmap topology and resource-management policy, not just leaf
accessors. It does not claim the whole merge engine or memory manager is Rust.

Inspected source: `99fd3dd96ac0b6131c34501dff9626e95b063037`; behavioral baseline:
`2926d88bb7fc4608fd942453d929c39e4e5ec006`. `source-review.json` binds 22 source/test
files, the resolved config, and all 11 proposed function bodies. Each proposed body
is byte-identical to the baseline (320 body lines total). Current vma.c differs
only in the previously proposed copy/link and remove-vma selection wrappers.
No source changes, build, configuration resolution, or test execution occurred here.

## Complete first implementation unit

Translate `__split_vma`, `split_vma`, private `vma_modify`, and the four public
`vma_modify_flags/name/policy/flags_uffd` entry points. Include
`init_multi_vma_prep`, `init_vma_prep`, `vma_prepare`, and `vma_complete` so the
publication/locking/removal transaction is not hidden in a new C policy helper.
The latter protocol is also called by existing C `commit_merge` and `vma_shrink`;
those callers must select the same Rust protocol. Preserve their native stack
storage through thin wrappers, with explicit C lifetime boundaries.

Do not postpone all eleven bodies behind a new general abstraction framework.
First implement/review the entire translation; local commits can separate source,
proof tooling, and fixtures without claiming helper commits as milestone completion.
Then migrate the whole merge decision engine (`vma_merge_existing_range`, `vma_merge_new_range`,
`vma_merge_copied_range`, `vma_merge_extend`, `commit_merge`, expansion/shrink and compatibility
rules) as the following coherent unit, followed by munmap gather/abort/commit.
Full `mmap_region` comes after these reusable topology transactions. Page ownership,
allocator, faults and scheduler remain required by ADR 0002.

## Contracts that cannot change

- Callers hold mmap write exclusion. mprotect acquires it before fixup; madvise
  explicitly documents it. Keep per-VMA `vma_start_write` on both source and clone,
  file i_mmap write lock and anon-vma write lock ordering, dcache interval-tree
  exclusion, and uprobe notification timing. A native lock operation may block.
- `split_vma` checks `map_count >= sysctl_max_map_count` first and returns ENOMEM.
  `__split_vma` deliberately bypasses this: munmap can exceed the limit temporarily
  while removing mappings. Do not collapse the two entry points.
- Split `may_split` callback runs before duplication and returns its exact error.
  Acquire clone, iterator preallocation, policy, anon chains and file ref in the
  original order, then invoke open. Roll back only acquired resources in the native
  order. A cloned VMA can fail even before publication; lifecycle/PFN ref handling
  must remain balanced. Do not replace exact errno with a generic Rust error.
- `new_below` changes which object owns each half, pgoff adjustment and final
  iterator rewind. The iterator must finish pointing to the original VMA. Preserve
  unsigned C-width arithmetic and map_count increment/decrement behavior.
- Prepare inserts a new file VMA before changing the old address range, while
  holding the mapping lock. Complete publishes the new maple entry/map_count before
  releasing anon/file locks. Reordering these operations exposes incomplete ranges.
- Complete's merge-removal branch is not `remove_vma`: it marks detached, drops
  file/anon/policy state and frees, potentially twice, without invoking vm_ops.close.
  Never reuse teardown's close transaction for it. Preserve remove2 sequencing,
  warning conditions and post-unlock uprobe calls.
- `vma_modify` tries merge first; merge OOM differs from ordinary no-merge.
  The first split can succeed and the second fail: retain this partial topology
  change, rather than invent transactional rollback. The function prepares topology;
  callers still apply protection, policy/name/uffd state and page-table changes.
- Merge can free/rebind the original VMA. Do not dereference cached source after a
  successful merge; return the selected VMA. Only successful flags merge writes
  sticky flags back to the caller. Never assume vma_merge_struct fields survive
  merge unchanged: its declaration explicitly permits mutation.
- Open/may_split and other foreign callbacks are genuine reentrancy boundaries.
  Use raw pointers or short field accesses, never a long-lived whole-VMA Rust
  reference spanning callbacks/locks/native observers. Preserve native access order.

## Temporary C boundary and removal plan

Use existing copy-VMA primitives where their contracts match, while maintaining
separate feature/dependency guards. Keep `vma_iterator`, `vma_prepare` and
`vma_merge_struct` canonical C storage at stable final addresses; native constructors
and typed field operations provide layout access. Rust owns branch decisions,
resource stages, ordered calls, error propagation and cleanup. Avoid Rust copies
of C bitfields or passing config-dependent `vm_userfaultfd_ctx` aggregates by value;
its C wrapper can initialize canonical context then pass an opaque pointer.

C can retain one-operation wrappers for maple allocation/store/rewind, anon interval
updates, file/policy refs, native locks, callbacks, diagnostics and huge-page hooks.
`vma_merge_existing_range` is an explicit temporary C transaction dependency, not
an adapter claimed to be finished Rust. Preserve generic function signatures for
remaining C callers; no broad layout/ABI promise follows after complete migration.

Once merge, split and munmap callers are Rust, remove redundant native context
wrappers/accessors and let Rust own private state. Maple/rmap/file/locking services
remain counted C until translated. Do not declare subsystem divergence or hide
these executed services from the inventory.

## Target and test plan

The current resolved copy-VMA profile disables NUMA, USERFAULTFD, ANON_VMA_NAME,
THP, hugetlb and KSM. Thus policy/name/uffd wrapper translation can preserve the
source contract without pretending these paths ran. New config expansion needs
its own declared coverage; do not silently switch these on to manufacture tests.

Retain the exact baseline `tools/testing/vma` 16-case C reference harness. It
already includes simple_modify, merge variants, callback-close restrictions,
preallocation failure and copy_vma. Its dummy anon-vma/fault controls are useful
for reference semantics but do not execute the Rust kernel or prove real lifetime.

Use unchanged baseline `tools/testing/selftests/mm/merge.c` first: its initial
five mprotect cases exercise left/right/both and faulted/unfaulted split/merge
with PROCMAP_QUERY topology assertions. A precisely enumerated kselftest filter
can run these five without silently counting unrelated skipped uprobe/KSM cases.
PROCMAP_QUERY is outside CONFIG_PROC_PAGE_MONITOR in fs/proc/task_mmu.c, so that
existing exclusion alone does not prohibit these assertions. Confirm actual static
fixture compilation and CLI selection before promising exact required names.

Then add paired ordinary consumers for lower/upper/interior splits, private and
shared file pgoff/content after close+unlink, DONTFORK/WIPEONFORK subrange changes,
munmap interior holes and map-count-limit behavior. Keep existing nine lifecycle
and native mremap_dontunmap consumers as regressions. mlock2/mremap tests can cover
locked splits once their exact permissions/fixture assumptions are checked.

Require native callback/ownership fixtures for may_split veto, open exactly once,
file/policy/PFN refs, clone/preallocation/anon-clone failures, and successful first
split followed by failing second split. Attribute real failure sites; a synthetic
host model does not certify kernel cleanup. Add both insert and one/two-remove
protocol paths because C merge callers now invoke Rust prepare/complete. Track
unavailable configuration paths as unexecuted rather than passed.

Proof gate: preserve original C bodies byte-for-byte under selection; preprocess
actual mm/vma.c; prove all eleven policies select Rust or native C exclusively in
object/archive/linked artifacts; verify actual C callers target the Rust protocol.
Context constructor wrappers are allowed, but no native policy body should remain
executing in the selected slice. Reuse same pinned toolchain/fixtures, compare only
the new selector and check exact diagnostics/console/results. All implementation
and runtime acceptance is future work; current scout is only a dependency decision.
