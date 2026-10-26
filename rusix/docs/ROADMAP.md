# rusix roadmap

[ADR 0002](adr/0002.md) defines the accepted target, compatibility baseline and
subsystem divergence policy. This roadmap orders implementation; it does not
expand or narrow that contract. Actual state is in [PROGRESS.md](../PROGRESS.md).

## Phase 0 — Integration bootstrap

Retain the verified Rust square-root replacement, original tests, added parity
checks and source evidence. The C BRD probe establishes the next component's
baseline.

## Phase 1a — Working Rust storage component

Transition deliberately to the accepted LTS baseline, inventory any newer Rust
infrastructure, pin a container toolchain and establish CI. Implement complete
BRD behavior on x86_64, with paired C/Rust tests and ordinary Linux userspace
performing verified ext4 I/O. Basic error, ownership and concurrency correctness
are required. [PHASE1.md](PHASE1.md) lists the gates.

## Phase 1b — Expanded validation

Add arm64, expanded failure/concurrency stress and instrumentation, and measured
performance/memory budgets. Port one selected upstream fix with its regression
test instead of rehearsing whole-tree rebases. Independent-machine bit-identical
builds are deferred; recorded pinned inputs are required now.

## Early core work — Completion ownership and wait/wakeup

Immediately after BRD, produce an executable `struct completion` ownership and
wait/wakeup spike. Inventory embedded C uses, lifetime and ordering constraints,
and the temporary boundary needed while C callers remain. Do not assume that a
C-accessed layout can change. Use its results to validate this dependency order:

1. Synchronization, completion/wait queues and RCU ownership.
2. Task/thread lifecycle, scheduling and timer dependencies.
3. Page ownership, allocation, faults and virtual-memory management.
4. VFS/ext4 and required pseudo-filesystems; virtio block transport.
5. Network core/protocols and virtio network transport.

These are dependency candidates to refine through source inspection, not a
promise that whole subsystems can be replaced independently. Every completed
subsystem gets a divergence record and removes obsolete C adapters. Track linked
C contributions and unknown/generated contributions alongside behavior coverage;
do not substitute more leaf drivers or Rust line counts for reducing the C core.

## Complete target kernel, then userspace

Audit all code required by the declared configurations. Verify their system,
compatibility, isolation and performance contracts, and inventory necessary
assembly separately. Executing C fallbacks/shims remain unfinished implementation.
After the target kernel is complete, agree the userspace/distribution inventory
and migrate those components with pinned interfaces and end-to-end tests.
