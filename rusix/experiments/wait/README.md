# Generic wait-queue wake policy

Rust now implements thirteen Linux 6.18.58 wait.c entry points: seven wake
wrappers, initialization, four add variants and removal. Selection remains
experimental/default-off under `CONFIG_RUSIX_COMPLETION_RUST`. At `fe458e05562e`,
C/Rust debug and plain kernels each pass 48 combined cases (39 core + nine BRD),
then 39 isolated core cases. [Core evidence](../../docs/evidence/wait-enrollment/manifest.json).
The same source passes nine ordinary-userspace/storage boots per implementation,
including six ext4 and four poll-consumer cases with identical guest fixtures.
[Userspace evidence](../../docs/evidence/wait-enrollment-ext4/manifest.json).
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
observation/update, marked list mutations and constructor macros. The queue lock does not protect all flag accesses:
wait_woken modifies WOKEN outside it. Direct Rust ownership or atomic references
need a separate mixed-access audit. Scheduler/callback ordering stays with those
C implementations. Raw-spinlock adapters are not substitutes for spinlock_t.
Prepare/finish policy, default/autoremove/woken/wait-bit callbacks and
__wake_up_pollfree remain C. Real epoll POLLFREE can release a waiter's last
protection before its callback returns; ordinary close tests do not prove this race.

## Gates and scope

Nine `rusix_completion_wake` cases join the strict core inventory (39 total), so
both combined and isolated core boots must execute them. The synchronous C fixture
configures inputs and records observations; Rust uses literal expected results.
It covers mixed exclusivity/order, zero/negative/positive callback returns,
zero/negative/INT_MIN budgets, pre-callback flag mutation, self-unlink/free, all
seven wrappers' arguments/IRQ handling, and null sync calls. The fixture clears
external ownership before freeing nodes and performs cleanup before assertions.
Uninstrumented frees exercise the path but cannot alone prove no post-free read.
Archive/object/symbol gates require exactly one definition of each wrapper in the
selected object and linked image, plus six enrollment/constructor definitions; fixture code is builtin-only Rust/KUnit=y.

The guest-only ordinary ext4 fixture adds four required consumer cases: pipe poll,
tagged pipe/eventfd epoll delivery and drain, one-shot suppression/rearm, and
DEL/last-close teardown with a surviving registration. Registration precedes
writes, so epoll callbacks are installed. The probe uses nonblocking descriptors,
finite waits, checked x86_64 ABI and RAII cleanup. It does not claim a thread was
blocked during notification, POLLFREE races, EPOLLEXCLUSIVE fairness, CFI, module,
other-architecture or exhaustive callback compatibility. Existing ext4 cases stay
required. Missing/duplicate/reordered/failing/skipped markers reject the whole run.

Next establish real blocked wait_event/wait-bit handoffs, migrate prepare/finish
and callback policy, and retire adapters with their ownership boundaries. Keep unchanged upstream tests and explicit configuration limits.

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
baseline contract. The four added cases verify structural order and actual callback order, unrelated
field preservation, rejection with unchanged NULL links, stray priority tail,
all removal positions/self-links and poisoned re-addition, constructor class/name
and wait type, and IRQ restoration. Both debug and plain configurations pass;
plain tests explicitly distinguish unavailable lockdep metadata. Prepare/finish
and callbacks remain the next policy dependencies.

## Lifecycle migration in progress

Five further entries are implemented on the lifecycle branch, pending matched
build/runtime verification: prepare_to_wait, prepare_to_wait_exclusive,
prepare_to_wait_event, finish_wait and autoremove_wake_function. Prepare retains
full state-publication barriers; its signal-first failure unlinks without a state
store. The exclusive return is true only for a new insertion into an empty queue.
Finish restores RUNNING before the careful acquire check and unlinks under lock
without a second check. Autoremove retains C default_wake_function, then performs
release self-linking as its final access to the entry on any nonzero return.
The new careful-delete adapter cannot be replaced with ordinary list_del_init.

Real-worker tests must retain task references and callback-owned fixture lifetimes,
use finite deadlines and clean up before assertions. A scheduler-locked sample
can establish that a task was descheduled at that instant; separately protected
queue membership is not an atomic cross-lock observation or proof that a later
wake caused execution. Finite tests supplement, rather than prove, the barrier
contract. WOKEN flag protocols and locked interruptible waits remain later work.
