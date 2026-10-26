# rusix roadmap

The target is a Linux-derived operating system whose kernel implementation is
rewritten in Rust, followed by incremental migration of its remaining components.
Linux itself is the kernel; userspace selection is a separate project decision.
No claim of full rewrite or distribution completeness is justified at bootstrap.

Accepted direction: [architecture decision 0001](ARCHITECTURE.md). Preserve
Linux-compatible external behavior; use Rust-native internal designs and migrate
incrementally toward complete subsystems. Required C interfaces are transitional
boundaries, not a permanent architecture constraint.

## M0 — Reproducible upstream foundation

Obtain and pin upstream Linux, retain licensing/history, create a rusix branch,
and record toolchain requirements. Establish a small x86_64 configuration with
Rust enabled, build it, and boot it in an isolated VM with captured console logs.
Success requires repeatable commands, exact revision/config, and observed boot.

## M1 — First actual C-to-Rust kernel replacement

Choose a bounded existing kernel implementation after inspecting its callers and
build rules. Specify the preserved semantics and replace the active implementation
with Rust. Test against upstream C, including edge cases, compile the linked
kernel, and exercise the implementation in a VM. Record remaining C/FFI costs.
First migration: integer square root; see `MIGRATIONS.md` and `VERIFICATION.md`
for actual evidence and outstanding gates.

## M2 — Repeatable subsystem migration

Inventory C and assembly by subsystem and dependencies. Migrate foundational
helpers and drivers, then memory management, scheduling, synchronization, VFS,
networking, security, and architecture support in dependency order. Each unit
needs explicit behavioral contracts, rollback boundaries, integration tests, and
performance checks. Reassess order as evidence exposes dependency constraints.
Track removed C execution paths, not just Rust line counts.
Each migration should advance a coherent subsystem. Once related components are
Rust, replace unnecessary internal C interfaces with Rust-native abstractions.

## M3 — Rust kernel completeness and compatibility

Audit every retained C implementation and assembly boundary. Demonstrate boot,
userspace ABI compatibility, filesystem/network behavior, concurrency correctness,
security invariants, and workload performance across a declared hardware matrix.
Any executing C fallback or shim remains visibly incomplete runtime migration
work. Upstream C retained solely as uncompiled reference material is allowed.
Define unavoidable assembly boundaries with Aaron rather than silently treating
an architecture shim as fully Rust.

## M4 — Remaining OS components

Inventory the chosen userspace/distribution: init, device management, libc/runtime,
utilities, shell, networking services, package/build tooling, and other included
components. Agree the distribution boundary and compatibility requirements before
claiming this phase is fully specified. Migrate each included component to Rust
with end-to-end system tests and licensing/provenance records.

## Decision rules

- Keep the Linux fork as the implementation base; a separate toy kernel does not
  satisfy the objective.
- Use existing upstream Rust infrastructure, expanding it when necessary for
  actual replacements. An enabling change must identify the migration it enables.
- Keep a working baseline and measure regressions; do not hide missing behavior
  by disabling required subsystems or weakening tests.
- These milestones organize the full objective; they do not redefine completion.
