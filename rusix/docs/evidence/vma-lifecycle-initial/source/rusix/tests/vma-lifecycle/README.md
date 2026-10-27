# VMA lifecycle consumers — uncompiled draft

Guest-only fixtures; no compilation or VM result is claimed. Never execute
these binaries on the host or in a container. The seven existing
[dup-mmap consumers](../mm-dup-mmap/README.md) are preserved, with independent
guards and markers. Two additional ordinary userspace cases exercise native
VMA splitting and forced movement outside fork.

PID1 requires exactly one `rusix.vma_lifecycle_probe=1` token, sets comm
`rusix-vma-init`, mounts the guest-private `/work` tmpfs, and directly launches
`/probe`. The initramfs must provide `/proc` and `/work`. Probe authorization,
fresh-exec checks, bounded supervision, separate process groups, subreaper
cleanup and retained worker zombies are inherited unchanged. No new libc
library dependency is introduced. The external VM deadline remains containment
for an unresponsive kernel.

Exact ordered inventory:

1. `shared_clone_write_and_exit`
2. `shared_clone_exec_detaches_mm`
3. `private_fork_cow`
4. `dontfork_omits_only_advised_range`
5. `wipeonfork_clears_child_and_grandchild`
6. `private_file_mapping_cow_and_lifetime`
7. `shared_file_mapping_survives_parent_unmap`
8. `mprotect_middle_split_and_restore`
9. `fixed_mremap_preserves_unlinked_file_mapping`

Success requires nine `RUSIX_VMA_LIFECYCLE_CASE <name> PASS` records followed
by exactly `RUSIX_VMA_LIFECYCLE_PASS`. Failures are never skipped.

The protection case reserves five anonymous PROT_NONE pages and populates the
middle three as writable. Changing only the middle active page to read-only
must expose exact `rw-p`, `r--p`, `rw-p` page boundaries in `/proc/self/maps`.
Every byte remains readable and intact; both outer pages remain writable.
Restoring write permission checks native map permissions and writes/reads every
byte again. It does not require merging after restoration and deliberately
avoids a signal/fault or console exception. Pinned `mm/mprotect.c` routes VMA
modification through `mm/vma.c` splitting, where `__split_vma` calls
`vm_area_dup`.

The movement case populates three shared file-backed pages, closes the file and
unlinks its pathname. It reserves a separate five-page PROT_NONE destination
and uses equal-size `MREMAP_MAYMOVE | MREMAP_FIXED` into its middle. This forces
movement rather than in-place growth. The surviving anonymous guards differ
from the writable file VMA and prevent destination merging: pinned
`mm/mremap.c:copy_vma_and_data` calls `mm/vma.c:copy_vma`, whose nonmerge branch
calls `vm_area_dup`. Before any further allocation, `mincore` must report
`ENOMEM` for each old page; the old address is never dereferenced. Exact new
range permissions, both guards, all preserved bytes, and subsequent writes are
checked. Only VMA references retain the backing file across the move. Cleanup
unmaps the whole reservation, including the moved VMA and its guards.

These cases do not establish allocation-failure rollback, RCU retirement,
non-NULL VMA open/close callbacks, userfaultfd, NUMA or huge-page behavior.
They provide native consumer coverage for the selected lifecycle implementation;
actual C/Rust selection proof and paired execution remain required separately.
