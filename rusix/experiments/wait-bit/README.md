# Bit-wait migration

Ten Linux 6.18.58 wait_bit.c definitions are implemented on `rusix/wait-bit`,
pending matched build/runtime verification. They share the experimental
`CONFIG_RUSIX_COMPLETION_RUST` selection: key matching, wake callback, ordinary
and exclusive acquisition loops, three scheduling actions and three out-of-line
wrappers. [Generic wait policy](../wait/README.md) supplies prepare/finish and
callback removal. No subsystem divergence point is declared.

## Contracts

Key identity is the bitmap address and bit number, not the bitmap contents;
timeout does not participate. Variable matching accepts bit number -1 without
bit access. Wake-bit checks identity before touching the matching bitmap, then
calls autoremove only if the bit is clear. It never accesses the entry after that
callback, which can release the waiter's lifetime.

Ordinary waiting prepares at least once, calls its action only for a set bit,
then performs an acquire bit test even after an action error. It finishes once
and returns that error even if the action cleared the bit. Lock waiting finishes
an error path before a fully ordered atomic test-and-set; successful acquisition
returns zero despite the error. A successful caller owns the bit and must release
it. The C bit-operation adapters retain architecture and LKMM behavior over
mixed-access C bitmaps; no Rust atomic reference overlays them.

bit_wait and bit_wait_io preserve scheduling/I/O accounting before checking
signals and return -EINTR. They have no intrinsic timeout. bit_wait_timeout reads
jiffies once, uses modular signed-difference expiry, returns -EAGAIN on existing
expiry before checking signals, otherwise schedules and then checks signals.
Shared Rust arithmetic is used by production and boundary tests; clock-wrap
vectors do not claim a physically wrapping runtime clock.

Self-referential wrapper waiters are initialized inside Opaque at their final
pinned stack address. All semantic fields precede publication; the wait loop
removes membership before storage drops. Timeout addition wraps as unsigned C
arithmetic. All eight original scheduler-text entry points retain their section;
selection gates require one definition in the selected object and linked image.

## Verification and remaining C

Tests are being integrated. Deterministic state-changing fixtures run on dedicated
threads, with Rust literal oracles; they do not modify the KUnit controller's sleep
state. Blocked workers retain Arc-owned fixtures and separate task references.
Owner-release and abort protocols must never clear another worker's acquired bit.
Acknowledgment permits result reads but is not a join; callback ownership lasts
through return. Finite waits and external VM watchdogs bound ordinary execution
and detect broken kernel operations respectively.

Hash table/selection/initialization, wake dispatch, variable-entry construction,
bit-operation/marked-jiffies adapters, scheduler and I/O accounting remain C.
Removing adapters requires reviewed Rust primitives or ownership eliminating
mixed access. Untimed action scheduling, broad signal/deadline races, PREEMPT_RT,
arm64, modules and performance require separate evidence. Existing ext4 calls
these interfaces through buffer/JBD2 paths; source reachability alone does not
prove a workload actually blocked at a particular site.
