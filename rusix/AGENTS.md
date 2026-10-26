# rusix agent instructions

## Authority and resumption

[ADR 0002](docs/adr/0002.md) is the accepted architecture and completion contract;
[ADR 0001](docs/adr/0001.md) remains historical context where not superseded.
Do not redefine completion around the current driver or test milestone.
The kernel rewrite is authorized; host kernel changes, hardware installation,
unrelated services and production deployment are not.

At session start, read `PROGRESS.md`, the accepted ADR, `docs/ROADMAP.md`, and
relevant migration records. Inspect Git status, source and actual artifacts.
Revalidate a process handle before treating work as running or stopped. Pick
an executable dependency toward the rewrite, not unrelated scaffolding.

## Repository and collaboration

- Tracked `rusix/` is authoritative. Paths here are relative to that directory
  unless stated otherwise. Do not restore outer copies over tracked files.
- Use `rusix/*` branches. `origin` is `https://github.com/rusix-org/rusix.git`;
  `upstream` is Linux and must never receive our pushes. Preserve others' work
  and published history.
- Tools resolve the checkout themselves. Outputs default to sibling
  `<checkout-name>-out`; override with `RUSIX_OUTPUT_ROOT`. Local tools default
  to `$RUSIX_OUTPUT_ROOT/.tools/root`; override with `RUSIX_TOOLS_ROOT`.
  Relative overrides resolve against the invoking directory.
- Parallel agents are authorized. Assign clear file ownership, serialize shared
  builds/edits, and use independent review for nontrivial migrations.
- Build on disk outside source and `/tmp`, initially with `-j2`. Check resources.
  Bound VM memory/time. Never execute guest init probes, load experimental
  modules, alter the bootloader, or install the kernel on the host.

## Implementation and unsafe-code discipline

Before editing, inspect the pinned C implementation, callers, Kconfig/Kbuild,
upstream tests and existing Rust interfaces. Record the preserved contract:
ABI/errors, overflow, allocation/context, locking, lifetime and architecture.
Check Rust-for-Linux branches and mailing-list work before introducing generic
bio, disk, xarray, allocation or similar abstractions; record applicable prior
work and review concerns. Prefer reusable, upstream-reviewable APIs.

Prefer safe Rust. Each unsafe operation needs a specific invariant and evidence
that ownership, callers, synchronization and context uphold it. Raw pointers do
not waive aliasing or data-race requirements. Do not expose safe APIs until their
boundary conditions are established. Separate translation, semantic changes and
redesign in reviewable commits. Inventory executing C/FFI and adapter removal
criteria; prove the Rust path is selected in the linked/running kernel.

Apply the ADR's selected-fix policy and subsystem divergence records. Do not
resume automatic whole-tree rebases or merge reference C back into a divergent
Rust subsystem. Baseline changes and behavioral departures require decisions
and fresh verification.

## Verification and records

Preserve baseline upstream tests unchanged; add missing differential, boundary,
failure and concurrency coverage. Compare C/Rust under matching relevant inputs.
Required gates reject missing, skipped, duplicate and failed cases. Compilation,
host checks and VM execution prove different scopes; no narrow result establishes
full compatibility or absence of bugs.

Record exact source/config/tool versions, commands, status, selection evidence
and raw results, retaining failures and unexplained warnings. Never mark an
unexecuted check or pending CI run green. Keep host-specific and LTS results
separate; pinning inputs is not proof of bit-identical reproduction.

Update `PROGRESS.md` after meaningful work and before ending a session, linking
detailed evidence and the migration record. Keep the baseline, implemented work,
verified scope, blockers and next actions explicit. Do not erase unresolved
failures or replace evidence with plans.

Preserve Linux licensing, attribution and SPDX notices. Follow the Git-root
`Documentation/process/coding-assistants.rst`, `generated-content.rst`, coding
and submission guidance. Disclose substantial generated content. Agents must
not add human Signed-off-by certification or represent agent review as human
maintainer approval. See `CONTRIBUTING.md` for reproduction and review requirements.
