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

**LTS C and Rust drivers pass the six-case x86_64 SMP block contract.**
[Rust evidence](evidence/brd-rust-initial/manifest.json) records implementation selection;
nine ownership tests and paired ordinary ext4 also pass. Parameter/on-demand
coverage and broader validation are tracked in PROGRESS.
The driver/store live in `drivers/block/brd_rust.rs` and `brd_rust/store.rs`;
`rust/kernel/block/{bio,bio_disk}.rs` provide transitional interfaces.
Six x86_64 SMP baseline cases: [manifest](evidence/lts-baseline/manifest.json). [BRD.md](BRD.md) owns the pinned
C contract, implemented ownership design, upstream API research and unresolved
safety obligations. [Probe instructions](../tests/brd-contract/README.md) reproduce
that baseline; [Phase 1](PHASE1.md) defines replacement gates. Existing mq APIs
and upstream rnull are not substitutes for the bio-based stateful BRD contract.

## Completion: opt-in partial core migration

[`complete()`](../../kernel/sched/completion_rust.rs) has an opt-in Rust
translation (`0e7d592fed`, default off, x86_64). Local `completion-c`/`completion-rust`
profiles support comparison; compilation, exclusive-symbol linking and paired
runtime verification remain pending. C still owns layout/init/reset, other
completion operations, wait loops, raw locks, swait and scheduler integration.
The scoped kernel LKMM atomic counter shares the existing raw lock with C writers;
no Rust reference covers the enclosing mutable C object.

The [ownership experiment](../experiments/completion/README.md) owns the contract,
remaining dependencies and current nine-case inventory: five behavior cases,
one layout case and three worker cases. Historical six-case i440fx evidence does
not cover those workers or Rust selection. No completed subsystem or divergence
point is claimed. GCD/LCM remain deferred; [the roadmap](ROADMAP.md) prioritizes
this ownership/wait-wakeup boundary after BRD.
