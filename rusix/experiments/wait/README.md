# Generic wait-queue policy

Rust now implements eighteen Linux 6.18.58 wait.c entry points: seven wake
wrappers, initialization, four add variants, removal, three prepare functions,
finish and automatic wake removal. Selection remains experimental/default-off under `CONFIG_RUSIX_COMPLETION_RUST`. At `ca91adc60e13`,
C/Rust debug and plain kernels each pass 53 combined cases (44 core + nine BRD),
then 44 isolated core cases. [Core evidence](../../docs/evidence/wait-lifecycle/manifest.json).
The same source passes nine ordinary-userspace/storage boots per implementation,
including six ext4 and four poll-consumer cases with identical guest fixtures.
[Userspace evidence](../../docs/evidence/wait-lifecycle-ext4/manifest.json).
There are no compiler/objtool or rejected runtime diagnostics in these pairs.
The earlier [wake evidence](../../docs/evidence/wait-wake/manifest.json) retains
its resolved pointer-conversion compile failure. No divergence point is declared.

## Contract and ownership

Traverse in the original list order. Cache successor, flags and callback before
invocation; callbacks may unlink/free the current waiter before returning. Never
access it again. A cached successor must remain valid if traversal continues,
matching the baseline safe-list iterator requirement. Check the head sentinel
before deriving an enclosing waiter. Keep queue storage alive through final unlock.
Callback code/private state must be valid, nonnull, and obey incoming lock/context
rules; no Rust reference covers mutable queue or waiter storage.

Negative callback returns stop before budget accounting. Zero continues without
consumption. A positive return consumes exactly one exclusive slot, based on flags
observed before the callback. Zero budget means unlimited; negative budgets and
subtraction use the kernel's signed-wrapping behavior. Preserve mode, opaque key,
private WF_SYNC/WF_CURRENT_CPU constants and the sync wrappers' null-queue behavior.
Locked wrappers retain the caller's lock; others preserve incoming IRQ state.

Temporary C adapters retain ordinary spinlock_t IRQ save/restore, flags
observation/update, marked list mutations and constructor macros. The queue lock
does not protect all flag accesses:
wait_woken modifies WOKEN outside it. Direct Rust ownership or atomic references
need a separate mixed-access audit. Scheduler wake ordering remains in the C
scheduler. Raw-spinlock adapters are not substitutes for spinlock_t.
Default/woken/wait-bit callbacks, the WOKEN protocol, entry initialization,
locked interruptible iteration and __wake_up_pollfree remain C. Real epoll
POLLFREE can release a waiter's last
protection before its callback returns; ordinary close tests do not prove this race.

## Gates and scope

Nine `rusix_completion_wake` and five lifecycle cases join the strict core
inventory (44 total), so both combined and isolated core boots must execute them. The synchronous C fixture
configures inputs and records observations; Rust uses literal expected results.
It covers mixed exclusivity/order, zero/negative/positive callback returns,
zero/negative/INT_MIN budgets, pre-callback flag mutation, self-unlink/free, all
seven wrappers' arguments/IRQ handling, and null sync calls. The fixture clears
external ownership before freeing nodes and performs cleanup before assertions.
Uninstrumented frees exercise the path but cannot alone prove no post-free read.
Archive/object/symbol gates require exactly one definition of each wrapper in the
selected object and linked image, plus six enrollment/constructor and five
lifecycle definitions; fixture code is builtin-only Rust/KUnit=y.

The guest-only ordinary ext4 fixture adds four required consumer cases: pipe poll,
tagged pipe/eventfd epoll delivery and drain, one-shot suppression/rearm, and
DEL/last-close teardown with a surviving registration. Registration precedes
writes, so epoll callbacks are installed. The probe uses nonblocking descriptors,
finite waits, checked x86_64 ABI and RAII cleanup. It does not claim a thread was
blocked during notification, POLLFREE races, EPOLLEXCLUSIVE fairness, CFI, module,
other-architecture or exhaustive callback compatibility. Existing ext4 cases stay
required. Missing/duplicate/reordered/failing/skipped markers reject the whole run.

Next migrate WOKEN/bit-wait and locked interruptible policy, with blocked
consumers, then retire adapters with their ownership boundaries. Keep unchanged
upstream tests and explicit configuration limits.

## Enrollment and constructor contract

Six further Rust entries initialize the queue, add ordinary/exclusive/priority/
priority-exclusive entries, and remove entries. Fresh additions may have
uninitialized links: do not inspect them before list insertion. Ordinary and
priority insertion scan only the contiguous priority prefix; exclusive insertion
always appends. Priority-exclusive rejection examines only the first entry and
leaves the candidate flag update in place. Removal uses list_del poisoning, not
self-linking. Pre-lock flag RMW remains C and is not silently moved under the lock.

The constructor retains ordinary spin_lock_init, caller lock-class assignment,
then final-address self-links under exclusive initialization. Its non-RT debug
wait type is LD_WAIT_CONFIG, distinct from swait's LD_WAIT_SPIN. Static/dynamic
lockdep metadata lifetimes and disabled-lockdep unused/null arguments remain the
baseline contract. The four added cases verify structural order and actual
callback order, unrelated
field preservation, rejection with unchanged NULL links, stray priority tail,
all removal positions/self-links and poisoned re-addition, constructor class/name
and wait type, and IRQ restoration. Both debug and plain configurations pass;
plain tests explicitly distinguish unavailable lockdep metadata.

## Lifecycle and worker contract

prepare_to_wait, prepare_to_wait_exclusive and prepare_to_wait_event retain full
state-publication barriers. The signal-first event failure unlinks without a
state store. Exclusive preparation returns true only for a new insertion into an
empty queue. Finish restores RUNNING before the careful acquire check and unlinks
under lock without a second check. Autoremove retains C default_wake_function,
then performs release self-linking as its final entry access on any nonzero
return. The careful-delete adapter is not ordinary list_del_init.

Five required cases cover actual descheduled exclusive workers and token/payload
handoffs, nonmatching wakes followed by signals, original C macro condition/error
precedence, timeout cleanup before a late wake, and repeated prepare/finish with
pending-signal state preservation. Structural/order cases above remain required.
The controller retains independent task references; each callback owns an Arc
through return. Results are read only after that slot's completion acknowledgment.
Abort, queue wake-all and direct task wake precede bounded acknowledgment waits
and assertions. A missing acknowledgment fails; its callback still owns storage.

Scheduler-locked samples require expected state, off-CPU and off-runqueue status.
Separately protected membership is not an atomic cross-lock snapshot or proof of
later wake causation. Polling and worker loops have finite deadlines; scheduler
lock acquisition itself is not a hard time bound, and the VM has a watchdog.
Finite tests supplement, rather than prove, the barrier contract. WOKEN, blocked
bit-waits, locked interruptible consumers, PREEMPT_RT and POLLFREE races remain
outside this verification.
