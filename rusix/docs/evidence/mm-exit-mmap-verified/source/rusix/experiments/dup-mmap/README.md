# Mapping duplication policy

Source candidate only. `RUSIX_DUP_MMAP_RUST` selects the complete MMU `dup_mmap`
transaction, inheriting the built-in x86_64 MM-copy/construction/release scope.
The original C body remains byte-exact. No build, linked-selection or VM result
is established by source reconstruction or inspection.

The C entry retains its `__latent_entropy` annotation and only initializes
`LIST_HEAD(uf)`, `VMA_ITERATOR(vmi, mm, 0)` and a pointer context at final stack
addresses. It synchronously calls Rust; the context cannot escape. This adds no
heap allocation or failure point. Rust owns parent/child lock order, every loop
branch, per-VMA acquisition stages, publication decisions and failure epilogues.
No whole-MM or whole-VMA references are formed: copied maple entries initially
borrow parent VMAs, and rmap/file/callback observers can see committed children.

Required ordering and cleanup:

- Killable parent lock failure returns EINTR directly. Otherwise flush parent
  caches, duplicate uprobe state, lock the child with the original nested lock
  subclass, copy executable/counters and duplicate the maple tree.
- Maple duplication failure skips iterator cleanup and unstable marking. On
  success clear tree RCU mode and process VMAs with `vma_start_write` first.
- DONTCOPY range removal precedes charge reset; a failure must not uncharge a
  previously committed VMA. Charge/allocation failures normalize to ENOMEM.
  Failed policy duplication frees the detached VMA without a policy put;
  later userfault/anon failures put the acquired policy first. Subsystems retain
  their own internal rollback responsibilities.
- Bulk store deliberately ignores its return: preduplicated tree storage makes
  allocation unnecessary in pinned C. Commit and map_count precede open callback,
  file references/interval-tree linkage and page copying. WIPEONFORK retains the
  preceding successful userfault result and does not copy pages.
- Page-copy failure advances the iterator before inserting XA_ZERO_ENTRY, so
  the newly committed VMA is cleaned by mmput. Other loop failures use the current
  borrowed entry. No remaining entry means no sentinel/OOM_SKIP, but UNSTABLE is
  still set. Successful exhaustion runs the architecture hook, enables tree RCU
  mode and invokes KSM/khugepaged hooks.
- Always unlock child, flush parent TLB, unlock parent, then complete/fail the
  userfault list. The outer dup_mm retains descriptor/mmput and uprobe-lock
  responsibility; this transaction must not free the descriptor itself.

`dup_mmap_impl.h` retains explicit unfinished C: plain field access, canonical
lock/iterator/maple primitives, flags/accounting and individual memory-policy,
userfault, anon-rmap, file, page-table, cache and architecture operations. There
is no C loop or combined failure helper. Rust's detached-allocation helper only
unwinds the stages already acquired. Replacing these subsystem implementations
and ownership rules requires later migration, not hidden changes in this slice.

Next prove actual C/Rust selection and ordinary anonymous/file COW, shared file,
DONTFORK/WIPEONFORK and parent-survival cases. Failure evidence must identify the
actual failing allocation and verify committed-map accounting/frontier cleanup;
a generic ENOMEM is insufficient. Current profile optional subsystem exclusions
must remain explicit, and unsupported configurations need separate evidence.
