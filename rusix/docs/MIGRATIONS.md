# Kernel migration inventory

## int_sqrt — active on Rust builds; x86_64 comparison verified

Baseline: `21a7f44fd0765fcc5194130b28767786eba1d1e7`.
Sources: `lib/math/int_sqrt.c`, `include/linux/math.h`,
`lib/math/tests/int_sqrt_kunit.c`, `lib/math/Makefile`.

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
