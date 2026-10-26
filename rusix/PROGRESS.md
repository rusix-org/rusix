# rusix progress

## Objective and current milestone

Fork Linux, rewrite its kernel in Rust, then migrate remaining OS components.
**Active; not complete. Phase 0 bootstrap is published; Phase 1 is not complete.**
Historical bootstrap checkpoints M0/M1 cover the Rust-enabled boot and first
integer-square-root replacement, with passing host/VM comparisons. They do not
constitute the Phase 1 migration base requested by Aaron. The exact next-phase
target is `docs/PHASE1.md`; the published-code audit is `docs/AUDIT-PHASE0.md`.
Module/export and broader verification remain outstanding. Current evidence:
`docs/VERIFICATION.md`. Full scope: `docs/ROADMAP.md`.

**Accepted architectural direction:** Linux-compatible external behavior,
Rust-native internals, incremental replacement toward complete Rust subsystems.
Preserve behavior at necessary boundaries; remove obsolete C interfaces as the
Rust implementation grows. Retain upstream C as reference material while tracking
all executing C as unfinished migration work. See `docs/ARCHITECTURE.md` (decision
0001, explicitly agreed by Aaron).

## Baseline and workspace

- Upstream: `https://github.com/torvalds/linux.git`, remote `upstream`, commit
  `21a7f44fd0765fcc5194130b28767786eba1d1e7`; local branch `rusix/main`.
- Linux Makefile reports 7.3.0 during the 7.4 merge window. History is shallow.
- Tracked `rusix/` inside the Git checkout is canonical. The local checkout
  happens to be named `linux/`; scripts do not require that name or a parent
  workspace. The former document synchronization command is retired.
- Public GitHub repository `https://github.com/rusix-org/rusix` is now a verified
  fork of `torvalds/linux`. `origin` points there; `upstream` still points to Linux.
  Aaron accepted the existing built/tested layer for first publication once docs
  are ready. The first source push succeeded at `5520dd71e`; `rusix/main` is the
  default branch and issues are enabled. See `docs/PUBLICATION.md`.
- No host kernel installation or host module loading.
- Build with two jobs on disk outside the source checkout; QEMU TCG uses one
  CPU/512 MiB. Outputs default to sibling `<checkout-name>-out`, overridable
  with `RUSIX_OUTPUT_ROOT`; local tools accept `RUSIX_TOOLS_ROOT`.
- Rust 1.99.0 (LLVM 23.1.1), Clang/LLD 23.1.3, bindgen 0.73.2, QEMU 11.1.2.
  Rust source and i686 target are installed; default toolchain is unchanged.
- Missing system packages were extracted into `.tools/root` with SHA-256 checks
  against the existing pacman database. See `docs/packages.lock` and TOOLCHAIN.md.

## Implemented

- Strong project instructions, full-scope roadmap, contributor entry point,
  migration contracts, local tool setup, configuration, build and VM scripts.
- Rust translation of native `int_sqrt` and the separate 32-bit `int_sqrt64` ABI;
  metadata-only C export shim. CONFIG_RUST now selects the Rust implementation;
  non-Rust configurations retain the original C fallback.
- Original upstream square-root suite remains unchanged. Separate KUnit tests
  compare original C behavior and independent mathematical bounds, including
  full-width boundaries. Host tests compile the actual pinned C source.
- Strict test-result gate rejects skipped/missing/duplicate/failed required cases.
  Build evidence uses fresh directories; boot labels cannot overwrite old results.
  Recorded builds require a clean committed source tree and matching configuration.
- Two independent review agents inspected the translation and workflow. Findings
  drove 32-bit coverage, strict suite acceptance, immutable evidence, system
  firmware fallback, Git worktree support, and clean-source build requirements.

## Verification (scope matters)

- Upstream `make LLVM=1 rustavailable`: passes with local tool wrapper.
- Initial baseline: kernel builds and boots; 23 KUnit cases pass (21 unchanged
  square-root inputs and two upstream Rust cases). Raw log: `logs/baseline-console.log`.
- C implementation plus added tests: 26 KUnit cases pass; `logs/c-compat-*`.
- Rust implementation plus same tests: 26 KUnit cases pass; `logs/rust-compat-*`.
  Resolved C/Rust configurations compare byte-for-byte equal. Archive lists
  `int_sqrt_rust.o` and export shim instead of `int_sqrt.o`; linked image has one
  `int_sqrt` definition. Rust object has no undefined symbols/panic dependency.
- Native host tests: 3 pass, covering 2,012,482 inputs against pinned C and
  independent square bounds with Rust overflow checks enabled.
