# Completion ownership and partial core migration

Linux 6.18.58 (`2926d88bb7fc4608fd942453d929c39e4e5ec006`) remains the
behavior reference. Opt-in Rust `complete()` and `complete_all()` build, link
exclusively and pass all ten core cases against C on q35 at `abec6b9cd125`.
[Paired broadcast evidence](../../docs/evidence/completion-broadcast/manifest.json).
`CONFIG_RUSIX_COMPLETION_RUST` defaults off and requires Rust/x86_64;
`completion-c` and `completion-rust` are the local comparison profiles.
This is neither a completed subsystem nor a declared divergence point.

## Implementation and remaining boundary

[`completion_rust.rs`](../../../kernel/sched/completion_rust.rs) preserves the C
layout, increments `done` unless it is `UINT_MAX`, then calls
`swake_up_locked(wait, 0)` under the embedded raw lock. Conditional Kbuild/C
selection retains exactly one intended `complete` definition and its C export.
The private non-Send guard restores the original IRQ flags on final unlock.

The counter uses **kernel LKMM `Atomic<u32>`**, not standard Rust atomics.
Its reference exists only while the raw lock is held: C plain writers hold the
same lock, lockless readers use `READ_ONCE`, and reset requires quiescence.
No Rust reference covers the containing concurrently mutable C object. Raw field
projection and scoped atomic access preserve the existing storage/alias boundary;
callers must keep initialized, pinned storage alive until the final lock release.

C still owns initialization/reset,
try-wait/status operations, all blocking/timed/interruptible wait loops, swait
queues, scheduler wakeups, and task/timer/signal integration. Raw-spin and lockdep macro helpers, plus LKMM atomic helpers, remain C.
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
five `rusix_completion_contract` cases plus seven `rusix_completion_layout` cases.
The two current-CPU cases are implemented with local build/runtime validation
pending; the archived broadcast source passed the prior ten-case inventory:

- Current-CPU signal counting/saturation and an observed enrolled-worker wakeup.
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
interruptible cancellation, deadline races, IRQ-context checks, lockdep/KASAN,
arm64, the nonempty `PROVE_RAW_LOCK_NESTING` assertion branch, and
Rust-completion-selected ext4 integration remain gaps.
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

Next: verify current-CPU signaling, then migrate the common wait engine and its
entry points, followed by `try_wait_for_completion` and `completion_done`.
Remove concurrent unmarked C counter writes before introducing lockless Rust
atomic references; the existing locked proof cannot justify those references.
Waiters need pinned stack storage and guaranteed unlink under the queue lock on
every exit. Preserve timeout/signal race order, IRQ transitions and I/O accounting.
Queue ownership and scheduler integration follow; Rust-native endpoints require
retiring C embedding/access. Preserve upstream `test-ww_mutex` unchanged.
