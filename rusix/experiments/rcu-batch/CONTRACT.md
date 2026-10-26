# Tree RCU callback-batch ownership contract

Status: C-first fixture implementation, unbuilt; explicit local debug/plain
profiles `rcu-batch-c` and `rcu-batch-plain-c` are wired.
No Rust batch policy exists here. No runtime or new linked-selection evidence is
claimed. Baseline is the pinned `rcu_do_batch` and `rcu_do_batch_check_time` in
`kernel/rcu/tree.c`; their original function bodies remain unchanged.

The intended migration owns the entire extraction, detached-chain dispatch and
reinsertion/accounting transaction. Rust will pin the private `rcu_cblist` before
initializing its self-relative tail, own dispatch rights while detached, dequeue
before calling a potentially self-freeing callback, and never touch its node
again afterward. It must preserve retained total counts until commit so barrier
entrainment cannot mistake a detached but unfinished batch for zero work.

C `rcu_data`, its segmented-list layout, parameters, per-CPU allocation, GP
engine, enqueue/barrier/hotplug callers, and debug/trace/IRQ/scheduler primitives
remain dependencies. This is not ownership of all RCU per-CPU state. No safe
mutable reference may span callback invocation while C enqueue remains possible.
Initial selection must exclude NOCB, BOOST and PREEMPT_RT. Target CPU-hotplug
behavior remains an explicit follow-up obligation, not silently excluded support.

## Test boundary and exact inventory

The test-only region under `RUSIX_RCU_BATCH_TEST` calls the actual private C
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
- `private_time_check_boundaries`: original time predicate with disabled budget,
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

The C-first profiles verify unchanged original C source plus test hooks and
require one C tree/fixture object with exact hook definitions. Independently
review and run these C profiles first, then translate the complete transaction
with independent source review. Require debug/plain pair6batch+67core+10list+9BRD
(92combined), fresh filesystem/server consumers, and actual linked-selection
proof. Separate supplemental budget-exit and hotplug coverage from this initial
inventory. No dependency on uncompiled RCU-sync/perCPU/file-owner branches is
introduced by this worktree.
