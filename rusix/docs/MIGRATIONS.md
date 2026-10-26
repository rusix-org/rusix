# Kernel migration inventory

[ADR 0002](adr/0002.md) governs contracts, divergence and removal of executing C.
No subsystem divergence point has been declared. New integration work uses the
pinned Linux 6.18.58 baseline; earlier evidence retains its recorded source.

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

**Paired x86_64 q35 BRD verification passes** at `9d1c1ca5dd`:
[manifest](evidence/brd-q35/manifest.json) records block6, ext4 six cases, six
parameter boots and partition5, with identical fixtures and only driver selection
differing between configs. Nine ownership tests also pass. The negative-parameter
exception is replaced by [ADR 0003](adr/0003.md) at `ff6ac4a5d732`: fixed C and
Rust each pass 29 boots, including 26 parameter variants
([evidence](evidence/brd-parameter-fix/manifest.json)). Parameter storage/metadata
and other residual C boundaries remain.
The driver/store live in `drivers/block/brd_rust.rs` and `brd_rust/store.rs`;
`rust/kernel/block/{bio,bio_disk}.rs` provide transitional interfaces.
Six x86_64 SMP baseline cases: [manifest](evidence/lts-baseline/manifest.json). [BRD.md](BRD.md) owns the pinned
C contract, implemented ownership design, upstream API research and unresolved
safety obligations. [Probe instructions](../tests/brd-contract/README.md) reproduce
that baseline; [Phase 1](PHASE1.md) defines replacement gates. Existing mq APIs
and upstream rnull are not substitutes for the bio-based stateful BRD contract.

## Completion and wait queues: opt-in core migration

The opt-in [Rust signaling implementation](../../kernel/sched/completion_rust.rs)
preserves C-visible storage while moving completion policy into Rust.
The [ownership experiment](../experiments/completion/README.md) owns the contract,
current test inventory, evidence and remaining dependencies. The
[generic wait record](../experiments/wait/README.md) covers shared enrollment,
prepare/finish and wake-callback policy; the [bit-wait record](../experiments/wait-bit/README.md)
covers bit acquisition and stack-waiter ownership. The
[locked-wait record](../experiments/wait-locked/README.md) covers the two
interruptible iterations and blocking consumers. The
[wait-table ownership record](../experiments/wait-owner/README.md) covers the
Rust-owned permanent table, initialization and bit/variable wake dispatch. Selection remains
default-off in Kconfig and enabled by the declared x86_64 server target, with
[matched target evidence](evidence/wait-owner-server/manifest.json). No subsystem
divergence point is declared. GCD/LCM remain
deferred; [the roadmap](ROADMAP.md) prioritizes this core boundary after BRD.
