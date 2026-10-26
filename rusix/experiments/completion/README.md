# Completion ownership and partial core migration

Linux 6.18.58 (`2926d88bb7fc4608fd942453d929c39e4e5ec006`) remains the
behavior reference. All fourteen completion.c entry points now have opt-in Rust implementations,
link exclusively and pass all twenty-one core cases against C on q35 at
`afaedde2732b`.
[Paired evidence](../../docs/evidence/completion-status/manifest.json).
`CONFIG_RUSIX_COMPLETION_RUST` defaults off and requires Rust/x86_64 builtins;
`completion-c` and `completion-rust` are the local comparison profiles.
This is neither a completed subsystem nor a declared divergence point.

## Implementation and remaining boundary

[`completion_rust.rs`](../../../kernel/sched/completion_rust.rs) preserves the C
layout, increments `done` unless it is `UINT_MAX`, then calls
`swake_up_locked(wait, 0)` under the embedded raw lock. Conditional Kbuild/C
selection retains exactly one intended `complete` definition and its C export.
The private non-Send guard restores the original IRQ flags on final unlock.

The counter uses **kernel LKMM `Atomic<u32>`**, not standard Rust atomics.
Counter updates hold the raw lock; short lockless references implement the
status/try-wait fast checks. All selected concurrent core accesses are marked
LKMM operations; initialization/reset requires external quiescence.
No Rust reference covers the containing concurrently mutable C object. Raw field
projection and scoped atomic access preserve the existing storage/alias boundary;
callers must keep initialized, pinned storage alive until the final lock release.

C still owns initialization/reset, swait queues, scheduler wakeups, and
task/timer/signal integration. Raw-spin and lockdep macro helpers, plus LKMM atomic helpers, remain C.
Replace those boundaries only with reviewed Rust scheduler/locking/atomic
interfaces. Preserve FIFO enrollment (not task execution order), saturation,
timeout success of at least one jiffy, interrupt errors and race ordering.

C callers embed and directly initialize/reset completion storage. Preserve actual
configuration-dependent layout, lockdep and pinned list links until those callers
migrate; an Arc pointer cannot replace their ABI. `submit_bio_wait` demonstrates
stack callback lifetime, while `__kthread_create_on_node` requires ownership
handoff or a second wait after interruption. A timeout alone never permits freeing
callback storage. `completion_done` is not proof of producer/waiter quiescence.

## Kernel verification

Select `kunit.filter_glob=rusix_completion_*`. The strict current inventory is
five `rusix_completion_contract`, eight `rusix_completion_layout`, four
`rusix_completion_wait` and four `rusix_completion_signal` cases. All twenty-one
pass on both implementations:

- Current-CPU signal counting/saturation and an observed enrolled-worker wakeup.
- All nine wait entry points consume presignals and preserve broadcast; all four
  timed variants distinguish zero-timeout states and unlink after positive timeout.
- Competing nonblocking consumers take exactly one token after an observed
  two-waiter start gate.
- Dedicated threads verify pending/enrolled signal interruption, pre-signaled
  token precedence and nonfatal-signal timeout for killable waits.
- Initial empty state, pre-signal consumption, persistent broadcast/reset,
  zero-timeout return/consumption, and saturation.
- `c_operations_share_pinned_rust_owned_storage`: `repr(C)` size/alignment/offset
  assertions and pinned initialization; counter inspection/reset is quiescent.
- `worker_handoff_observes_published_value`: single completion and LKMM payload
  publication; pre-signaling is allowed, blocked wakeup is not guaranteed.
- `two_workers_consume_exactly_two_tokens`: concurrent waiters and two signals.
- `broadcast_serves_two_workers_and_late_waiters`: a KUnit-only helper counts
  two enrolled waiters under the queue lock; both must finish before worker
  timeouts, and late waits remain successful. The helper is absent from server builds.
- `timed_out_worker_unlinks_before_late_signal`: positive timeout followed by a
  late signal consumed exactly once.

Workers use
pinned Arc-owned upstream wrappers, finite waits and no borrowed KUnit stack.
Their final notification acknowledges data access, not callback exit; retained
Arc ownership protects late callbacks. VM timeout bounds scheduler failure.
Missing, duplicate, skipped or failing cases reject a run. FIFO execution,
untimed signal paths, deadline races, IRQ-context checks, lockdep/KASAN,
arm64, the nonempty `PROVE_RAW_LOCK_NESTING` assertion branch, and
instrumented integration remain gaps.
BRD ownership has a separate nine-case inventory.

**Historical evidence:** the original five contract cases and one layout case
passed on x86_64 **i440fx**, using a copied KUnit object cache:
[kernel manifest](../../docs/evidence/completion-kernel/manifest.json).
That result proves neither the three worker cases, q35 nor Rust `complete()`.

## Host model and next work

`model.rs` is a safe standard-library ownership model, not a kernel replacement.
Its five tests cover accounting, saturation/broadcast, quiescent reset, abandoned
waiter storage and concurrent consumption; it has no blocking wait, IRQ, LKMM,
FIFO, timeout or kernel-layout proof. Five cases passed with host Rust 1.99.0 and
[pinned container Rust 1.85.1](../../docs/evidence/completion-host/manifest.json).

