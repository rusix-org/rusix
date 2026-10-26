# Generic wait-queue wake policy

The working slice translates Linux 6.18.58 wait.c traversal/accounting and seven
wake wrappers into `kernel/sched/wait_rust.rs`. It shares the experimental,
default-off `CONFIG_RUSIX_COMPLETION_RUST` selection. Compilation and paired
runtime verification are pending; prior completion/swait evidence does not certify
this new code. No subsystem divergence point is declared.

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

Three temporary C adapters retain ordinary spinlock_t IRQ save/restore and the
baseline flags observation. The queue lock does not protect all flag accesses:
wait_woken modifies WOKEN outside it. Direct Rust ownership or atomic references
need a separate mixed-access audit. Scheduler/callback ordering stays with those
C implementations. Raw-spinlock adapters are not substitutes for spinlock_t.
Enrollment, initializer, default/autoremove/woken/wait-bit callbacks and
__wake_up_pollfree remain C. Real epoll POLLFREE can release a waiter's last
protection before its callback returns; ordinary close tests do not prove this race.

## Gates and scope

Five `rusix_completion_wake` cases join the strict core inventory (35 total), so
both combined and isolated core boots must execute them. The synchronous C fixture
configures inputs and records observations; Rust uses literal expected results.
It covers mixed exclusivity/order, zero/negative/positive callback returns,
zero/negative/INT_MIN budgets, pre-callback flag mutation, self-unlink/free, all
seven wrappers' arguments/IRQ handling, and null sync calls. The fixture clears
external ownership before freeing nodes and performs cleanup before assertions.
Uninstrumented frees exercise the path but cannot alone prove no post-free read.
Archive/object/symbol gates require exactly one definition of each wrapper in the
selected object and linked image; fixture code is builtin-only Rust/KUnit=y.

The guest-only ordinary ext4 fixture adds four required consumer cases: pipe poll,
tagged pipe/eventfd epoll delivery and drain, one-shot suppression/rearm, and
DEL/last-close teardown with a surviving registration. Registration precedes
writes, so epoll callbacks are installed. The probe uses nonblocking descriptors,
finite waits, checked x86_64 ABI and RAII cleanup. It does not claim a thread was
blocked during notification, POLLFREE races, EPOLLEXCLUSIVE fairness, CFI, module,
other-architecture or exhaustive callback compatibility. Existing ext4 cases stay
required. Missing/duplicate/reordered/failing/skipped markers reject the whole run.

Next establish real blocked wait_event/wait-bit handoffs and priority enrollment,
then migrate enrollment/callback policy and retire adapters with their ownership
boundaries. Keep unchanged upstream tests and explicit configuration limits.