- i686 host ABI tests: 5 pass via explicitly selected qemu-i386 userspace
  emulation; log `logs/int-sqrt-host-i686-qemu.log`. Native i686 execution also
  passed outside the sandbox. This is not a 32-bit kernel boot. Initial missing
  lib32 linker failure and sandbox-native SIGSYS failure remain in logs.
- Acceptance-gate regression tests: 9 pass, including missing/skipped cases.
- Added C test passes kernel checkpatch (0 errors/warnings). Rust formatting and
  Git whitespace checks pass.
- Clean committed comparison repeated successfully: C `b46d927d0` and Rust
  `e87d0bc14` both pass 26/26 VM tests and the strict acceptance gate with identical
  configurations. Source differs only in Kbuild selection. Raw evidence and hashes
  are archived under `docs/evidence/int-sqrt/`; images/configs are in `artifacts/`.
- No userspace boot, module loading/export-runtime test, 32-bit kernel boot,
  other architecture/hardware test, performance benchmark, or full parity claim.

## Known failures and warnings

- Initial sandbox clone failed DNS; approved network retry succeeded.
- System install failed because sudo requires a password; local tools resolved
  the build blocker without changing host packages.
- Initial allnoconfig omitted the parent testing menu; build was deliberately
  interrupted, config corrected, and tests verified in the resolved config.
- Initial parser call required `--json=PATH` and absolute paths; corrected.
- Baseline and replacement print an upstream deprecated-workqueue warning from
  the upstream Rust spinlock test. Build logs also contain a jobserver warning.
  Keep these visible; neither is evidence of a clean warning-free system.

## Next actions

1. Supply a pinned independent build environment and verify on clean workers;
   repository-native tooling passed the renamed-worktree build/test workflow.
2. Establish project CI and bind expected implementation/source/configuration to
   tested images. Retain existing proof; do not accept passing C tests as Rust proof.
3. Establish the BRD C contract/workload baseline and review bio/non-MQ and page
   ownership design before the complete Rust driver implementation.
4. Incorporate prepared module/export/CRC checks into the declared Phase 1 matrix,
   followed by its lifecycle, failure, architecture and performance gates.
5. Continue broader subsystem migration after proving this coherent layer; most
   kernel implementation is still C. Do not substitute more disconnected helpers.

## Session log

### 2026-10-25 — Foundation and first replacement

Created local fork, project governance, progress ledger, roadmap and tool checks.
Installed missing tools locally after sudo was unavailable. Built and booted a
Rust-enabled Linux baseline. Added integer-square-root Rust translation and
separate parity tests; original upstream tests are unchanged. Initial C and Rust
VM comparisons pass. Aaron emphasized external scrutiny and authorized parallel
agents; independent reviews identified and corrected verification weaknesses.
32-bit host validation and clean committed C/Rust VM comparisons now pass.
Independent final source review found no additional build-selection or export
policy defect; module runtime/CRC and other architecture gates remain open.

### 2026-10-25 — Architecture decision accepted

Aaron explicitly agreed to the recommended direction and requested that it guide
the entire project. Added architecture decision 0001 and linked it from agent
instructions, roadmap, and contributor entry point. The decision distinguishes
Linux external compatibility from temporary C internal boundaries, permits
uncompiled upstream C references, and requires upstream integration plus Rust
parity verification before promotion. It preserves the full rewrite objective.
Module/export verification remains the next implementation gate; VM-only test
fixture preparation is in progress and has not yet established runtime results.

### 2026-10-25 — Public repository reserved; source publication held

Aaron created `rusix-org` and requested a public `rusix` repository and remote,
with no push until the first working layer and documentation/contribution
guidelines are ready. Created the empty public repository via GitHub CLI and
verified `isEmpty=true`, `visibility=PUBLIC`, and no default branch. Added it as
`origin` and configured `remote.pushDefault=origin`; Linux `upstream` is unchanged.
No commits, files, branches, tags, or releases have been published. Recorded the
hold in agent instructions and `docs/PUBLICATION.md`; contributor guidance is
drafted locally with repository-root entry points and an assistance record.
Fresh-checkout reproduction and first-layer module/fallback verification remain
open publication gates.

The VM-only module fixture is now implemented and independently source-reviewed:
the Rust init compiles as a static ELF with no interpreter/undefined symbols;
the C consumer checks 17 boundary cases and is deliberately non-GPL-compatible
to exercise the existing unrestricted export. It has not yet been built as a
module or executed in a VM. Keep that distinction explicit. GCD/LCM source
investigation identified a coherent next cluster and its architecture-dependent
dispatch constraint; recorded in `docs/MIGRATIONS.md`.

