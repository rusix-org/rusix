# Independent VMA merge source review

PASS: no concrete source/unsafe translation blocker found in the frozen candidate.
This is source review only. Configuration, kernel compilation, actual emitted
selection and runtime remain unexecuted, including the modification prerequisite.
Exact nine-file identities are in source-check.json.

Independently reconstructed the entire original mm/vma.c byte-for-byte to f70b5bc4,
removing two exact include insertions and evaluating only the 21 new selector
regions (17 native policies plus four selected-wrapper exclusions). Each of the
17 original function texts also matches pinned Linux2926 bytes. The initial
review projector retained inserted blank lines around includes; its correction
removes the whole exact insertion, without modifying candidate source.

Compared all17 Rust policies against their native definitions, including:

- Nontransitive anon ancestry and fork-child exclusion, file/policy/uffd/name,
  VM_SPECIAL and page-offset wrapping, left/right compatibility and close-hook
  eligibility. Two-sided merge correctly degrades when next cannot be removed.
- Existing-range cursor movement, middle/next adjustment, target choice, sticky
  flags, clone order, allocation abort cursor restoration and conditional NOMEM.
- New/copied/extend contexts and just_expand handling, early clone-error return,
  target survival and next retirement, plus shrink's preallocation/clear/range
  update/completion/validation ordering.
- Complete commit remains in Rust: canonical prep initialization, preallocation,
  prepare, THP adjustment, range updates, iterator overwrite and complete. C has
  no hidden commit/expand policy adapter. C clone failure clears anon_vma and
  unlinks its partial chain; Rust records rollback ownership only after success.

Unsafe boundaries use raw opaque contexts and typed scalar/field primitives,
without creating descriptor-wide Rust references or copying layouts. The only
mutable Rust reference is private rollback-pointer storage. Caller-local C merge
and prep objects remain at final addresses, disjoint from live descriptors.
Mmap write locking and per-VMA write acquisition match native sites. Completion
can free middle/next, but successful Rust paths subsequently access only surviving
target/context. Retirement goes through existing Rust prepare/complete and
intentionally omits close. Argument mm reads occur before completion consumes
storage; shrink retains its VMA. No foreign borrow spans allocation/free/callback.

Reviewed mmap/brk, mremap extend/copy, modification and exec relocation expand/
shrink callers, reusable adapters, native anon_vma_clone cleanup and existing
prepare/complete retirement. New C code is42 field/primitive functions and6
constants, alongside31 reused functions/2constants; Rust has17 policies and6
native entries. Four redundant selected C prep dispatch wrappers are correctly
excluded only when MERGE is selected; Rust directly reuses the existing Rust
symbols. MODIFY-only and disabled C bodies remain unchanged. Warning conditions
are preserved through diagnostic primitives; locations/expressions identify the
adapter as documented.

Default-off selector depends on MODIFY,RUST,MMU and inherits builtin x86-64
restrictions. Kbuild selects one Rust object; MAINTAINERS has the project pattern.
No new profile routing is enabled or compilation claim made. Migration inventory
and remaining-C/removal criteria agree with source. Required next gates include
configuration, actual17-body/entry selection, transaction fault/rollback and
merge topology/close/lifetime cases; source review cannot substitute for them.
