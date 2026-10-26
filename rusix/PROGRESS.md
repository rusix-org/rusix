# rusix progress

## Objective

Fork Linux, rewrite the kernel in Rust, then migrate the remaining operating
system components to Rust incrementally. **Active; not complete.**

## Current milestone

M0: obtain a pinned upstream foundation and establish a reproducible Rust-enabled
kernel build and isolated VM boot. See `docs/ROADMAP.md` for the full scope.

## Baseline and environment

- Workspace: `/home/aaron/code/rusix`; initially empty except protected tool
  directories. The root `.git` is a read-only placeholder, not a Git repository.
- Kernel checkout: `linux/`; download initiated from
  `https://github.com/torvalds/linux.git` using `--depth 1`. Checkout completed;
  upstream baseline `21a7f44fd0765fcc5194130b28767786eba1d1e7` (Makefile version
  7.3.0, during the 7.4 merge window). Branch `rusix/main`, remote `upstream`.
  History is shallow and must be deepened for older provenance investigations.
  This is a local fork; no hosted fork has been created.
- Host tools observed: rustc 1.99.0 (b940084d7 2026-09-28), clang 23.1.3,
  cargo, make, git, llvm-ar, flex, bison, cpio.
- Missing from PATH at initial inspection: bindgen, ld.lld, bc,
  qemu-system-x86_64. Rust-src is absent from installed rustup components.
- Initial resources: 260 GiB disk available; 5.4 GiB available RAM with swap
  already in use. Start builds at two jobs; keep build output off `/tmp`.

## Implemented

- Project `AGENTS.md`: continuity, provenance, migration/unsafe-code rules,
  verification gates, resource limits, and host isolation.
- Full-scope roadmap with explicit milestone acceptance requirements.
- Script to copy root governance documents into the kernel repository so they
  can be versioned despite the protected root `.git` placeholder.

## Verification and known failures

- `git status --short` at workspace root: failed, not a Git repository.
- Initial sandboxed clone: failed DNS resolution for github.com; retry with
  network escalation completed with exit 0. Checkout occupies about 2.1 GiB.
- `bash -n scripts/sync-project-docs.sh`: passed.
- In `linux/`, `make LLVM=1 rustavailable`: exit 2; upstream reports
  `Rust bindings generator 'bindgen' could not be found.` Other tool requirements
  remain unverified until this first failure is resolved.
- Upstream Rust quick-start documentation reviewed:
  https://docs.kernel.org/rust/quick-start.html . Source checkout and its own
  requirements remain authoritative for the selected revision.
- No kernel replacement, kernel build, or VM boot verified yet.
- Tool installation authorized by Aaron. `rustup component add rust-src`
  completed with exit 0 for the existing stable toolchain.
- `sudo -n pacman -S --needed --noconfirm rust-bindgen lld bc qemu-system-x86`
  failed with `sudo: a password is required`. Asked Aaron to run the package
  command locally; system packages remain pending, not installed.
- `/dev/kvm` absent in this environment; plan to use QEMU TCG if still absent
  at VM startup. LLVM utilities, GCC, Python, Perl and pkg-config are present.
- Initial governance documents committed in `linux/` as `68709bf59`.
- Both shell scripts pass `bash -n`. `bash scripts/check-toolchain.sh` exits 1,
  correctly reporting the four missing system tools and confirming Rust source
  is now present. Its upstream Rust check still fails on absent bindgen.

## Next executable actions

1. Resolve exact tool dependencies from pinned upstream requirements in a
   project-local setup where feasible. Save commands and results.
2. Build/boot the baseline in a bounded x86_64 VM, then select the first actual
   C replacement using source and caller evidence.
3. Synchronize and version project documents with implementation changes.

## Session log

### 2026-10-25 — Bootstrap

Inspected the empty workspace and host tool availability. Started upstream Linux
download, which completed successfully. Created the fork branch and recorded the
upstream SHA. Aaron requested strong project instructions and an evolving progress
document; created both and a full-scope roadmap. Bootstrap is in progress; no
rewrite success is claimed. The first Rust availability check identified missing
bindgen; no experimental code has been loaded onto the host.

Added a read-only toolchain preflight and installation notes. Installed rust-src;
remaining system tools require an interactive sudo invocation by Aaron. This is
a dependency-installation blocker, not evidence that kernel migration is complete.