### 2026-10-25 — First-publication scope clarified and reproduced

Aaron explicitly accepted the existing kernel build and passing tests as a
sufficient first layer if documentation is ready; module/export/CRC and fallback
checks remain follow-up work rather than additional first-push prerequisites.
Independent doc review confirmed the recorded 26/26 C/Rust results and found one
contributor path error (`linux/scripts/checkpatch.pl`), now fixed.

Aaron approved a GitHub-recognized Linux fork. Deletion of the empty standalone
repository failed because the CLI token lacks `delete_repo`; it was retained as
`rusix-org/rusix-empty-placeholder`. Created `rusix-org/rusix` as a public fork
and verified parent `torvalds/linux`. Local remotes and commits are intact.

Reproduced the documented restoration/build/test workflow from an independent
clean worktree at `9047da37a`, using the same host tool installation: preflight,
3 native host tests, 9 gate tests, a fresh kernel build, and 26 VM tests all pass.
Raw evidence is archived in `docs/evidence/publication-check/`. Audited project
history and retained upstream license/README content. The local full-history
fetch was deliberately stopped after the GitHub fork preserved public ancestry;
the local repository remains shallow and passes Git connectivity checks.
First source push succeeded at `5520dd71ea4637bca9e82761463c0df53f3feb46`.
GitHub returned the exact branch SHA, verified the fork parent and public
visibility, and confirmed `rusix/main` as default plus the project's README.md.
The temporary verification worktree is removed after archiving its logs/results;
its image/config remain under `artifacts/publication-check/`. Broader rewrite
work remains incomplete. The unpublished module runner prepared in the outer
workspace still needs independent review and actual VM execution.

### 2026-10-25 — Published-code audit and Phase 1 definition

Aaron asked for the exact codebase state expected after Phase 1 of a well-funded
Linux/Rust fork. Audited the public revision with two independent read-only agents.
The square-root replacement and evidence are worth retaining, but are Phase 0:
60 Rust implementation lines plus nine C export-shim lines do not exercise
stateful kernel ownership, lifecycle, or useful userspace workloads.

Documented material gaps: parent-workspace mirroring, host-dependent tools, no
project CI, no ordinary userspace workload, selection/provenance not enforced by
the automated boot gate, narrow unsafe/architecture coverage, and an unexercised
upstream integration policy. No new defect invalidating the recorded arithmetic
results was identified. The proposed engineering slice is a complete Rust BRD
driver, with explicit bio/non-MQ/page-lifetime work and measurable exit gates.
`docs/PHASE1.md` defines the desired codebase; no BRD code or Phase 1 success is
claimed. This changes the work priority, not the full rewrite objective.

### 2026-10-25 — Repository-native tooling

Project sources now live directly in tracked `rusix/`; parent mirroring is retired.
Shared shell/Python path resolution supports renamed checkouts, Git
worktrees, and caller-relative output/tool overrides. Build outputs default to a
sibling directory. Installer reads the tracked package manifest. Documentation
and the host harness use repository-native paths. Shell path fixtures passed;
native (3) and i686 emulated (5) differential tests plus gate (9) and path (6)
regressions passed in a separate `relocation-check` worktree at `ed5bb5239`.
A fresh x86_64 kernel build succeeded and all 26 VM tests passed. Build evidence
confirms the source commit and clean state remained unchanged. Manual archive/
symbol inspection confirms the Rust square-root object remains selected.
Logs, configuration, hashes, and result manifest: `docs/evidence/repository-layout/`.
The upstream unused `Flags::from_raw` warning also appears in the earlier
publication build; it is not introduced by this tooling change.
The test reuses this host's tools via `RUSIX_TOOLS_ROOT`, not a clean-worker
installation. Independent review found no tooling regression and corrected the
checkout-path claim: Kbuild disallows spaces and colons.
This closes a tooling defect, not the remaining Phase 1 driver/environment gates.

### 2026-10-25 — BRD C baseline preparation

Inspected the unchanged pinned C RAM-disk driver and its Rust API dependencies.
Added an x86_64 SMP BRD build profile and explicit C source/object/symbol selection
evidence. A VM-only static userspace probe and strict runner are being reviewed
for geometry, sparse reads, page-boundary writes, partial-edge discard, competing
first insertion, and settled allocation accounting. Configuration preflight
retains all requested settings. Runtime results are pending; this is test
infrastructure for the C baseline, not a Rust driver or complete userspace system.