```sh
mkdir -p ../lts-integration-out/experiments/completion
rustc --edition=2021 --test -D warnings rusix/experiments/completion/model.rs \
  -o ../lts-integration-out/experiments/completion/model-test
../lts-integration-out/experiments/completion/model-test
```

Current-CPU signaling now uses the shared Rust counting path and a private
immutable C `int` initialized from `WF_CURRENT_CPU`; this four-byte data bridge
keeps the scheduler macro authoritative until Rust owns that boundary.

Next: migrate swait queue policy and its generic consumers. The status pair removed remaining
concurrent plain C counter writes before introducing lockless Rust references.
Waiters need pinned stack storage and guaranteed unlink under the queue lock on
every exit. Preserve timeout/signal race order, IRQ transitions and I/O accounting.
Queue ownership and scheduler integration follow; Rust-native endpoints require
retiring C embedding/access. Preserve upstream `test-ww_mutex` unchanged.

## Blocking wait translation

The private `completion_rust/wait.rs` implements the shared wait loop and nine
entry points. It initializes an `Opaque<swait_queue>` in final pinned stack
storage, holds the queue lock across state checks and enqueue/unlink, enables
IRQs around the retained scheduler call, and reacquires before touching protected
state. No LKMM atomic reference survives that unlock. The original `.sched.text`
placement and C exports are retained; section and exclusive-symbol gates check
the linked image. Four macro/inline adapters for IRQ locking, signal queries and
current task state remain C, as do queue and scheduler primitives.

The four wait cases above do not inject signals or test deadline races.
The [initial evidence](../../docs/evidence/completion-wait-initial/manifest.json)
retains a test conversion failure and ten Rust declaration/visibility warnings.
Explicit integer casts, private symbol visibility and an opaque pointer at the
private swait ABI resolved those diagnostics before the clean paired run.

## Counter-access configuration boundary

The [target audit](../../docs/evidence/completion-counter-audit/manifest.json)
records reviewed dependency inventories and their source/config identities.
Known plain completion-counter reads in OneNAND, MT7601U, IPR and SGI GRU lack a
demonstrated synchronization proof against Rust atomic stores. Kconfig excludes
these families, including modular forms, and excludes modules for this built-in
slice. No reviewed external counter access appeared in the completion/server
inventories; their direct Rust test accesses are quiescent. This textual review
is not whole-tree alias analysis. Expanding configurations requires another
boundary review, not merely enabling the option. Initialization and reset still
require caller-provided quiescence.

## Signal testing and remaining queue work

Dedicated test kthreads have private signal handlers; no KUnit controller or
shared worker receives an injected signal. A successful stopped-thread creation
transfers one Arc reference to its callback and retains a separate task reference
before wakeup. Creation failure reclaims the Arc; no stop-before-start path exists.
Cleanup broadcasts before assertions. Finished notification acknowledges result
publication, not callback exit; callback-owned Arcs protect delayed execution.
These KUnit-only C creation/signal/jiffy helpers are excluded from server builds.
The nonfatal timeout case checks elapsed jiffies, and other cases must complete
before their ten-second worker deadlines. This is not module-unload evidence.

The next queue slice covers `__prepare_to_swait`, `__finish_swait`,
`swake_up_locked` and `swake_up_all_locked`. Some also serve generic swait/RCU:
retain marked list updates and debug validation, and test those callers too.
Deletion must be the final waiter access because generic `finish_swait` can
observe self-links and release stack storage without acquiring the queue lock.
Scheduler wakeup still precedes deletion. List primitives and task wakeup remain
explicit dependencies until their own ownership migration.

## Ordinary-userspace integration

[Paired core/ext4 evidence](../../docs/evidence/completion-ext4/manifest.json)
at `3df316f9971f` uses Rust BRD in both kernels, with only C/Rust completion
selection differing. Both pass block and ordinary Debian ext4 operations,
six parameter boots and partition checks. Four fixture archives are byte-identical;
all fourteen symbols and blocking scheduler-text placement are verified. This
extends the focused core tests without implying a full-kernel rewrite, arm64
support or a measured performance budget.

## Shared swait policy under verification

The working slice replaces `__prepare_to_swait`, `__finish_swait`,
`swake_up_locked` and `swake_up_all_locked`. C list adapters retain marked pointer
accesses and hardening/debug validation; initialization, outer generic wrappers,
raw locking and scheduler task wakeup remain C. This also affects generic swait
consumers, so five dedicated cases check empty wake/IRQ restoration, repeated
enrollment/state restoration, structural FIFO removal, the original C condition
macro, and timeout cleanup before a late wake. No CPU execution order is claimed.

The current completion comparison profiles enable `BUG`, `PROVE_LOCKING`,
`PROVE_RAW_LOCK_NESTING`, `DEBUG_ATOMIC_SLEEP`, `DEBUG_LIST` and `LIST_HARDENED`.
Explicit `BUG=y` matters: without it, the baseline WARN macros can be silent.
The new 26-case inventory and instrumented profiles are pending verification;
prior 21-case and ordinary-userspace results remain attributed above.
