# MM sharing and duplication consumers

Guest-only static fixtures. Never execute either binary on the host or in a
container. Static compilation and child-code inspection passed at `b5bb24438c36`;
paired kernel/VM execution is pending.
[Compile evidence](../../docs/evidence/mm-copy-fixtures/manifest.json). The two ordinary profiles retain Rust task construction, MM construction
and MM release; only `CONFIG_RUSIX_MM_COPY_RUST` differs. No KUnit is enabled.

PID1 mounts proc, requires exactly one `rusix.mm_copy_probe=1` cmdline token,
sets its comm to `rusix-copy-init`, and directly runs `/probe`. The probe checks
that token and PID1 name, and requires PID1 as parent except in its explicit
fresh-exec child mode. The exact ordered result inventory is:

1. `shared_clone_write_and_exit`: `clone(CLONE_VM | SIGCHLD)` shares a private
   anonymous mapping. A two-way pipe handshake and release/acquire atomic state
   prove child writes are visible while both processes live and parent writes
   are visible to the child. After child exit and reap, the parent verifies the
   final payload and writes the surviving mapping and child-stack VMA.
2. `shared_clone_exec_detaches_mm`: the same shared-MM handshake precedes child
   `execve`. A freshly initialized global in the new executable verifies a new
   image, while the parent's old shared payload/global and mappings survive.
3. `private_fork_cow`: ordinary fork provides the contrasting private mapping
   path: child modifications and unmap leave all parent bytes unchanged.

The shared clone uses neither `CLONE_VFORK`, `CLONE_THREAD` nor `CLONE_FILES`.
Its separate 64 KiB mmap stack has an inaccessible guard page at each end. The
libc clone trampoline enters a callback that only uses lock-free atomics and
inline x86_64 Linux syscalls; it never calls libc, accesses errno, allocates or
returns through runtime cleanup while TLS storage is shared. Explicit `SYS_exit`
terminates that separate process. The parent never frees stack or argument
storage before reap. Failure to join triggers bounded kill/reap; if the child
cannot be reaped, the worker exits without unmapping shared storage.

Each case has a separate process group. The supervisor is a subreaper and keeps
the worker zombie with `waitid(WNOWAIT)` until group kill/reap, preventing PID
reuse during cleanup. Case supervision is ten seconds, child handshake/join is
bounded, and group cleanup is one second. The outer VM timeout contains a stuck
kernel; no timeout or unsupported behavior counts as a pass.

Success emits exactly three `RUSIX_MM_COPY_CASE <name> PASS` lines followed by
`RUSIX_MM_COPY_PASS`. Failures emit `RUSIX_MM_COPY_FAIL` and exit nonzero.
These ordinary consumers do not establish allocation-failure rollback, partial
`dup_mmap` sentinel cleanup, kernel-thread MM-null behavior or leak freedom.
