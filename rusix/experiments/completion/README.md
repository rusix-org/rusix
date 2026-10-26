# Completion ownership spike

Status: **kernel contract/layout tests and a host ownership model**. Baseline
Linux 6.18.58 (`2926d88bb7fc4608fd942453d929c39e4e5ec006`). The initial six
kernel cases passed on x86_64 i440fx; q35 verification is pending. Two added
worker tests are implemented but not compiled or executed. Production completion
behavior and upstream tests remain unchanged; no subsystem is declared migrated.

## Inspected boundary

- `include/linux/completion.h`, `include/linux/swait.h` and
  `kernel/sched/{completion,swait}.c`: counting state, embedded raw spinlock,
  intrusive FIFO waiters, scheduler wakeups and IRQ state transitions.
- `rust/kernel/sync/completion.rs`: the existing pinned, opaque C-layout wrapper
  provides broadcast and uninterruptible wait; it delegates both operations to C.
- `block/bio.c:submit_bio_wait`: a stack completion escapes through `bi_private`;
  the synchronous wait keeps it alive until the asynchronous end-I/O callback.
- `kernel/kthread.c:__kthread_create_on_node`: interruption requires an atomic
  ownership handoff of `create->done`, or a second wait before stack teardown.
  A timeout/signal result alone cannot authorize freeing callback storage.
- `kernel/locking/test-ww_mutex.c`: existing callers exercise counting,
  timed waits and embedded completions. Preserve this upstream test unchanged.

## Behavior and layout obligations

`done` counts successful signals; a successful wait consumes one unless it is
`UINT_MAX`. Increment saturates at that sentinel; `complete_all` sets it, serving
future waiters too. Reset writes zero, but callers must ensure prior waiters and
producers have finished. `completion_done` does not prove quiescence, especially
after broadcast. Wake order is FIFO queue order, not a guarantee of task execution
order. Signal/timeout paths must unlink their stack waiter before returning.
Timeout success returns at least one remaining jiffy; interruption uses
`-ERESTARTSYS` where specified. Preserve completion-vs-timeout/signal race ordering
from `do_wait_for_common`, including completion observed after reacquiring the lock.

Remaining C callers allocate, embed, statically initialize and directly reset
`struct completion`. Its `unsigned int done` plus `swait_queue_head` layout must
remain intact during transition, including configuration-dependent raw-lock and
lockdep layout and self-referential list initialization. Do not hard-code sizes or
replace it with an Arc pointer. Generate size/alignment/offset assertions against
bindings for each actual x86_64/arm64 configuration before selecting a replacement.
Pin initialized queue storage; never create exclusive Rust references over fields
that C can concurrently access. Preserve READ_ONCE-style observations, lock
serialization, IRQ-save/restore behavior, lockdep annotations and scheduler memory
ordering. Ordinary Rust atomics or a host mutex are not evidence of LKMM parity.

## Migration dependencies

1. Extend the implemented C baseline/layout tests into a differential suite:
   pre-signals, token exhaustion/saturation, broadcast, FIFO enrollment, timed and
   interrupted waits, completion at timeout, cancellation and quiescent reuse.
   Use controlled worker handshakes, and validate lockdep/KASAN runs in VMs.
2. Implement counting and wait-loop control in Rust over the preserved C layout.
   Keep temporary raw-spin/IRQ, swait enqueue/unlink/wake, task-state/signal and
   schedule-timeout calls explicit. Every stack waiter needs pinned lifetime and
   guaranteed unlink on every return path. Keep I/O accounting and
   `complete_on_current_cpu` wake flags. Make C/Rust symbol selection exclusive;
   exercise existing C callers against both implementations.
3. Move queue ownership and wake integration into Rust with task lifetime and
   scheduler primitives. Remove each temporary helper once both sides are owned.
   This dependency crosses synchronization, task state, scheduler, timers and
   signal delivery; a standalone leaf port cannot complete it.
4. Migrate callers to scoped borrowed endpoints or owned endpoints. Only after
   C embedding/initialization/access is gone may the layout become Rust-native.
   Arc allocation is an option for heap lifetimes, not a requirement for existing
   stack/no-allocation or interrupt-context paths. RCU is a separate dependency
   for task lifetime where needed, not an assumed replacement for quiescence.

## Executable ownership model

