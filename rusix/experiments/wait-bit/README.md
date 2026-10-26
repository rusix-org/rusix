# Bit-wait migration

Ten Linux 6.18.58 wait_bit.c definitions pass matched verification at
`4e487a43f0a9`. C/Rust debug and plain pairs each pass 66 combined cases
(57 core + nine BRD), then 57 isolated core; the same source passes nine storage/
userspace boots per implementation with identical fixtures.
[Core evidence](../../docs/evidence/wait-bit/manifest.json),
[userspace evidence](../../docs/evidence/wait-bit-ext4/manifest.json).
The initial C-profile build failed at Rust test compilation because core and
kernel C-long aliases differed; all final runs use corrected kernel aliases.
The entries share the experimental
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
signals, returning -EINTR for an allowed signal and zero otherwise. They have no
intrinsic timeout. bit_wait_timeout reads
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

Nine required cases cover loop/error/acquisition precedence, key/clear-bit
matching, expired actions, production arithmetic across wrap, blocked bit-clear
payload handoff, two exclusive owners, signal/expiry cleanup and all three stack
wrappers. Plain and lock wrappers use precleared bits with unused null actions;
the timeout wrapper has a real blocked consumer. Deterministic state-changing
fixtures run on dedicated threads with Rust literal oracles. Pure arithmetic
compares the actual shared production module with original C macros. Blocked
workers retain Arc-owned fixtures and separate task references.
Owner-release and abort protocols must never clear another worker's acquired bit.
Acknowledgment permits result reads but is not a join; callback ownership lasts
through return. Acquisition and owner-hold phases each have a finite deadline;
their budgets add. Controller success deadlines prevent natural expiry from
imitating handoff. External VM watchdogs detect broken kernel operations.

Hash table/selection/initialization, wake dispatch, variable-entry construction,
bit-operation/marked-jiffies adapters, scheduler and I/O accounting remain C.
Removing adapters requires reviewed Rust primitives or ownership eliminating
mixed access. Untimed action scheduling, broad signal/deadline races, PREEMPT_RT,
arm64, modules and performance require separate evidence. Existing ext4 calls
these interfaces through buffer/JBD2 paths; source reachability alone does not
prove a workload actually blocked at a particular site.
