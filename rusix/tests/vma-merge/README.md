# Bounded merge userspace consumers

These are guest-only Rust programs. Never execute either binary on the host or in
a container. Source and 13 pure host parser tests are ready for peer review;
compilation and C/Rust kernel execution have not run. No production code or
runtime routing changes accompany this fixture.

PID 1 requires the exact single token `rusix.vma_merge_probe=1`, mounts proc,
sets its name to `rusix-mrg-init`, clears the probe environment and starts `/probe`
in a fresh process group. The probe also checks that exact token, its direct
PID-1 parent, `/proc/1/comm` and 4096-byte pages. The architecture is x86-64 only.
The supervisor retains the unreaped group leader while killing remaining group
members, bounds orphan reaping, then powers down the disposable VM. Its 60-second
probe deadline and an external bounded VM remain containment for broken syscalls.

## Two literal cases

1. `concurrent_mprotect_procmap`: fourteen mapped pages enclose a twelve-page
   payload between two inaccessible guard pages. Every byte is initialized before
   the mapping enters an Arc. A writer changes only the center four pages'
   permissions, never payload bytes. Two initial handshakes prove read-only and
   read/write query controls while the writer waits for acknowledgment. Both
   workers then run 256 iterations: the writer makes R/RW transitions, while the
   reader checks every payload byte and performs one covering `PROCMAP_QUERY`.
   Each query is self-consistent; no cross-query snapshot or `/proc/maps` text
   consistency is assumed. Returned bounds must match that query's reported
   permissions. Both threads must return, fully join, and relinquish their Arcs
   before the exact original guarded interval is unmapped. Successful counters
   are 514 permission changes, 258 queries and 258 scans (including controls).
2. `fork_cow_mremap_lifetime`: only after those threads have joined, a private
   two-page payload with separate guards and another disjoint two-page remap
   allocation are initialized. A raw-syscall child changes its own protections and
   private COW bytes, acknowledges readiness, and waits while the parent performs
   64 grow-to-three/shrink-to-two cycles. Parent checks the preserved prefix,
   every zero-extension byte and its unchanged private COW payload each cycle.
   The child verifies its private changed bytes before raw exit. Parent waits for
   the exact owned child and requires status zero. A successful `mremap` updates
   the sole owning pointer/length immediately; cleanup never unmaps an old hole.
   Retained guards are unmapped only by their original owner. The child count is
   one, with 64 successful grows, shrinks and checked zero extensions.

The second case permits actual relocation but does not require it; the first's
free-running phase permits scheduler interleavings without claiming every query
races an in-progress change. These consumers supplement native upstream merge
filters and kernel fixtures. They do not establish exhaustive concurrency,
allocation rollback, every merge branch or complete MM compatibility.

## Unsafe and lifetime boundaries

`ProcmapQuery` is the public `include/uapi/linux/fs.h` ABI: 104 bytes, `#[repr(C)]`,
`_IOWR('f',17,104)` (`0xc0686611`), with no optional pointer buffers. Compile-time
size/offset assertions and `upstream.json` bind it to the pinned native UAPI. This
is not a reconstructed private kernel layout. A missing ioctl is failure, not skip.

The shared mapping's unsafe Send/Sync implementation requires immutable payload,
read access in every permission phase and Arc-held ownership through callback
return. No Rust slice or reference into mapped payload is formed. The channel
carries actual successful operation counts. Worker deadlines/cancellation and
bounded join observation prevent starting fork after an unfinished thread; a
failed join leaves worker Arcs owning storage until process shutdown.

Post-fork child code uses inline x86-64 syscalls and raw byte reads/writes only:
no allocation, I/O formatting, libc/TLS errno, locking or Rust destructors. Its
private mm makes its COW writes independent of the parent's reads. Nonblocking
pipes and raw monotonic clock checks bound the handshake. Parent alone consumes
wait status; PID remains live or an unreaped zombie until successful wait, and
cleanup clears PID ownership before any further kill after a consuming wait (or
unexpected ECHILD). Timeout cleanup kills the owned child and polls boundedly;
PID 1 and VM timeout contain an unresponsive kernel child.

The strict gate requires both exact case names, exact completed counters and the
PID-1 envelope. Missing, duplicate, reordered, skipped, foreign or failed results,
extra test output and kernel diagnostics fail. Host parser tests execute no guest
code. Future compilation must use the pinned image, retain source/tool/command
identities, inspect static ELF, chmod binaries 0644 and never execute them there.
