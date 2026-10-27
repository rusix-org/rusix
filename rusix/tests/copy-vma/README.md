# Native copy_vma consumer fixture

The guest runs the unchanged Linux 6.18.58
`tools/testing/selftests/mm/mremap_dontunmap.c`, with its unchanged
`tools/testing/selftests/kselftest.h`. `upstream.json` binds both files to baseline
commit `2926d88bb7fc4608fd942453d929c39e4e5ec006` and exact blob/SHA-256 identities.
Do not copy or modify the native test to make a candidate pass.

The x86-64 static PID 1 mounts proc, requires exactly one
`rusix.copy_vma_probe=1` token (rejecting conflicting values), then directly starts
`/probe` with a cleared environment and a separate process group. A 60-second
watchdog observes its unreaped leader with `waitid(WNOWAIT)`, kills the group before
reaping, and bounds descendant cleanup. The external VM deadline is final
containment for kernel failures. Never execute either binary on the host or in a
container. The guest archive must provide `/proc`, `/dev/console`, `/init` and
`/probe`; no shell is needed for success. Native failure diagnostics try to invoke
`cat` through a shell, which is absent in this minimal archive; failure still
exits nonzero and is rejected.

`gate.py` requires these exact five native TAP names, in order:

1. `mremap_dontunmap_simple`
2. `mremap_dontunmap_simple_shmem`
3. `mremap_dontunmap_simple_fixed`
4. `mremap_dontunmap_partial_mapping`
5. `mremap_dontunmap_partial_mapping_overwrite`

The exact TAP version, `1..5` plan, successful totals and wrapper BEGIN/END/PASS
markers are required. Old-kernel unsupported returns (including the silent shmem
return), skips, missing/duplicate/reordered cases, failure and kernel diagnostics
are rejected. The wrapper's PASS records only child exit and cleanup; acceptance
also requires the host TAP gate and future VM/selection gates.

Thirteen synthetic parser regressions pass. The uncommitted fixture snapshot
compiled cleanly in pinned c02 with 1 CPU/1 GiB, no network, KVM or capabilities.
Both binaries are static x86-64 ELF files without INTERP/NEEDED entries, retained
with mode 0644 and never executed. [Compile-only evidence](../../docs/evidence/copy-vma-fixtures/manifest.json)
binds the exact inputs, native baseline, compiler commands, limits and binary
hashes; its captured README reflects the earlier precompile state. Guest execution
remains pending. These five native success cases do not establish allocation rollback,
self-merge coverage, complete VMA compatibility or Rust selection. Further paired
native-identity/lifetime tests and actual linked-selection proofs remain required.
