# Locked interruptible wait iterations

At `5234e2809e9b`, C/Rust debug and plain pairs each pass 70 combined cases
(61 core + nine BRD), then 61 isolated core cases. The two Rust iterations bring
the selected generic wait inventory to 23 definitions. Original C bodies remain
for comparison and export records are unchanged. [Core evidence](../../docs/evidence/wait-locked/manifest.json).

The same source passes nine ordinary-userspace/storage boots per implementation,
including six ext4, four poll/epoll and two blocking read cases with identical
fixtures. [Userspace evidence](../../docs/evidence/wait-locked-ext4/manifest.json).
The exact declared server pair passes the same twelve ext4/consumer cases and
refreshes language measurements; only core selection differs.
[Server evidence](../../docs/evidence/wait-locked-server/manifest.json).
No compiler/objtool or rejected runtime diagnostics occur in these pairs.

## Contract

These entry points perform one iteration with the caller's ordinary `spinlock_t`
held on entry and return. They append a self-linked waiter at the queue tail,
set TASK_INTERRUPTIBLE with the full state barrier, then inspect pending signals.
They preserve waiter flags and do not apply priority-prefix insertion.

A pending signal returns -ERESTARTSYS without unlocking, restoring task state or
unlinking. A concurrent signal wake can independently set TASK_RUNNING; tests
must not confuse absence of a state store with an unconditional final-state
value. Without a pending signal, the function unlocks, schedules, reacquires the
same lock and returns zero. The caller owns condition looping and final cleanup.

The ordinary variant uses `spin_unlock`/`spin_lock` without IRQ adjustment. Its
caller must permit sleep after unlocking. The IRQ variant uses
`spin_unlock_irq` to enable IRQs during sleep and `spin_lock_irq` to disable them
again. It does not save/restore an arbitrary entry IRQ state. No acquisition
guard may release the caller-owned lock on return; Rust performs the exact
unlock/schedule/relock sequence, with no unwinding scheduler call.

Queue and waiter are initialized, pinned and retained across the unlocked
interval. Waiter list links must be initialized; private task and callback obey
the existing generic wait protocol. No Rust reference spans sleep. The caller
must not hold another lock or atomic context that prevents scheduling or wakeup.
The original functions are not `__sched`, so no new scheduler-section annotation
is added.

## Caller behavior and remaining C

`wait.h`'s locked wait macro first bypasses iteration when its initial condition
is true. Inside its loop it checks an iteration error before rechecking condition.
After success/error it performs `__remove_wait_queue` (list_del poisoning) and
restores TASK_RUNNING, still holding the lock. Calling `finish_wait` instead
would reacquire that held lock and change the protocol. A signal arriving during
sleep can wake the task; the iteration still returns zero, and a true condition
then succeeds. If false, a later iteration observes the signal error.

The translation reuses marked list operations, full state publication,
signal/current-task helpers, ordinary spinlock helpers and the C scheduler.
Only two new C adapters preserve ordinary-spinlock IRQ macros. Their removal
requires reviewed Rust spinlock/IRQ primitives, including configuration-specific
semantics; raw-spinlock pointer casts are not valid replacements. This slice
neither changes C layouts nor establishes a subsystem divergence point.

Selected real consumers include blocking eventfd reads/full writes and timerfd
reads. Existing nonblocking eventfd/epoll probes do not execute these waits.
GPIO/Chrome EC callers cover the non-IRQ variant outside the declared target;
C macro fixtures are needed for that path. PREEMPT_RT remains unverified.

## Required evidence

Dedicated worker fixtures must cover both variants: actual blocked observation,
condition/payload publication under the queue lock, lock/IRQ ownership on return,
spurious wake/re-enrollment and pending-signal cleanup. Exclusive macro wake
accounting remains open.
State-mutating synthetic cases belong in worker contexts, not the KUnit controller.
Snapshots must precede cleanup so repairs cannot hide incorrect state or links.

Neither production function has a timeout. Failure paths need an independently
owned abort/wakeup mechanism and retained fixture/task lifetime. Acknowledgment
plus Arc lifetime protection is not a task join. A stuck kernel is bounded by the
VM watchdog and remains a failure. The matched runs above verify exact symbol
selection and reject missing, skipped, duplicate or failed cases.

Four new required KUnit cases exercise both variants: pending-signal iterations
including repeated enrollment, original macro condition/error precedence,
observed blocked/spurious wakes with locked payload publication, and blocked
signal cleanup. The required inventory is 61 core cases (70 with BRD).
A per-worker delayed-work watchdog runs in process context; a hardirq timer
must not acquire a lock that the ordinary variant holds with IRQs enabled.
The callback cancels work synchronously after unlocking and before acknowledgment;
its retained Arc covers the remaining return gap. A failed pending-signal setup
exits before either untimed iteration.

Two added guest cases use blocking eventfd and timerfd reads. A separate observer
samples the reader's sleeping state and matching read(fd, *, 8) syscall twice
before the sole producer writes or arms the initially disarmed timer. This is
sampled blocked-syscall evidence, not an atomic snapshot of the whole system.
The observer itself can block in procfs, so controller waits and error cleanup
are bounded; retained descriptor Arcs protect detached failure paths. Threads
are joined only after result acknowledgment and observed thread completion.
Exclusive macro accounting and full eventfd writes remain separate open coverage.
