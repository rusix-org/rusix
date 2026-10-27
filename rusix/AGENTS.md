# rusix agent instructions

## Authority and resumption

[ADR 0002](docs/adr/0002.md) owns architecture and completion criteria; do not
redefine success around a driver or test milestone. The kernel rewrite is
authorized; host kernel changes, hardware installation, unrelated services and
production deployment are not. Global instructions still apply.

Read `PROGRESS.md`, the ADR, roadmap and relevant migration records on resumption.
Inspect Git status, source and actual evidence; revalidate process handles before
treating work as running or stopped. Choose an executable rewrite dependency.

## Repository and execution

Tracked `rusix/` is authoritative; paths here are relative to it unless stated
otherwise. Never restore outer copies over tracked files. Use `rusix/*` branches,
preserve others' work and published history, and push only to `origin`
(`rusix-org/rusix`), never the Linux `upstream`. Output/tool path conventions and
contributor commands are in [CONTRIBUTING.md](CONTRIBUTING.md).

Parallel agents are authorized: assign file ownership, serialize shared builds
and edits, and independently review nontrivial migrations. Check resources;
build on disk outside source and `/tmp`, initially with two jobs. Bound VM memory
and time. Never execute guest init probes, load experimental modules, modify the
bootloader or install the experimental kernel on the host.

Hosted CI spending is restricted. Follow [the local-only policy](ci/README.md);
do not enable or dispatch GitHub Actions without an explicit request.

## Implementation and unsafe code

Inspect the pinned C implementation, callers, Kconfig/Kbuild, tests and existing
Rust interfaces before editing. Define ABI/errors, overflow, allocation/context,
locking, lifetime and architecture contracts. Check Rust-for-Linux branches and
mailing-list proposals before adding generic bio, disk, xarray or allocation
abstractions; record prior work and review concerns. Prefer reusable APIs.

Prefer safe Rust. Each unsafe operation needs a specific invariant supported by
ownership, callers, synchronization and context. Raw pointers do not waive
aliasing or data-race requirements; establish boundary conditions before exposing
a safe API. Separate translation, semantic changes and redesign. Inventory
executing C/FFI and adapter removal criteria; prove Rust is selected in the
linked/running kernel. Follow the ADR's selected-fix and divergence policy.

## Verification and records

Preserve baseline upstream tests; add missing differential, boundary, failure and
concurrency coverage. Compare C/Rust with matching relevant inputs. Required
gates reject missing, skipped, duplicate and failed cases. Compilation, host tests
and VM execution establish different scopes, never full compatibility by themselves.

Record source/config/tool identities, commands, status, selection proof and raw
results. Retain failures and unexplained warnings; never report unexecuted checks
or pending runs as passing. Separate engineering-baseline and LTS evidence;
pinned inputs alone do not prove bit-identical reproduction.

Stage every manifest-promised stored file, including exact ignored paths, and
verify committed Git blob hashes before claiming an evidence archive is complete.
Raw binary references remain hash-only records, not promises to commit binaries.

Update `PROGRESS.md` after meaningful work and before ending: implemented work,
verified scope, blockers and next actions, with links to evidence and migration
records. Follow [licensing and authorship rules](CONTRIBUTING.md#licensing-and-authorship),
including the inherited kernel process guidance. Agents must not add human
Signed-off-by certification or present agent review as human-maintainer approval.
