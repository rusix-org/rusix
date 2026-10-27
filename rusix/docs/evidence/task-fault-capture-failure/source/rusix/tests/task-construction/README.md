# Task-construction userspace probe

Source-only guest fixture; not compiled or executed. Five literal cases use real
syscalls. No allocation-failure injection, stack-allocation-site evidence or full
fork compatibility is claimed.

The future PID1 init must mount proc, set its comm to `rusix-task-init` with
PR_SET_NAME, and directly spawn `/probe` (no intermediate shell). Kernel cmdline
must contain exactly one `rusix.task_construction_probe=1` token. The probe checks
both before running; normal mode additionally requires getppid()==1. Self-exec
modes retain the same guest checks. These are execution guards, not a security
boundary. Never run the probe on the host.

Compile later in the pinned container as a static x86_64 binary, e.g.
`gcc -std=gnu11 -O2 -Wall -Wextra -Werror -static probe.c -o /out/probe`.
Required kernel interfaces: fork/clone, vfork, execve, waitid/waitpid, procfs,
process groups, affinity, child subreaper, SECCOMP and SECCOMP_FILTER. Missing
support fails; there are no skip/pass substitutions. No host knobs are written.

Exact ordered markers (one each):

- `RUSIX_TASK_CONSTRUCTION_CASE fork_private_and_wait PASS`: child mutates
  private volatile stack/data, exits37; parent observes original values and status.
- `RUSIX_TASK_CONSTRUCTION_CASE exec_fresh_image PASS`: fork/exec of /proc/self/exe
  resets mutated image data; exec child independently validates guard and exits42.
- `RUSIX_TASK_CONSTRUCTION_CASE vfork_exec_handoff PASS`: vfork child only calls
  execve or _exit; CLOEXEC pipe is already closed when parent resumes. Fresh-image
  exit43 distinguishes exec success from the error exit111.
- `RUSIX_TASK_CONSTRUCTION_CASE affinity_inherited PASS`: worker restricts itself
  to one allowed CPU, child observes exact inherited mask; worker restores and
  checks the full original mask before returning.
- `RUSIX_TASK_CONSTRUCTION_CASE seccomp_filter_inherited PASS`: isolated worker
  installs a harmless filter denying only raw getppid with EACCES. Worker and
  fork child check both the denied syscall result and SECCOMP_MODE_FILTER; child
  exits41. Main supervisor/PID1 never acquire this irreversible filter.

Final marker: `RUSIX_TASK_CONSTRUCTION_PASS`, then process exit0. Failures emit
`RUSIX_TASK_CONSTRUCTION_FAIL CASE` where available and exit nonzero; guard exits
125. Worker exit codes carry actual predicates independently of printed markers.
A strict future runner must reject missing/duplicate/out-of-order markers,
failure lines, nonzero exit and kernel diagnostics.

Every case runs in its own worker/process group. Supervisor observes worker exit
using waitid(WNOWAIT), retaining its PID until group cleanup to avoid PID reuse.
Subreaper mode retains orphaned children; failures kill only the owned group and
reap with a finite deadline. Worker and child waits use monotonic deadlines;
poll delays only pace observation and never prove behavior. vfork can block its
worker, so the independent supervisor supplies its timeout. Kernel-stuck tasks
can still outlive SIGKILL: outer VM timeout is final containment. No unbounded
wait is used in the supervisor. Upstream clone3/pidfd suites and dedicated
allocation-failure profiles remain separate future gates.
