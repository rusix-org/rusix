# Completion and swait core migration

Linux 6.18.58 (`2926d88bb7fc4608fd942453d929c39e4e5ec006`) is the behavior
reference. All fourteen completion.c entry points and nine swait.c operations
have opt-in Rust implementations. At `e7b7b9a94103`, both implementations pass
29 core cases plus nine BRD cases, then 29 isolated core cases with lock/list/sleep
checks enabled. [Instrumented evidence](../../docs/evidence/swait-wrappers/manifest.json).
The same source passes nine ordinary-userspace storage boots per implementation.
[Ext4 evidence](../../docs/evidence/swait-wrappers-ext4/manifest.json).

`CONFIG_RUSIX_COMPLETION_RUST` defaults off and requires Rust/x86_64 builtins.
The four driver families with incompatible plain counter access are excluded by
Kconfig. Use the local `completion-c`/`completion-rust` and
`core-ext4-c`/`core-ext4-rust` profiles; [execution policy](../../ci/README.md).
No subsystem divergence point is declared.

## Storage, counter and lifetime contract

[`completion_rust.rs`](../../../kernel/sched/completion_rust.rs) preserves the
configuration-dependent C layout. C callers still embed and initialize/reset it;
an Arc pointer cannot replace their ABI. Storage and embedded list links remain
pinned, initialized and live through the operation's final unlock.

The counter uses kernel LKMM `Atomic<u32>`, not standard Rust atomics. Updates
hold the raw lock; short lockless references implement status/try-wait fast checks.
All selected concurrent core accesses are marked LKMM operations. Initialization
and reset require external quiescence. No Rust reference covers the containing
C object, and no counter reference survives an unlocked scheduling interval.
The [counter audit](../../docs/evidence/completion-counter-audit/manifest.json)
records reviewed dependencies, excluded drivers and its limits as a source scan.

Signals preserve saturation at UINT_MAX and broadcast persistence. A private
immutable C integer supplies `WF_CURRENT_CPU` without exposing scheduler headers.
`completion_done` keeps its positive-read lock handoff without rereading after
acquisition; it is not proof of producer/waiter quiescence. A timeout alone never
permits freeing callback storage: `submit_bio_wait` and interrupted kthread
creation illustrate the distinct ownership/handoff obligations.

## Blocking wait and shared queue policy

[`completion_rust/wait.rs`](../../../kernel/sched/completion_rust/wait.rs)
implements the shared wait engine and nine blocking entries. An Opaque waiter
is initialized at its final pinned stack address. The queue lock covers state
checks and enqueue/unlink; IRQs are enabled around the retained scheduler call.
Every exit restores task state and unlinks before stack storage disappears.
Preserve signal/timeout race order, positive timeout success of at least one jiffy,
signed returns and I/O accounting. All nine entries retain `.sched.text` placement.

[`swait_rust.rs`](../../../kernel/sched/swait_rust.rs) implements four shared
locked primitives and five outer wrappers. They preserve FIFO enrollment/removal,
not CPU execution order. Wake precedes unlink; unlink is the final waiter access:
a generic finisher may observe self-links and free its stack before the waker
releases the queue lock. The original lock also protects detached batch nodes.

Generic `swake_up_all` pins a temporary head, detaches the initial batch and
enables IRQs between nonfinal wakes. Newly enrolled nodes stay on the original
head. Reload the batch after each reacquisition; never retain a node reference
across it. Its caller must enter with IRQs enabled. Other outer wrappers preserve
incoming IRQ flags through private non-Send guards.

Prepare uses the full `set_current_state` barrier. Pending-signal prepare removes
the node unconditionally, leaves task state unchanged and returns `-ERESTARTSYS`;
the original C consumer macro determines condition precedence. Finish restores
RUNNING before `list_empty_careful`, then locks and deletes without a second check.
C macro adapters preserve marked pointer accesses, list validation and state hooks.

## Verification and remaining coverage

The strict `rusix_completion_*` inventory has five contract, eight layout,
four wait, four signal and eight swait cases:

- Counter/token/saturation/broadcast behavior, layout and pinned C-visible storage.
- All blocking entry points on presignals/broadcast; timed zero/positive exits.
- Payload handoff, current-CPU enrolled wake, two-token and competing consumers.
- Dedicated-thread pending/enrolled signals, token precedence, killable nonfatal timeout.
- Empty queue/IRQ restoration, repeated enrollment, structural FIFO removal,
  original generic condition macro and timeout cleanup before a late wake.
- Fresh/enrolled pending-signal removal preserves a distinct task state and IRQs.
- Generic interruptible error versus condition becoming true after prepare.
- Initial broadcast batch removal and a separately enrolled post-return waiter.

Workers own pinned Arcs and use finite deadlines. Successful stopped-thread creation
transfers one Arc to its callback and retains a task reference before wakeup;
failure reclaims the Arc. No stop-before-start cancellation path exists. Signals
are confined to dedicated tasks with private handlers. Cleanup precedes assertions.
Final notification acknowledges data publication, not callback exit; callbacks
retain ownership until return. KUnit-only C observation helpers are absent from
ordinary userspace/server builds.

Required gates reject missing, duplicate, skipped or failed cases. Symbol/archive
checks prove all fourteen completion and nine swait definitions come from the
selected objects, and verify scheduler text placement. Instrumented profiles enable
BUG, lockdep/raw-lock nesting, atomic-sleep, DEBUG_LIST and LIST_HARDENED. Earlier
minimal profiles lacked BUG and did not establish the same assertion coverage.

Outstanding: forced diagnostic violations, deterministic detached-batch concurrent
enrollment/spurious-wakeup races, broadcast wake latency, untimed signal paths,
deadline races, all IRQ contexts, Rust race instrumentation, arm64, modules and
performance budgets. Current broadcast coverage does not force enrollment during
its unlock window. Historical failures/results remain in the
[verification index](../../docs/VERIFICATION.md), including initial conversion
errors and warnings resolved before the passing pairs.

## Remaining C and next ownership step

C still executes queue/completion initialization/reset, raw-lock and lockdep
macros, list/state/LKMM adapters, task wakeup, scheduler/timer/signal primitives
and generic consumer macros. Next translate the swait initializer while preserving
raw-lock class/name and LD_WAIT_SPIN in debug/nondebug configurations. Its
constructor needs exclusive quiescent storage and synchronized publication; that
argument cannot justify unmarked writes on live queues. Then retire adapters as
Rust owns the corresponding primitives and callers. Preserve upstream tests,
including `test-ww_mutex`, and the declared configuration bounds.

`model.rs` remains a host-only standard-library ownership model: five tests cover
accounting, saturation, quiescent reset, abandoned storage and concurrent consumers.
[Historical host evidence](../../docs/evidence/completion-host/manifest.json).
It provides no kernel layout, IRQ, LKMM or blocking-wait proof. Run it with
`rustc --edition=2021 --test -D warnings`, writing the binary outside the source tree.
