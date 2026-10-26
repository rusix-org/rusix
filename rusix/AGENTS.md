# rusix agent instructions

## Objective and authority

Fork Linux and progressively replace its kernel implementation with Rust, then
migrate the remaining operating-system components one at a time. Preserve this
objective across sessions. A Rust module, demonstration kernel, or Rust-enabled
Linux build is a milestone, never evidence that the rewrite is complete.

Architecture decision 0001 in `docs/ARCHITECTURE.md` is accepted by Aaron:
Linux-compatible external behavior, Rust-native internals, incremental migration.
Preserve behavior at required boundaries; do not freeze C implementation details
inside Rust. Work toward complete Rust subsystems and remove obsolete adapters.
Retained upstream C references are allowed; executing C remains tracked migration
work. Changes to these commitments require an explicit superseding decision.

Aaron's global instructions continue to apply. The requested Linux/Rust rewrite
authorizes work on this project's kernel; it does not authorize changes to the
host kernel, unrelated backends, services, homelab, or production systems.
Ask before installing or booting rusix on physical hardware. Use isolated build
directories and virtual machines for verification.

## Resume protocol

1. Read `PROGRESS.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, and relevant
   local instructions.
2. Inspect actual Git status, diffs, source, and existing build/test artifacts.
   Treat ledger claims as pointers to evidence, not as evidence themselves.
3. Revalidate any recorded process before restarting work. Never assume a lock
   file means a process is alive or an observation timeout means it died.
4. Select the next dependency toward the real rewrite. Record any changed scope
   or assumptions. Do not replace hard migration work with unrelated tooling.
5. Update `PROGRESS.md` after meaningful work and before ending a session.

## Repository and provenance

- `linux/` is the Linux-derived Git repository. Keep upstream history and
  license notices. Record the exact starting commit and source remote.
- Root documents govern the project and live outside the kernel source tree.
  Keep versioned copies in `linux/rusix/` using `scripts/sync-project-docs.sh`.
  Root copies are authoritative; edit them, then sync before committing.
- Work on a `rusix/*` branch. Keep upstream remote named `upstream` and never
  push to it. Publishing remote `origin` is the public
  `https://github.com/rusix-org/rusix.git`, created as a GitHub fork of `torvalds/linux` at Aaron's request.
  Aaron clarified that the existing kernel build and passing tests suffice for
  the first source push once documentation and contribution guidance are ready.
  Module/export and broader architecture checks remain disclosed follow-up work,
  not first-push blockers. Follow `docs/PUBLICATION.md` and verify its readiness
  evidence before the first push. No production release or complete-rewrite claim
  is authorized by this milestone. Do not rewrite history or discard someone
  else's changes.
- Use small, reviewable migrations. Separate mechanical translation, interface
  changes, and algorithm changes. Retain attribution and SPDX identifiers.
- Pin and record toolchain versions and configurations. Explain upstream
  rebases and conflicts; never silently change the baseline to make tests pass.
- Integrate upstream updates on a separate integration branch, assess semantic
  changes in migrated code and its callers, and restore Rust parity before
  promotion to `rusix/main`. Follow `docs/ARCHITECTURE.md`; a clean merge is not
  sufficient evidence. Preserve upstream tests for each pinned snapshot.

## Migration requirements

- Before editing, read existing C implementation, callers, Kconfig/Kbuild,
  tests, and pinned upstream Rust interfaces. Prefer established interfaces.
- Define behavior to preserve: ABI, error values, integer overflow, allocation,
  concurrency, locking, interrupt context, lifetime, and architecture assumptions.
- Integrate Rust into the real kernel build and execution path. A parallel
  implementation that is never selected does not count as migrated.
- Keep compatibility with Linux userspace and supported hardware explicit.
  Start verification with x86_64 in a VM; do not claim other architectures work
  until tested. Assembly and unavoidable hardware/FFI boundaries must be tracked.
- Use safe Rust where possible. Each unsafe block must explain its safety
  invariant and why callers, ownership, and synchronization uphold it. Avoid
  unchecked pointer conversions or panics in kernel paths.
- Transitional C is allowed during migration, but inventory it and retain a
  concrete replacement/removal criterion. Do not label wrappers as rewrites.
- For each migration, add meaningful boundary and differential tests against
  the upstream behavior. Include failure and concurrency tests where relevant.
  Verify symbol/build integration and boot/runtime behavior as applicable.
- Preserve the existing upstream test suite unchanged as a compatibility gate.
  Run baseline C and replacement Rust against the same tests/configuration.
  Add missing coverage separately; do not weaken expectations to fit a rewrite.
  Passing tests establishes tested behavior, never complete absence of bugs.
- Never equate compilation with correctness, host tests with kernel execution,
  or a successful VM boot with full Linux compatibility.

## Resource and verification discipline

- Build under this workspace on disk, never in `/tmp`. Use modest parallelism
  (initially `-j2`) on this laptop and inspect available memory/disk first.
- Never modify the host bootloader or load an experimental kernel module on the
  host as part of routine testing. Bound VM memory and execution time.
- Record exact commands, exit status, relevant versions/configuration, and log
  locations. Preserve failed results as well as successes. Do not fabricate
  results or mark an unexecuted command as verified.
- Document missing dependencies precisely. Prefer project-local tools where
  practical; do not change global toolchain defaults to satisfy a local build.
- Aaron authorizes parallel sub-agents for independent work. Assign clear file
  ownership or read-only review tasks; serialize builds in each output directory
  and integration edits. Use independent review for nontrivial migrations.

## Living progress ledger

`PROGRESS.md` must contain the baseline, current milestone, implemented work,
verification evidence, blockers, next executable actions, and chronological
session entries. Keep it concise by linking longer evidence under `docs/` or
`linux/rusix/`. Never erase unresolved failures or silently promote planned work
to completed. Mark work as planned, implemented/unverified, verified (with scope),
or blocked. Completion means the original objective is implemented and verified,
not merely that the current milestone passed.

## External review and contributors

Aaron expects heavy scrutiny and wants outside developers to be able to join.
Treat every initial migration as a public-review candidate: small diffs, preserved
attribution, reproducible commands, precise behavior contracts, and explicit
limitations. Record the source revision, resolved config, compiler versions, and
raw runtime evidence behind verification claims. A reviewer must be able to
reproduce a result without relying on chat history. Keep upstream tests unchanged
and added tests visibly separate. Document residual C, untested architectures,
and known gaps prominently; do not market an early experiment as a finished OS.

The source-tree `AGENTS.md` points to this synchronized guide. Also follow the
inherited `linux/Documentation/process/coding-assistants.rst` and
`linux/Documentation/process/generated-content.rst` guidance (paths relative to
the outer workspace), including its rule that AI agents must not add human
Signed-off-by certification. Keep the upstream README and process documents
intact; project-specific guidance supplements them.
