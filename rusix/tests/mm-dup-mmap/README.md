# VMA duplication consumers

Guarded static guest fixtures only. Source implementation is complete; compile
and paired VM verification remain pending. Never execute these binaries on the
host or in a container. Both profiles retain Rust task construction, MM
construction/release and MM copying. Only `CONFIG_RUSIX_DUP_MMAP_RUST` differs;
KUnit is disabled. Partial allocation-failure coverage remains separate.

PID1 checks its identity, mounts proc, requires exactly one
`rusix.mm_dup_mmap_probe=1` cmdline token and sets comm `rusix-dup-init`. Only then
it mounts a 4 MiB tmpfs at `/work` with mode 0700 and nosuid/nodev/noexec flags.
The initramfs runner must provide `/work` as well as `/proc`. PID1 directly runs
`/probe`; normal probe mode requires PID1 as parent. The explicit fresh-exec
child mode still checks token and PID1 comm.

The exact ordered inventory is:

1. `shared_clone_write_and_exit`
2. `shared_clone_exec_detaches_mm`
3. `private_fork_cow`
4. `dontfork_omits_only_advised_range`
5. `wipeonfork_clears_child_and_grandchild`
6. `private_file_mapping_cow_and_lifetime`
7. `shared_file_mapping_survives_parent_unmap`

The first three retain the existing [MM-copy consumers](../mm-copy/README.md),
including the separate guarded clone stack, raw-syscall shared-MM child and
bounded reap before storage reclamation. Their policy is unchanged.

DONTFORK advises only the middle page of a populated three-page anonymous
mapping. The child checks `mincore` returns `-1/ENOMEM` for that hole before any
child allocation, while both neighboring VMAs remain readable. It never
accesses the missing page. The parent verifies all three mappings and bytes.
The pinned `mm/madvise.c` maps this advice to `VM_DONTCOPY`, whose branch in
`dup_mmap` removes the copied range and adjusts child statistics.

WIPEONFORK checks every byte of three populated pages becomes zero in the child.
After the child writes a new pattern, its child must again observe all zeroes.
The intermediate child retains its pattern and the original parent retains its
original bytes. This checks inherited wiping and independent anonymous pages,
not just one initially unpopulated mapping.

The file cases populate a regular tmpfs file, map it, then close the descriptor
and unlink its name before fork. Only VMA references retain the backing file.
Child writes are checked by the parent: private mappings preserve original
parent bytes; shared mappings expose child writes. The parent writes a reply,
unmaps, then sends a pipe token. Only after that token does the child verify its
mapping, write/read every byte again, and unmap. The reply is visible only in
the shared case. These cover file-backed VMA reference/interval-tree and shared
writable-mapping paths; they do not claim a non-NULL `vm_ops->open` callback.

Every case runs in its own process group. The supervisor retains the worker
zombie until group cleanup using `waitid(WNOWAIT)` and acts as a subreaper for
orphaned descendants. Pipe waits, descendant waits and case supervision are
bounded; the external VM timeout remains containment for a stuck kernel.
Failures never count as skips or passes. Success emits exactly seven
`RUSIX_MM_DUP_MMAP_CASE <name> PASS` lines, then `RUSIX_MM_DUP_MMAP_PASS`.

These ordinary consumers do not verify partial maple duplication/sentinel
rollback, security charges, VMA-policy/userfaultfd/anon-vma allocation failures,
fatal-signal interruption, architecture failure, or leak freedom. NUMA,
userfaultfd, KSM and huge-page behavior excluded by the declared profile cannot
be inferred from these results. Required failure attribution remains pending.
