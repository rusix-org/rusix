# VMA copy and publication transaction

Source-only, default-off candidate. `CONFIG_RUSIX_COPY_VMA_RUST` requires Rust
mapping teardown and inherits its builtin x86_64 MM restrictions. Compilation,
linked selection and paired runtime evidence remain pending.

Rust owns complete `copy_vma`, `vma_link`, `vma_link_file` and locked
`__vma_link_file` policy. Original C bodies remain byte-preserved in `mm/vma.c`.
C entries construct the native iterator and VMG at their final stack addresses;
Rust borrows opaque context pointers only until return. The VMG retains canonical
initial offset arithmetic and source metadata. No additional allocation or
whole-MM/VMA reference is introduced.

The caller holds mmap write and source VMA locks. Copy preserves overlap rejection,
unfaulted-anonymous pgoff adjustment, uprobe suppression and exact keep-source
neighbor exclusion. Merge may consume the source descriptor: its saved start is
compared with the result before rebinding the source output, and no stale source
fields are read afterward. Rmap-lock output compares offsets with `<=`, including
equality. Address addition retains native unsigned wrapping. Failure leaves
caller outputs unchanged.

Fallback duplication initially borrows copied resources. Policy failure frees
only the descriptor; anon-clone failure releases policy then descriptor (native
clone already unwinds partial chains). Successful clone precedes file acquisition
and optional open. Open can change fields; subsequent link and rollback read
fresh values. Link failure performs hugetlb fixup, common close/dummy reset,
fresh file put, anon unlink, policy put and descriptor free in that order. No
operation accesses a freed descriptor or invents accounting refunds.

Publication preserves prealloc → start-write → attached maple store → file link
→ map-count increment → validation. Preallocation is the only failure. File link
acquires the mapping lock; the locked entry used by `vma_prepare` does not
reacquire it. Shared-writable accounting precedes dcache lock, interval insertion
and dcache unlock. Existing caller lock and file-lifetime contracts remain.

Forty typed C primitives and two readonly native constants retain field/context
accesses, iterator and merge engines, maple publication, policy/anon operations,
file references, mapping/dcache locks, interval trees, hugetlb fixup and diagnostic
macros. Existing teardown accessors/close and selected Rust descriptor lifecycle
are reused. C stack bridges also remain unfinished implementation. Remove these
boundaries with the corresponding Rust iterator/storage, resource and memory-model
work; this is not a subsystem divergence point.

Before promotion, require exact whole-file restoration and actual preprocessing,
archive/relocation/linked selection proofs. Reuse native upstream copy/mremap
cases and ordinary file-lifetime consumers, then add adjacent unfaulted anonymous
merge and DONTUNMAP cases. Native fixtures must observe rebound descriptor/offset
identity, open/close and file references; attributable maple-prealloc and anon
clone failures must validate rollback. NUMA-disabled policy duplication is a
stub, not evidence for its failure path. Existing successful mremap cases do not
prove these failure paths, rmap concurrency or exact reference accounting.
