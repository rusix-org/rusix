# Kernel migration inventory

All migrations follow accepted [architecture decision 0001](ARCHITECTURE.md):
preserve required boundary behavior, advance complete Rust subsystems, and remove
obsolete internal C interfaces. Record reference-only C separately from executing
fallbacks or shims. Retaining a reference file does not make its Rust replacement
incomplete; selecting its C implementation in a claimed migrated build does.

## int_sqrt — active on Rust builds; x86_64 comparison verified

Baseline: `21a7f44fd0765fcc5194130b28767786eba1d1e7`.
Sources: `lib/math/int_sqrt.c`, `include/linux/math.h`,
`lib/math/tests/int_sqrt_kunit.c`, `lib/math/Makefile`.
Rust implementation: `lib/math/int_sqrt_rust.rs`. Transitional export metadata:
`lib/math/int_sqrt_exports.c`. Added checks: `lib/math/tests/int_sqrt_rusix_kunit.c`
and `rusix/tests/int_sqrt_host.rs`.

Contract: return floor(sqrt(x)) for every unsigned-long value, preserving the
`unsigned long int_sqrt(unsigned long)` C ABI and non-GPL-only export. On 32-bit
architectures, also preserve `u32 int_sqrt64(u64)`; on 64-bit architectures that
interface is already an inline C wrapper around int_sqrt. No allocation, locking,
shared state, sleeping, or failure return is involved. Calls are legal during
early boot and in atomic context. No Rust panic path is acceptable.

Callers include page allocator minimum-watermark initialization, reclaim,
block writeback throttling, RCU grouping, NFS/Ceph limits, and device drivers.
Replacing the linked symbol affects real kernel paths, even in a small build.

Approach: translate the shift/subtract algorithm without algorithm changes;
retain C exports as a temporary metadata-only shim. Select Rust when CONFIG_RUST
is enabled and retain the upstream C fallback for configurations without Rust.
The fallback remains unfinished migration scope; it is not counted as removed C.
Remove it when Rust support covers the declared architecture/configuration matrix.

Verification gates:

1. Boot the unchanged baseline with its existing KUnit suite.
2. Extend boundary coverage to the native unsigned-long maximum, adjacent squares,
   and a deterministic differential corpus against the pinned C algorithm.
3. Build/boot the Rust replacement with those tests, inspect linked symbol and
   object provenance, and confirm no arithmetic panic dependency in the object.
4. Verify the non-Rust fallback still builds and tests. Verify 32-bit behavior
   separately; x86_64 results cannot establish that claim.

The initial upstream KUnit table has 21 inputs, all <= 2^32-1, so it is not enough
by itself to validate the full x86_64 input domain.

Current evidence: see `VERIFICATION.md` for clean committed C/Rust comparison,
32-bit host checks, retained C, and remaining kernel/module/configuration gates.

## Phase 1 component: RAM-backed block driver

Status: contract/API investigation only; no Rust BRD replacement implemented.
See `PHASE1.md` for the complete target, behavior inventory and exit gates.
Contract and proposed ownership design: [BRD.md](BRD.md).
VM baseline probe: [test instructions](../tests/brd-contract/README.md).

Reference: `drivers/block/brd.c`, `include/linux/bio.h`, `include/linux/blkdev.h`,
and the existing Rust block/page/xarray APIs. The bio-based C driver cannot be
treated as a drop-in user of the existing Rust blk-mq disk abstraction. Upstream
`rnull` does not store data and is not evidence of BRD parity. The first code work
requires C baseline tests plus an ownership/concurrency design, not a renamed
sample driver.

## Deferred cluster: gcd, lcm, lcm_not_zero

Status: source investigation only; no replacement implemented. Deferred behind
the Phase 1 foundation/BRD target rather than used to pad the migration count.
This remains a coherent cluster because `lib/math/lcm.c` calls `gcd`, and block queue geometry uses
both. A single Rust unit could preserve the three C entry points while making
their internal arithmetic calls Rust-to-Rust. This advances the accepted
architecture without creating an unused general-purpose math framework.

Reference: `lib/math/gcd.c`, `lib/math/lcm.c`, `include/linux/gcd.h`,
`include/linux/lcm.h`, `lib/math/tests/gcd_kunit.c`, and callers including
`block/blk-settings.c`. Preserve unsigned-long width, zero handling, wrapping
LCM arithmetic, `lcm_not_zero`'s exact fallback semantics, and GPL-only exports.
The upstream GCD suite has 11 parameter cases; LCM requires added coverage.

Architecture dependency: `gcd.c` owns `efficient_ffs_key`, which RISC-V setup may
disable when Zbb is absent; `CONFIG_CPU_NO_EFFICIENT_FFS` also selects the algorithm.
Both algorithms and this dispatch behavior need preservation and verification.
The current Rust jump-label API does not supply the needed true-key branch form.
Resolve that boundary explicitly rather than silently replacing both algorithms
with unconditional trailing-zero operations. Benchmark any temporary C bridge.

Tests must cover both algorithms, both integer widths, zero/maximum/high-bit
inputs, Fibonacci pairs, symmetry, and LCM overflow, comparing pinned C with an
independent Euclidean GCD oracle. Module/architecture gates from the first helper
remain prerequisites for broad compatibility claims.
