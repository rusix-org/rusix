# Phase 1: a migration base and a complete Rust storage component

## Required outcome

Phase 1 ends with an independently buildable Linux-derived kernel running
ordinary Linux userspace and a complete Rust RAM-backed block driver doing real
filesystem I/O. CI continuously compares it with the pinned C implementation.
The original C driver remains available for reference/comparison, but does not
execute in the selected Rust driver path.

The published square-root replacement is **Phase 0 bootstrap**. Historical
checkpoints M0/M1 are not completed Phase 1. Phase 1 still leaves most Linux code
in C; it does not complete the full kernel or subsequent userspace rewrite.

This engineering target follows Aaron's request for the base expected of a
well-funded rewrite. The driver choice is based on source inspection, not a claim
that Aaron personally selected BRD. Architecture decision 0001 remains governing:
Linux-compatible externally, Rust-native internally, incremental migration.

## Selected complete component

Replace `drivers/block/brd.c`: the RAM-backed block-device driver. It owns real
data, allocation, concurrent access, errors, registration, and teardown, while
avoiding hardware transport/DMA in the first slice. The surrounding block layer,
filesystem, VFS, and allocator remain explicit C dependencies at this stage.
Enabling an already-upstream Rust driver is not our implementation achievement.

The pinned source exposes substantive API and ownership work:

- BRD uses bio-based `block_device_operations.submit_bio`. Current Rust block
  APIs expose mq; their disk builder calls `__blk_mq_alloc_disk`.
- Upstream `rnull` completes requests without storing their contents. Adapting
  that sample alone does not provide BRD semantics.
- C BRD uses RCU lookup/revalidation, page references, competing insertion, and
  discard synchronization. Rust page/xarray APIs require a deliberate ownership
  design. Naive lookup-then-store can lose a competing insertion; unchecked
  overlapping page transfers do not establish a sound Rust implementation.

Add narrowly scoped bio/non-MQ disk and backing-page abstractions that the driver
actually needs. Keep ownership, synchronization, errors, and lifecycle policy in
Rust. Remaining C bridges may expose ABI/inline/macro/export metadata; delegating
driver logic to C does not pass the milestone. Switching BRD to blk-mq would be
a separate architectural decision, not a shortcut around its existing contract.

## Exact exit state

Every gate requires implementation and observed evidence. Documents/configuration
alone do not satisfy it. All gates are currently open at their full scope.

| Gate | Required codebase state |
| --- | --- |
| P1-01: canonical repository | A fresh clone with any Kbuild-compatible directory name builds/tests without copying files into its parent or depending on Aaron's home directory. Project docs/configs/scripts/tests have one tracked source of truth. Standard Kbuild remains the kernel build system. |
| P1-02: reproducible environment | Compiler, Rust source, bindgen, dependencies, QEMU and test-rootfs inputs are pinned and independently installable on a clean Linux worker. Two clean workers reproduce kernel/initramfs hashes with timestamp, identity, path and configuration inputs controlled. Caches are optional. |
| P1-03: complete driver | Rust implements BRD reads/writes, zero-filled holes, discard, capacity/partitions, parameters/aliases, on-demand creation, accounting, initialization rollback and teardown. Built-in and module forms work. Rust-native internals have documented ownership and synchronization. |
| P1-04: useful system | Pinned ordinary Linux userspace boots, creates/mounts ext4 on the Rust RAM disk, runs integrity-checked buffered/direct I/O where supported, creates/renames/fsyncs files, unmounts/remounts, verifies contents and runs filesystem consistency checks. RAM loss on unload/reboot is expected; durable storage is not claimed. |
| P1-05: continuous parity | CI compares pinned C/Rust implementations with matching relevant configurations and workloads, preserves upstream tests, and adds driver-specific coverage. Required gates reject failures, skips, missing cases and timeouts. Source/config/tool/rootfs/image identities and the actual selected implementation are bound to each run. |
| P1-06: failure and concurrency | Allocation failure, NOWAIT, competing insertions, overlapping I/O, discard edges, memory pressure, busy removal and repeated teardown are tested. Supported Rust memory instrumentation, lockdep and SMP stress produce no unexplained new reports. Instrumentation scope is demonstrated. |
| P1-07: matrix | x86_64 and arm64, 4 KiB pages, SMP, each with built-in and module driver forms, pass the common integrity/lifecycle suite. The x86_64 module profile also verifies version checks and the existing math consumer fixture. Other architectures/page sizes remain unverified until added. |
| P1-08: resource/performance budget | Controlled paired runs cover sequential/random read/write, mixed I/O, discard and sparse allocation. Initial budget: at most 10% throughput loss, p99 latency increase or populated backing-store memory increase. Record baseline variance before judging the port. TCG-only timing is not production performance evidence. Budget changes require a recorded design decision, not silently weakened tests. |
| P1-09: upstream maintenance | Migration records map reference files, callers, contracts, tests, Rust implementation, unsafe invariants and retained C. Rehearse one relevant upstream change through an integration branch, detecting and correcting parity drift before promotion. Review findings and human/agent provenance are explicit. |

