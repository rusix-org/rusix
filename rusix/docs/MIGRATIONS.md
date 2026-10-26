# Kernel migration inventory

[ADR 0002](adr/0002.md) governs contracts, divergence and removal of executing C.
No subsystem divergence point has been declared. Existing evidence uses
`21a7f44fd0765fcc5194130b28767786eba1d1e7`; the LTS transition remains pending.

## Integer square root

**Selected on Rust builds; x86_64 comparison verified.** Implementation:
`lib/math/int_sqrt_rust.rs`; reference and non-Rust fallback: `lib/math/int_sqrt.c`;
export metadata shim: `lib/math/int_sqrt_exports.c`. Public ABI:
`include/linux/math.h`; selection: `lib/math/Makefile`.

Contract: floor(sqrt(x)) for all unsigned-long inputs; preserve the unrestricted
`unsigned long int_sqrt(unsigned long)` export and 32-bit `u32 int_sqrt64(u64)`
entry point (inline wrapper on 64-bit). No allocation, shared state, sleeping,
failure return or panic path; early-boot and atomic callers remain supported.
The shift/subtract translation preserves unsigned wrapping arithmetic.

Tests: unchanged `lib/math/tests/int_sqrt_kunit.c` (21 inputs), added
`int_sqrt_rusix_kunit.c`, and `rusix/tests/int_sqrt_host.rs` cover wider boundaries
and differential inputs. [Verification](VERIFICATION.md) records comparison,
object selection, host ABI results and unverified module/configuration scope.
The executing C fallback and export shim remain inventory items; remove them
when the declared target and export mechanism no longer require them.

## RAM-backed block driver

**C baseline verified; Rust driver not implemented.** Six x86_64 SMP cases:
[manifest](evidence/brd-c-baseline/manifest.json). [BRD.md](BRD.md) owns the pinned
C contract, proposed ownership design, upstream API research and unresolved
safety obligations. [Probe instructions](../tests/brd-contract/README.md) reproduce
that baseline; [Phase 1](PHASE1.md) defines replacement gates. Existing mq APIs
and upstream rnull are not substitutes for the bio-based stateful BRD contract.

## Next core boundary

After BRD, investigate completion ownership and wait/wakeup as specified in
[the roadmap](ROADMAP.md). GCD/LCM remain unimplemented, deferred investigations;
they are not migration progress or the next implementation target.
