# VMA modification, split and mutation protocol

Source translation of Linux 6.18.58 `mm/vma.c`, based on local checkpoint
`99fd3dd96ac0b6131c34501dff9626e95b063037`. The default-off
`CONFIG_RUSIX_VMA_MODIFY_RUST` depends on the existing Rust copy-VMA/MM chain,
RUST and MMU, inheriting the current builtin x86-64 restrictions.

Rust owns eleven complete native policies: `init_multi_vma_prep`,
`init_vma_prep`, `vma_prepare`, `vma_complete`, `__split_vma`, `split_vma`,
`vma_modify`, and the four `vma_modify_{flags,name,policy,flags_uffd}` entries.
The private `vma_modify` decision is Rust `modify`; native wrappers construct
canonical stack contexts and forward arguments. Existing C `commit_merge` and
`vma_shrink` call the same selected Rust prepare/complete protocol. Original C
bodies remain byte-preserved behind eleven selector guards.

This is source-only implementation: no candidate Kconfig resolution, kernel
compilation, actual object ownership or VM parity has run. The whole merge
engine, memory manager and declared target remain unfinished.

## Boundary and ownership

Native entries retain final-address `vma_prepare`, `vma_merge_struct` and iterator
storage; Rust treats them as opaque pointers. No bitfield/layout copies or
long-lived whole-VMA references cross native callbacks, locks or publication.
The pointer-only userfaultfd bridge preserves its config-dependent C aggregate
layout, including the empty structure when disabled. Callers retain mmap write
exclusion and descriptor/resource lifetimes. Per-VMA, mapping, anon-vma and dcache
locking keeps the original nesting and acquisition timing.

Rust preserves these contracts:

- Public split checks map_count first; the private split bypasses that check for
  munmap's temporary over-limit behavior. Boundary warnings retain native macros.
- `may_split` runs before duplication. Clone, maple preallocation, policy clone,
  anon clone, file reference and open occur in native order. Failure releases only
  acquired resources with exact errno; no close callback belongs on pre-open
  cleanup. Native anon-clone failure owns its partial-chain unwind.
- Splitting below/above adjusts the same object and pgoff, then leaves the iterator
  pointing to the original VMA. Unsigned offsets and signed count updates use
  native-width wrapping arithmetic; PAGE_SHIFT and ENOMEM use inherited C constants.
- Prepare links a new file interval before changing the old VMA range. Complete
  publishes the maple entry/count before releasing interval locks. Uprobe
  notifications retain their native positions around those locks.
- Merge removal can consume two descriptors. It updates detached/file/anon/policy
  state and frees without calling `vm_ops.close`; it must not reuse `remove_vma`.
  Rust also owns shared-file removal sequencing in this protocol, while the
  separate native helper remains for other C callers.
- Modification tries merge first, distinguishes merge OOM from no-merge, and does
  not read the original VMA after successful merge. Sticky flags are written back
  only after successful flags merge. If the leading split succeeds and trailing
  split fails, the leading topology change remains, as in Linux.
- The modification entries prepare topology; their callers still apply actual
  protection, name, policy or uffd updates. No semantic redesign is included.

Each unsafe Rust entry documents the precise caller-held storage/locking contract;
its unsafe block describes the native lifetime/publication/cleanup invariants.
Foreign callbacks are fetched as typed nullable function pointers. Later field
reads remain native accesses after callbacks, rather than borrowed snapshots.

## Executing C and adapter removal

Seventy new single-operation accessors/primitives retain canonical context fields,
bitfields, ERR_PTR/IS_ERR, warning macros, callbacks, maple cursor operations,
private anon interval operations, huge-page hooks and native lock/resource calls.
Existing typed copy/link/lifecycle operations are reused. The native
`vma_merge_existing_range` is still an explicit full transaction dependency, not
finished Rust. Maple/anon/rmap/file/policy/uprobe/architecture services remain C
and count as unfinished kernel work.

Next translate the complete merge/expand/shrink decision unit, then munmap
gather/abort/commit. When both sides of these boundaries are Rust, remove redundant
context wrappers and field adapters and give Rust private state ownership. Do not
declare subsystem divergence while executing C remains in the target dependency
closure.

## Required verification

Source checks reconstruct `mm/vma.c` byte-for-byte at the base checkpoint
(SHA-256 `ae07770c413cf47155e342b58a8ad5706ac7e69d190c0732ae208e98cf7f3abc`),
check the helper/entry inventory, and format Rust. These do not prove compilation.
The [source evidence](../../docs/evidence/vma-modify-source/manifest.json) retains
reviewed source identities and check outputs. Initial C declaration formatting
errors were fixed. The existing project MAINTAINERS entry now includes
`mm/vma_modify*`; no human maintainer or sign-off is invented. The generic
new-file reminder, if emitted by checkpatch, is informational.

Required paired gates must prove all eleven policies are selected in actual
preprocessed/object/archive/linked artifacts and C merge/shrink callers dispatch
to Rust. Preserve pinned upstream tests. The first five unchanged `merge.c`
mprotect cases test left/right/both and faulted/unfaulted topology with
PROCMAP_QUERY. The [fixture](../../tests/vma-modify/README.md) binds seven
unchanged native inputs and five explicit harness filters; its Rust PID1 and
strict parser have source review and sixteen synthetic parser cases pass.
The final formatted fixture compiles as static x86-64 ELFs in pinned run `002`;
pre-format compile `001` is retained separately. [Compile evidence](../../docs/evidence/vma-modify-fixtures/manifest.json)
does not execute either binary or certify a kernel. Guest execution remains
pending. Existing lifecycle and mremap consumers remain regressions.

Additional gates must exercise lower/upper/interior splits, file offsets/lifetime,
DONTFORK/WIPEONFORK subranges, map-count admission, native may_split/open callbacks,
insert and one/two-remove paths, attributable clone/preallocation/anon failure,
and first-split-success/second-split-failure behavior. Keep exact diagnostics,
source/config/fixture/tool identities, with only the new selector differing.

Current inherited profiles exclude NUMA, USERFAULTFD, ANON_VMA_NAME, THP, hugetlb
and KSM. Their source paths are preserved but not claimed as executed. Concurrency,
PFN lifetime boundaries, expanded architectures and performance require their own
recorded gates. No host model substitutes for actual kernel lifetime tests.
