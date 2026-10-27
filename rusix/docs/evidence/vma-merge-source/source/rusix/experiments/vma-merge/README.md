# VMA merge, expansion and shrink

Dependent source-only translation from `f70b5bc41e8f31e93dd4fb04e4559dced57de0c0`
(Linux 6.18.58 behavior). `CONFIG_RUSIX_VMA_MERGE_RUST` defaults off and depends
on the existing modification/copy/MM chain, inheriting its builtin x86-64
restrictions. The modification prerequisite has not yet passed kernel/VM gates.
This candidate has no configuration, compilation, ELF-selection or runtime result.

Rust owns seventeen complete policies: fork-child and VMA/anon eligibility;
before/after/left/right compatibility; close-hook removal eligibility;
`dup_anon_vma`, `vmg_adjust_set_range`, `commit_merge`; existing/new/copied range
merges; expand, shrink and extend. Six native entry wrappers allocate canonical
stack contexts/preparation storage and dispatch to Rust. All seventeen original
C definitions remain byte-preserved under the disabled selector. Existing Rust
prepare/complete policies are reused directly; commit and expansion are not
whole-policy C callbacks. The four now-unused C prep dispatch wrappers are
excluded only when merge is enabled; MODIFY-only routing remains intact.
Existing modification/copy callers dispatch through the
selected entries; mmap, brk, mremap and exec retain their native caller contracts.

## Ownership and behavior

Mmap write locking, per-VMA write acquisition, iterator position and final-address
context storage are native preconditions. Rust accesses individual native fields;
it creates no descriptor-wide references or layout copies. Successful completion
can retire middle/next. Only surviving target/context is read after commit.
Merge retirement deliberately does not invoke `vm_ops.close`.

Eligibility preserves file/policy/uffd/name, flags, offsets and pairwise anon
ancestry. A close hook prevents deletion and can reduce both-side merge to left.
Maple preallocation precedes prepare/range mutation; after successful preallocation
commit cannot fail. Anon clone owns its partial-failure cleanup; rollback ownership
is recorded only after clone success. Existing-range allocation abort restores the
native cursor and conditional OOM state. Expansion retains its early clone-error
return and later preallocation cleanup. Sticky flags, THP adjustment, publication,
free and khugepaged notifications retain their native order. Arithmetic explicitly
preserves C unsigned wrapping. No rollback improvement or behavior redesign is
included. Native warning conditions are retained through diagnostic primitives;
their diagnostic source location/expression names identify those primitives.

## Remaining C and removal

New native operations are precisely inventoried below; the Rust extern block
binds each by its exact symbol. There are 42 new functions and six native constant
objects, plus 31 reused function interfaces and two reused constants. No new
bindgen type is needed: only existing bound types behind pointers, scalar native
values and a nullable typed close callback cross the boundary.

- Merge-field getters (9): `mm`, `prev`, `target`, `copied_from`, `pgoff`,
  `vm_flags`, `anon_vma`, `file`, `just_expand`.
- Merge-field writes (12): `set_middle`, `set_next`, `set_target`,
  `set_copied_from`, `set_start`, `set_end`, `set_pgoff`,
  `set_adjust_middle_start`, `set_adjust_next_start`, `set_remove_middle`,
  `set_remove_next`, `set_state`.
- Predicates/access (5): `singular`, `policy_equal`, `uffd_equal`, `name_equal`,
  `set_anon`.
- Lock assertions/diagnostics (5): `assert_mm`, `assert_vma`, `warn`,
  `warn_range`, `warn_vmg`.
- Iterator operations (8): `iter_addr`, `iter_next_range`, `iter_prev_range`,
  `iter_set`, `iter_load`, `iter_store`, `iter_clear`, `iter_next_rewind`.
- Subsystem operations (3): `adjust_huge`, `flags_set`, `khugepaged`.

All new names use `rusix_merge_`; constants are `sticky`, `special`, `ignore`,
`nomerge`, `success`, `nomem`. Existing interfaces supply ten merge-field reads,
VMA fields, clone/unlink, range/config/preallocation, VMA write, previous cursor,
validation, prepare/complete and typed close-pointer access. Native maple,
anon/rmap/file/policy/THP/locking/resource operations remain executing C and count
as unfinished work.

Next, after translation acceptance, give Rust private merge/prepared transaction
state and direct Rust-to-Rust calls on both sides. Remove field projections as
mmap/brk/exec and munmap consumers migrate; retire native context storage and its
accessors when no C caller requires it. `vm_area_struct` layout ownership requires
migration of its other direct users. This checkpoint does not freeze any internal
ABI or declare subsystem divergence.

## Verification required

Source restoration must reconstruct all of `mm/vma.c` at the base, not just the
17 function bodies. Rust formatting and native adapter style checks are source
checks only. Configuration and actual compiler preprocessing/object/archive/linked
proof must establish all selected entries and private policy calls; historical
verifier profiles are not aliases for this new selector.

Paired ordinary gates retain existing VMA/copy/modification tests and unchanged
native merge mprotect/fork/mremap filters with exact inventories. Add mmap/brk,
file-offset mismatch and exec-stack consumers. Preserve native
`tools/testing/vma/vma.c` as an additional C oracle, including its preallocation
failure assertions; its stubbed host environment is not kernel parity evidence.
Attributable task-local clone/preallocation failures and close-hook lifetime
fixtures require a concrete, separately reviewed design before implementation.
They must check topology, offsets, cursor/state/errno and ownership balance.
Bounded concurrent protection/query/fault and fork/mremap cohorts need real guest
results. No skipped, extra or duplicate case counts as a pass. NUMA, uffd, anon
names, THP, hugetlb and KSM remain outside inherited runtime configuration coverage.
