# rusix progress

## Objective and current milestone

Fork Linux, rewrite its kernel in Rust, then migrate remaining OS components.
**Active; not complete.** M0 has a Rust-enabled x86_64 VM boot. M1 (integer square
root replacement) passes host and x86_64 VM comparisons from clean committed
revisions. Module/export testing and other architecture verification remain
outstanding. Review evidence: `docs/VERIFICATION.md`. Full scope: `docs/ROADMAP.md`.

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
- Actual Git repository: `linux/`; root `.git` is a protected placeholder.
  Root docs/scripts are canonical and synchronized into tracked `linux/rusix/`.
- Public GitHub repository `https://github.com/rusix-org/rusix` created at Aaron's
  request and verified public/empty. `origin` points there; `upstream` still points
  to Linux. **No source pushed:** publication held per `docs/PUBLICATION.md`.
- No host kernel installation or host module loading.
- Build with two jobs on disk under `builds/`; QEMU TCG uses one CPU/512 MiB.
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

1. Verify non-Rust fallback and module/export/CRC behavior using recorded builds.
2. Test 32-bit kernel targets and CFI/LTO configurations; add relevant workload
   and performance checks without weakening the preserved upstream tests.
3. Continue the subsystem inventory/migration; most kernel implementation is C.

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