The matrix bounds Phase 1 verification, not the ultimate rewrite objective.
Production readiness, all-hardware compatibility, and the entire Rust kernel are
later milestones. Performance thresholds above are targets, not observed results.
Specifically, throughput must be at least 90% of C, p99 latency at most 110%,
and populated backing-store memory at most 110% under the matching workload.
Before measuring the Rust port, pin workload sizes, sampling/aggregation, and
variance handling in the benchmark protocol. Maintain a separate explicit
inventory of excluded upstream tests and reasons; required coverage must not
silently shrink to make CI green.

## BRD contract inventory

Establish checked-in tests against the C baseline before translating the driver:

- Zero reads from holes; preservation outside partial writes; transfers crossing
  bio segments/page boundaries and at device capacity boundaries.
- Full-page discard and preservation of partially covered edge pages, matching
  pinned C behavior rather than assuming every discarded byte becomes zero.
- Concurrent insertion and read/write/discard lifetimes; legal overlapping I/O
  semantics and their explicit Rust synchronization model.
- `REQ_NOWAIT` allocation/locking and would-block versus I/O errors; ordinary
  allocation's no-I/O recursion requirements.
- `rd_nr`, `rd_size`, `max_part`, legacy `ramdisk_size=`, numbering, partition
  limits, aliases, on-demand devices, and optional debugfs page accounting.
- Initialization rollback, memory/accounting recovery, busy-device protection,
  and repeated module load/use/unload.

Initial inspection found no dedicated BRD KUnit suite. Supplement the unchanged
upstream tests with driver-specific differential coverage and a pinned block/
filesystem test selection. Intentional fixes/semantic changes belong in separate
patches with explicit contracts, not hidden inside the rewrite.
For example, pinned C `brd_init` ignores individual precreated-device allocation
failures. Establish that baseline behavior in tests and treat any improvement as
a separate semantic-change patch rather than quietly changing initialization.

KCSAN configuration alone does not prove Rust race coverage: pinned Kbuild KCSAN
rules currently export C instrumentation flags. Supported Rust KASAN, lockdep,
and stress results must state which paths they cover. No sanitizer or language
choice proves complete memory/concurrency safety.

## Execution order

1. Keep valid Phase 0 code/evidence and label its scope honestly.
2. Replace workspace mirroring with repository-native tooling, pin the build/test
   environment, and establish CI using the existing small tests. Bind automated
   results to the expected implementation and actual built image.
3. Establish BRD's C contract/workload baseline; review bio/disk/page-store
   ownership before introducing new unsafe APIs.
4. Implement the complete Rust driver in reviewable steps and run paired tests.
5. Complete matrix, failure, resource/performance and upstream-rehearsal gates;
   publish an evidence-backed Phase 1 report.

More unrelated helpers, a null driver discarding data, a demonstration kernel, or
more scaffolding cannot substitute for this outcome. The module probe remains
useful test infrastructure; its custom Rust init is not P1-04's ordinary userspace.
See `AUDIT-PHASE0.md` for current deficiencies and `PROGRESS.md` for actual status.