`model.rs` uses only safe standard-library Rust. It tests token accounting,
saturation/broadcast, reset refusal while endpoints exist, producer storage
surviving an abandoned waiter, and concurrent token consumption. It intentionally
has no blocking wait: no FIFO, IRQ, memory-order, signal, timeout, task-state,
allocation-context or kernel-layout proof is claimed. A dropped endpoint models
storage ownership only, not cancellation of a queued kernel waiter. Mutex poison
unwraps are host-test conveniences, not proposed kernel behavior.

Run from the checkout root, writing artifacts outside the source tree:

```sh
mkdir -p ../lts-integration-out/experiments/completion
rustc --edition=2021 --test -D warnings rusix/experiments/completion/model.rs \
  -o ../lts-integration-out/experiments/completion/model-test
../lts-integration-out/experiments/completion/model-test
```

Next: execute the worker cases and review the pinned waiter/IRQ-safe lock
interface before attempting Rust completion control flow.

Local execution on 2026-10-25: `rustc 1.99.0 (b940084d7 2026-09-28)`,
compile exit 0; five tests passed, zero failed/ignored/filtered. This is a host
toolchain observation, separate from the pinned kernel/container toolchain.

## C baseline kernel contract suite

The test-only `rusix_completion_contract` module in
`rust/kernel/sync/completion.rs` calls the original C implementation through
pinned Rust-owned storage. Exact five-case inventory:

- `initial_state_has_no_token`
- `presignals_are_consumed_once_each`
- `broadcast_persists_until_quiescent_reset`
- `zero_timeout_reports_completion_and_consumes_token`
- `signal_saturates_instead_of_wrapping`

Reset/saturation use direct counter writes only while the test is the sole user,
with no outstanding waiter or producer; queue layout is untouched. Zero-timeout
waits exercise the C return contract without an unbounded worker. No production
API was added. These five cases do not cover worker handoff, FIFO, interruption
or timeout races.
The initial `rusix_completion_layout` case is
`c_operations_share_pinned_rust_owned_storage`: a Rust-owned `repr(C)` layout
with compile-time size, alignment and field-offset checks is initialized and
operated on by the original C completion functions. Rust reads/resets its counter
only while quiescent. This is a storage interoperability spike, not a replacement
implementation, concurrent waiter test, or proof for other configurations.

Two additional kernel cases in that suite are implemented, pending compilation
and execution:

- `worker_handoff_observes_published_value`: a safe unbound workqueue closure and
  test task exchange notifications and a Relaxed LKMM atomic payload through C
  completions. Pre-signaling is allowed; deterministic blocked wakeup is not claimed.
- `timed_out_worker_unlinks_before_late_signal`: a worker waits with a positive
  timeout on an unsignaled completion, reports its return, then a late signal is
  consumed once by the test task. This exercises enrollment/timeout teardown.

Concurrent cases use the existing upstream `Completion` wrapper, not the private
single-task `Layout`. Safe workqueue closure ownership and kernel Arc pin every
completion until its last user returns. Waits are finite (20 ms/5 s for workers,
10 s for observers). A test timeout may leave a scheduled worker with its own
Arc; no callback borrows KUnit stack storage or performs assertions. The finished
notification acknowledges the final data access, not workqueue callback exit;
there is no bounded join API here. Thus no queue-wide flush or unsafe lifetime
extension is used. External VM timeout still bounds scheduler failure. FIFO,
interruptible cancellation and completion-at-deadline races remain untested.

Use `kunit.filter_glob=rusix_completion_*` to select both suites. The recorded
six-case gate/result below covers the original five C behavior cases and one
layout case. The new worker cases require a reviewed eight-case inventory before
recording a new result; missing, duplicate, skipped or failing cases must reject.
BRD ownership tests retain their separate nine-case inventory.

## Recorded verification

The five host cases also pass with pinned container Rust 1.85.1:
[recorded output](../../docs/evidence/completion-host/manifest.json).
The original six x86_64 kernel cases passed with zero skips on i440fx, alongside
all nine BRD cases: [evidence and source](../../docs/evidence/completion-kernel/manifest.json).
That build reused a copied KUnit object cache and retained original artifacts.
It does not verify the two new worker cases or q35. Host results do not establish
kernel layout or scheduling behavior.
