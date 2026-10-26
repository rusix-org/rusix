# Phase 1 delivery gates

[ADR 0002](adr/0002.md) defines the target and Linux 6.18.58 behavioral baseline.
The integration tree uses that baseline; earlier engineering results remain
attributed to their original commits. Gate completion is
observed evidence, not checked-in plans. See [PROGRESS.md](../PROGRESS.md).

## Phase 1a — Working x86_64 Rust BRD system

| Gate | Required result |
| --- | --- |
| Repository | A Kbuild-compatible checkout builds/tests using tracked tooling without parent copies or developer-specific paths. |
| Environment and CI | Pin container/compiler/Rust source/bindgen/QEMU/rootfs inputs. Execute required gates locally, retaining failures and source/config/tool/image identities; keep the manual CI definition ready. Required skips, missing cases and timeouts fail. Hosted execution is deferred until review readiness and explicit authorization under the [execution policy](../ci/README.md). |
| Complete BRD | Rust implements the pinned RAM-disk driver contract with [ADR 0003](adr/0003.md): data/holes, discard, geometry/partitions, parameters/aliases, on-demand creation, accounting, rollback and teardown. Verify the x86_64 built-in form; C reference remains available but cannot execute in the claimed Rust path. |
| Paired parity | C and Rust run matching preserved upstream tests plus BRD-specific cases. Bind expected implementation and build evidence to the tested image. Basic lifetime, allocation/error and competing-insertion behavior must be correct; expanded stress is in 1b. |
| Useful userspace | Boot pinned ordinary Linux init/shell/utilities. Format/mount ext4 on Rust BRD; verify buffered/direct I/O where supported, files, rename, fsync, unmount/remount, content integrity and offline fsck. A custom test init alone does not satisfy this gate. |
| Review and ownership | Review unsafe invariants and upstream API proposals; record remaining C dependencies and the subsystem divergence point. |

The complete component is BRD, not the surrounding storage stack. Block core,
VFS, ext4 and allocator C dependencies remain tracked kernel work. The
[BRD contract/design](BRD.md) owns detailed behavior and unsafe-boundary analysis;
do not duplicate it here or replace BRD with a data-discarding null driver.

## Phase 1b — Expanded assurance

| Gate | Required result |
| --- | --- |
| Architecture | arm64, 4 KiB pages and SMP, passes the common integrity suite. Add built-in/module lifecycle coverage on both architectures, including x86_64 math export/version checks. |
| Failure and concurrency | Deterministic allocation/NOWAIT faults, overlapping I/O/discard lifetimes, memory pressure, busy removal and repeated teardown; supported Rust memory instrumentation and lockdep with demonstrated coverage and no unexplained new reports. |
| Performance and memory | Controlled paired sequential/random/mixed I/O, discard and sparse allocation. Initial thresholds: throughput at least 90% of C, p99 latency at most 110%, populated-store memory at most 110%. Pin the protocol and measure baseline variance first. TCG timing is not production performance evidence. |
| Selected-fix maintenance | Review one relevant upstream fix, port its behavior deliberately into a migrated Rust component and demonstrate the regression test. Record relevance/disposition; no whole-tree rebase requirement. |

The selected-fix exercise is verified; [ADR 0003](adr/0003.md) records its
contract and evidence. Other gates remain independently required.

Bit-identical kernel/initramfs output on two independent workers is deferred.
Pinned inputs and recorded provenance remain mandatory. Budget changes or
behavioral departures require recorded decisions; do not weaken tests silently.

## Sequence and limitations

Finish the baseline/container/local verification work, establish C workloads, review reusable
upstream abstractions, implement Rust BRD and run paired tests, then complete the
1b matrix and budgets. Immediately after BRD, start the executable core ownership
spike in [ROADMAP.md](ROADMAP.md), rather than an indefinite sequence of drivers.

Keep exclusions and remaining C explicit. Instrumentation configuration alone
is not coverage: pinned KCSAN rules currently export C instrumentation flags,
so enabling KCSAN does not demonstrate Rust race instrumentation.
