# Tree RCU callback-batch ownership contract

Status: the full Rust batch transaction and paired debug/plain routing are
implemented, source-reviewed and **unbuilt**. No runtime or linked-selection
result is claimed. `RUSIX_RCU_BATCH_RUST` is default-off; deselection retains the
literal Linux 6.18.58 `rcu_do_batch` and `rcu_do_batch_check_time` bodies. Both
sides retain Rust BRD, core and RCU lists.

Rust owns extraction, detached-chain dispatch, budget decisions and
reinsertion/accounting. It pins a private `Opaque<rcu_cblist>` before initializing
its self-relative tail, dequeues before invoking a callback and never accesses
that head afterward: callbacks may free or requeue themselves. Total callback
counts remain conservative until reinsertion and commit, preserving barrier
entrainment. Deadline comparison retains C's unsigned `local_clock()` conversion,
wrapping arithmetic and short-circuit clock cadence. The full rcuc path retains
BH enable, IRQ assertions, rescheduling and BH disable after each callback.

### Remaining C boundary

`rcu_batch_ffi_impl.h` lives in the canonical `tree.c` translation unit. Its typed
primitives project `rcu_data.cblist`, access per-CPU counters/status and global
parameters, and preserve plain versus marked C accesses. Other primitives cover
IRQ save/restore, BH/task scheduling, clocks, tick dependency, trace events,
callback debug lifecycle/function access and lockdep. Distinct warning/assertion
sites retain independent suppression state. No primitive executes the batch loop,
chooses budget exits or performs the extraction/commit transaction. List operations
call the already selected Rust list implementation through its existing ABI.

C still owns `rcu_data`, its layout/allocation, GP progression, enqueue/barrier and
hotplug callers, plus architecture/LKMM/debug services. There is no safe mutable
Rust reference to shared state or callback payload ownership claim. Remove these
adapters only as those fields gain proven Rust ownership and equivalent primitive
contracts; do not replace shared accesses with ordinary Rust loads or stores.
The small C dispatch wrapper and primitive calls are tracked executing C.
Selection excludes NOCB, BOOST and PREEMPT_RT; it does **not** exclude CPU hotplug
or the `rcutree.use_softirq=0` callback-thread mode.

## Test boundary and exact inventory

The test-only region under `RUSIX_RCU_BATCH_TEST` calls the selected production
batch on a separately allocated, zeroed `rcu_data`; no live RCU queues are reset.
The descriptor explicitly initializes its segmented list, batch limit and
non-running callback-thread status. All other fields accessed in this supported
mode have canonical zero values. Each head uses debug-object initialization and
queue/unqueue lifecycle. A retained worker holds `cpus_read_lock` and disables BH
around the call; no global environment override, replacement dispatch algorithm
or artificial controller task state is involved. Refused private teardown
records failure and retains both descriptor and callback storage.

Suite `rusix_rcu_batch`, six literal cases:

- `private_empty_and_fifo_accounting`: empty transaction, then three FIFO
  callbacks; each observes positive total count with detached main-list head;
  final total/segment counts, empty state and invocation accounting.
- `private_time_check_boundaries`: selected production time predicate with disabled budget,
  count31 no-clock path, count32 far-future deadline and expired deadline.
- `held_reader_payload_before_barrier`: CPU0 reader, CPU1 producer/orchestrator;
  no callback while reader remains held, then publication and barrier completion.
- `self_free_callback_final_access`: real callback frees its own separate node.
  This exercises the lifetime path; without memory poisoning/instrumentation it
  does not by itself prove the absence of every illegal post-free read.
- `self_requeue_once_before_second_barrier`: same real head requeues exactly once;
  two worker-side barriers cover the original and its newly submitted callback.
- `flood_exact_once_before_barrier`:129 unique callbacks exceed default count10;
  per-node seen counts/payloads and total count reject loss or duplication.

Private invocation is process context, so it intentionally does not claim
forced softirq budget exits. Deterministic partial-batch reinsertion and timing
exit decisions remain **pending coverage**. Flood completion establishes no
particular batch split or latency budget. The test boundary deliberately does
not introduce a scheduler/clock override merely to claim those cases.

## Lifetime and failure discipline

Controller, worker, reader and every real queued callback own separate context
references. Worker and reader task references survive through final context
release. The reader never sleeps within its ordinary RCU read section and has a
three-second release fallback; CPU1 drives release. A timed-out reader is a failed
prerequisite, not a valid grace-period observation. Only the retained worker
calls RCU barriers; the KUnit controller waits at most15seconds and releases its
reference before assertions. Missing callbacks retain their submission refs.
The self-requeue callback takes its replacement ref before submission and does
not inspect the node afterward. Self-free nodes are never inspected by cleanup.
Results become immutable before the worker's completion; only acknowledged
results may be read. Broken RCU/barrier/scheduler progress may retain workers and
storage indefinitely; the external VM timeout is final containment, not a claim
that RCU has an intrinsic finite timeout.

## Remaining work before migration acceptance

The C-first fixture baseline is committed as `6f240ef01d`; its recorded 17 host
script results belong to that baseline, not to the later production translation.
The production source review records preservation of the C bodies/test region,
Rust formatting, diff checks and exact input hashes in the local
`linux-out/rcu-batch-source-review-001` record. It is not compilation evidence.

Run C before Rust for both debug/plain profiles. Require 92 combined cases
(6 batch + 67 core + 10 list + 9 BRD), isolated controls, matching configurations
and actual tree-object call/selected-definition proof. Follow with ordinary
filesystem/server consumers and a separate `rcutree.use_softirq=0` runtime pair;
normal softirq execution cannot establish callback-thread behavior. Deterministic
partial-budget exits/reinsertion and CPU-hotplug runtime coverage remain pending.
The retained C caller protocol supplies the hotplug lifetime argument, not a new
hotplug test result. No dependency on uncompiled RCU-sync/perCPU/file-owner
branches is introduced by this worktree.
