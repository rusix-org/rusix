# RCU sync state machine

Status: implementation and five fixtures passed source review; sixteen host
gate scripts pass. Kernel compilation and runtime parity remain unexecuted.
Reference: Linux 6.18.58 `kernel/rcu/sync.c`, retained unchanged. This slice
translates its four external functions, private callback and wait loop. It
follows [callback-list policy](../rcu-lists/README.md); neither slice replaces
the grace-period engine or declares RCU divergence.

## Real consumer and boundary

The declared server links this code through per-CPU read/write semaphores used
by CPU-hotplug locking and VFS superblock writer locks. Existing ext4 mounting
does not establish contested writer, replay, freeze/thaw or hotplug coverage.

The five states are IDLE, ENTER, PASSED, EXIT and REPLAY. First enter publishes
ENTER and waits for a grace period before PASSED; concurrent enters join that
transition. Last exit defers restoring IDLE until a callback. Enter/exit pairs
during an outstanding callback can require REPLAY and another grace period.
Preserve nested counts, state ordering, separate warning sites and callback
requeue behavior without adding saturation or validation.

The first grace period switches readers off their fast path. It does not drain
all active per-CPU semaphore readers: the semaphore separately blocks new
readers and waits for its counters. These are distinct parts of the protocol.

## Address, context and ordering

C owners still embed the temporary `rcu_sync` layout, including its wait queue
and callback head. Dynamic initialization occurs at the final address; static
initializers remain separate C callers. No Rust reference may cover shared or
partially initialized foreign storage.

Enter, exit and destruction preserve their IRQ-disable/enable lock operations;
the callback preserves IRQ-save/restore because it also runs synchronously.
The Rust wait loop must preserve the original uninterruptible wait-event
ordering and condition checks, without keeping a queue lock across scheduling.
Shared state uses the original marked versus plain C access primitives while
the C inline fast-path observer remains. Scheduler, spinlock and grace-period
primitives remain visible executing-C dependencies.

Storage must survive every entrant and queued callback, including a callback
that requeues itself. Destruction requires exclusive lifetime ownership and
may block in the global RCU barrier. Exit returning does not establish that
storage can be freed. A future safe Rust owner needs explicit sleepable shutdown
or a process-context reclaimer; an arbitrary last-reference `Drop` cannot simply
call the barrier.

## Verification and next ownership step

Require paired C/Rust state and real-consumer tests before promotion: first and
nested enter, partial/last exit, outstanding-callback reuse, replay, destruction,
a held reader across CPUs, and per-CPU semaphore writer handoff. Controllers
must have bounded observations; workers, tasks and callback allocations survive
timeouts. Do not invoke a synthetic callback concurrently with a queued head.
The real replay case drains the original callback and its successor before
destruction. A separate synthetic case invokes the captured callback only on a
distinct, never-queued scratch head. Candidate teardown observations precede
independent worker barriers; failure retains storage and is reported before
completion. Controller cleanup precedes assertions because KUnit aborts do not
unwind Rust destructors.

Keep linked-definition selection, exact test inventories and existing storage
gates. Dedicated profiles require 91 combined cases, plus isolated controls for
67 core, ten callback-list and five sync cases. The list-only filter names its
exact suite so the new sync suite cannot accidentally enter that isolated run. Unsupported stress and architecture claims require separate evidence.

Next migrate per-CPU semaphore/rcuwait policy and counter primitives as a coherent
unit, then one real embedded owner. That step must encode reader context, writer
registration, storage lifetime and shutdown before C layouts can become private
Rust internals. Grace-period and per-CPU RCU orchestration remain subsequent work.
