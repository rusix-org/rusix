# rusix progress

## Objective and current milestone

Fork Linux, rewrite its kernel in Rust, then migrate remaining OS components.
**Active; not complete.** M0 has a Rust-enabled x86_64 VM boot. M1 (integer square
root replacement) has passed initial host and VM checks; clean-commit evidence,
module/export testing and other architecture verification
are being completed or remain outstanding. Full scope: `docs/ROADMAP.md`.

## Baseline and workspace

- Upstream: `https://github.com/torvalds/linux.git`, remote `upstream`, commit
  `21a7f44fd0765fcc5194130b28767786eba1d1e7`; local branch `rusix/main`.
- Linux Makefile reports 7.3.0 during the 7.4 merge window. History is shallow.
- Actual Git repository: `linux/`; root `.git` is a protected placeholder.
  Root docs/scripts are canonical and synchronized into tracked `linux/rusix/`.
- No hosted rusix fork, host kernel installation, or host module loading.
- Build with two jobs on disk under `builds/`; QEMU TCG uses one CPU/512 MiB.
- Rust 1.99.0 (LLVM 23.1.1), Clang/LLD 23.1.3, bindgen 0.73.2, QEMU 11.1.2.
  Rust source and i686 target are installed; default toolchain is unchanged.
- Missing system packages were extracted into `.tools/root` with SHA-256 checks
  against the existing pacman database. See `docs/packages.lock` and TOOLCHAIN.md.

## Implemented

- Strong project instructions, full-scope roadmap, contributor entry point,
  migration contracts, local tool setup, configuration, build and VM scripts.
- Rust translation of native `int_sqrt` and the separate 32-bit `int_sqrt64` ABI;
  metadata-only C export shim. Rust selection was exercised experimentally;
  Kbuild is temporarily back on C for a clean committed comparison baseline.
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
- These first VM runs used an evolving tree; repeat from committed revisions is
  required for the final review evidence. Images/configs saved under `artifacts/`.
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

1. Commit reproducible C comparison baseline, build/boot it, then commit Rust
   selection and repeat with identical config; archive source IDs and raw evidence.
2. Verify non-Rust fallback and module/export behavior; test 32-bit kernel targets.
3. Continue the subsystem inventory/migration; most kernel implementation is C.

## Session log

### 2026-10-25 — Foundation and first replacement

Created local fork, project governance, progress ledger, roadmap and tool checks.
Installed missing tools locally after sudo was unavailable. Built and booted a
Rust-enabled Linux baseline. Added integer-square-root Rust translation and
separate parity tests; original upstream tests are unchanged. Initial C and Rust
VM comparisons pass. Aaron emphasized external scrutiny and authorized parallel
agents; independent reviews identified and corrected verification weaknesses.
32-bit host validation now passes; clean committed comparison is current work.
