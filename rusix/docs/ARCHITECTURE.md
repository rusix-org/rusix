# Architecture decision 0001: Linux-compatible outside, Rust-native inside

**Status: Accepted by Aaron, 2026-10-25.**

## Objective and decision

rusix is a Linux-derived operating system pursuing a Rust kernel implementation,
followed by migration of its remaining operating-system components to Rust.
The destination is a Rust-native kernel. Incremental replacement of existing
Linux components is the migration strategy, not the permanent architecture.

Our governing rule is:

> Preserve behavior at the boundary; use idiomatic Rust inside it.

Preserve Linux-compatible external behavior while progressively replacing C
implementation details and internal interfaces with Rust ownership, lifetimes,
and stronger types. Do not preserve C architecture merely to make translation
mechanical. Do not abandon Linux compatibility merely to make the rewrite easier.

## Compatibility boundaries

| Boundary | Policy |
| --- | --- |
| Applications and userspace ABI | Preserve Linux syscall interfaces, executable formats, error behavior, and observable semantics within the declared support matrix. |
| Persistent data and protocols | Preserve supported filesystem formats, device interfaces, and network protocols; explicitly test interoperability. |
| C callers and drivers still inside the kernel | Preserve the required ABI, layout, ownership, locking, lifetime, context, and error contracts at each migration boundary. |
| Interfaces entirely within a migrated Rust subsystem | Prefer Rust-native interfaces. Replace C-shaped structures and conventions when they no longer serve a required boundary. |
| Kernel modules | Preserve the specific interfaces still required during migration; this is not a promise of a permanently stable Linux internal module ABI or compatibility with every third-party module. |

Compatibility is a verified behavior contract, not an obligation to preserve
known defects. Upstream bug fixes or intentional behavior changes require an
explicit contract update and corresponding tests. Do not silently weaken tests
or label a regression an architectural improvement.

The initial verification target is x86_64 in a VM. That is an initial testing
target, not a reduction of the full rewrite goal or evidence for other hardware.
The eventual hardware and distribution support matrices remain to be specified.

## How implementation progresses

1. Identify an existing component's behavior, callers, dependencies, and tests.
2. Define the smallest necessary C/Rust boundary and document its invariants.
3. Implement safe, idiomatic Rust behind that boundary. Keep unsafe operations
   narrow and justified; prefer upstream Rust abstractions where they fit.
4. Run the unchanged upstream tests for the pinned baseline against both
   implementations, supplementing them with differential, boundary, concurrency,
   failure-path, workload, and performance checks as appropriate.
5. Activate Rust in the real kernel execution path and verify integration.
6. Migrate related components toward a complete Rust subsystem. As boundaries
   become Rust-to-Rust, redesign internal interfaces and remove obsolete adapters.

Keep translation and architectural redesign in separate reviewable changes.
An initial behavior-preserving translation can establish a baseline; it does not
oblige later Rust code to retain every C convention. Conversely, a Rust file full
of unchecked pointers does not by itself demonstrate the safety benefits we seek.

Prioritize coherent subsystem progress over an indefinitely growing collection
of isolated helper translations. The first integer-square-root migration proves
the comparison/build/test workflow; it is not the template for every subsystem's
architecture. Each subsequent migration should identify the subsystem it advances.

## Retaining C and following upstream

Retaining C **source as a reference** is different from retaining C **execution
in rusix**. Keep upstream history, source attribution, and original implementations
available for comparison and maintenance. A fully Rust kernel implementation may
retain uncompiled upstream C reference material in its repository/history.

During migration, C fallbacks may keep unsupported configurations functional.
Track them explicitly as unfinished runtime migration work. C export shims and
other executing/generated C boundaries also remain tracked work. A fallback
must not silently replace Rust in a configuration claimed as migrated.

For upstream updates:

1. Preserve the upstream history and pin the candidate upstream revision.
2. Integrate it on a separate `rusix/integration/*` branch. Keep `rusix/main` on
   its last verified baseline while parity work is pending.
3. Review affected reference implementations, public interfaces, callers,
   configuration, locking/lifetime assumptions, and tests. A conflict-free Git
   merge is not proof of semantic compatibility.
4. Update Rust for the new contract. Run both implementations against the same
   new upstream snapshot and relevant additional tests. Record old/new baseline
   revisions and any intentional changes in test expectations.
5. Promote the update only after the relevant gates pass. Preserve unresolved
   differences in the ledger rather than silently carrying stale Rust behavior.

Each migration record must identify its upstream reference files, Rust
implementation, public boundary, important callers/dependencies, original and
added tests, last verified upstream revision, retained C, and remaining gates.
Upstream remains a behavioral reference and source of fixes; it does not dictate
Rust-internal architecture forever. A deliberate departure needs a documented
decision, not an unnoticed consequence of merging.

## Alternatives considered

- **Permanent literal C-to-Rust translation:** makes initial comparison simpler,
  but risks retaining unsafe ownership conventions and unnecessary C interfaces.
  Use literal translation where useful as a step, not as the destination.
- **Redesign the whole kernel before integration:** permits broad internal
  freedom, but delays a working system and makes regressions difficult to isolate.
  Prefer progressively complete, tested Rust subsystems.
- **Abandon Linux external compatibility:** could enable a different operating
  system design, but changes this project's agreed direction. Do not substitute
  a separate demonstration kernel or incompatible OS for the Linux rewrite.

## Completion and change control

Neither a Rust-enabled Linux build nor one migrated subsystem completes this
objective. Completion requires the requested kernel and included OS components
to be implemented in Rust and verified against their declared contracts.
Reference-only C is not runtime implementation; executing C fallbacks and shims
remain visible unfinished scope. Architecture-specific assembly boundaries must
be separately inventoried and agreed rather than silently called Rust.

If evidence motivates a different direction, record the proposed change and
obtain Aaron's agreement to changes in objective or compatibility commitments.
Supersede this decision explicitly; do not gradually redefine success through
implementation shortcuts. Maintain `PROGRESS.md` and `docs/MIGRATIONS.md` as the
working evidence for this direction.
