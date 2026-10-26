# Contributing to rusix

rusix aims for Linux-compatible external behavior and Rust-native internals.
Read [architecture decision 0001](docs/ARCHITECTURE.md), [AGENTS.md](AGENTS.md),
[PROGRESS.md](PROGRESS.md), and the [migration inventory](docs/MIGRATIONS.md)
before choosing work. Build toward complete Rust subsystems; preserve required
boundaries while replacing unnecessary C conventions inside those subsystems.

The initial public scope is the built and tested integer-square-root migration,
not a completed Rust kernel or production release. Aaron accepted that layer for
the first source push once documentation is ready; module/export and broader
architecture checks remain follow-up work. See [PUBLICATION.md](docs/PUBLICATION.md)
for the readiness record and [PROGRESS.md](PROGRESS.md) for current limitations.

## Set up the repository

Clone on disk, outside `/tmp`. Choose a checkout path without spaces or colons,
as required by upstream Kbuild; the directory need not be named `linux`:

```bash
git clone --branch rusix/main https://github.com/rusix-org/rusix.git rusix
cd rusix
git remote add upstream https://github.com/torvalds/linux.git
git switch -c rusix/your-topic
```

All commands below run from the checkout root. Project documents, scripts,
configuration, and tests are canonical tracked files under `rusix/`; edit them
directly. No copy or synchronization step is needed. The source-root `AGENTS.md`
points to `rusix/AGENTS.md`. Never push to the Linux `upstream` remote.

Builds, logs, temporary files, and extracted tools default to a sibling directory
named `<checkout-name>-out` (`../rusix-out` in this example). Set
`RUSIX_OUTPUT_ROOT` to override this location and `RUSIX_TOOLS_ROOT` to override
the extracted tools directory (default: `$RUSIX_OUTPUT_ROOT/.tools/root`).
Relative overrides resolve against your current directory. Keep generated output
outside the source checkout, on disk rather than `/tmp`.

Git worktrees are supported; each worktree gets its own default output directory.
Preserve other contributors' changes and do not share an output directory between
concurrent worktrees. The original development checkout was shallow; differential
tests require the pinned upstream commit recorded in `rusix/PROGRESS.md` to be
available locally.

## Toolchain and first checks

The currently exercised environment is x86_64 Linux, using LLVM and Rust, with
QEMU TCG for VM execution. Other hosts and distributions are not yet verified.
See [TOOLCHAIN.md](docs/TOOLCHAIN.md) and the pinned kernel's
`Documentation/rust/quick-start.rst` for requirements. Expect GNU Make, a
host C compiler, the LLVM tools, Rust and `rust-src`, bindgen/libclang, flex,
bison, bc, cpio, Python, Perl, development libraries, and QEMU with firmware.
The scripts also use standard shell tools including `flock`, `timeout`, and
`sha256sum`.

Use suitable distribution packages or an explicitly configured local toolchain.
The `.tools` extraction recipe and `rusix/docs/packages.lock` were resolved against
Aaron's Arch/Omarchy host libraries; they are **not** a portable SDK or container
image. Do not install those packages blindly on another distribution. The local
installer requires Python 3.11 or newer. Keep toolchain changes project-local
where practical, and record exact versions rather than only minimum versions.

```bash
bash rusix/scripts/with-local-tools.sh bash rusix/scripts/check-toolchain.sh
python3 rusix/tests/test_kunit_gate.py
bash rusix/scripts/with-local-tools.sh python3 rusix/scripts/test-int-sqrt-host.py
```

The wrapper uses local tools if present and otherwise falls through to `PATH`.
Passing the preflight or host tests does not prove that a kernel builds or boots.
The optional i686 userspace checks require additional tools described in
`rusix/docs/TOOLCHAIN.md`; they do not establish a 32-bit kernel boot.

After committing your source changes locally, build and boot:

```bash
bash rusix/scripts/build-kernel.sh review
source rusix/scripts/repo-paths.sh
bash rusix/scripts/boot-kunit.sh "$RUSIX_OUTPUT_ROOT/builds/review" review-001
```

The recorded build requires a clean kernel Git tree and checks that its commit
and clean state are unchanged after compilation. A local work-in-progress commit
makes the exact candidate reproducible; it is not permission to publish it. The build
uses two jobs. The VM uses one emulated CPU, 512 MiB RAM, no network, and a
180-second timeout. Builds generate fresh evidence directories; every boot needs
a new label such as `review-002`. Do not run two builds in the same output tree.

Keep failures, timeouts, and warnings in the evidence. Never load experimental
modules on the host, change its bootloader, or install the test kernel as part of
routine verification. Module/runtime, broader configuration, and architecture
checks remain explicitly scoped in `PROGRESS.md`; an unexecuted fixture or absent
CI job must not be presented as a passing check.

## Implement a migration

Before coding, record the upstream revision, reference files, callers,
configuration/build rules, current tests, and the intended subsystem outcome.
Specify ABI/layout, error and overflow behavior, ownership/lifetime, allocation,
locking, interrupt context, and architecture assumptions where applicable.

Keep the C boundary as small as necessary. Prefer safe Rust and existing kernel
Rust abstractions. Every unsafe operation needs a concrete safety invariant and
an explanation of how callers, ownership, and synchronization uphold it. Separate
mechanical translation, algorithm changes, and internal API redesign into
reviewable commits.

Preserve upstream tests unchanged for the pinned snapshot. Add independent
boundary, differential, concurrency, and failure-path coverage as needed; do not
weaken expectations or skip cases to make a rewrite pass. Compare C and Rust
under the same relevant configuration and tests, then prove the linked kernel
actually selects Rust. Include workload and performance evidence when the change
can affect those properties. Compilation, host tests, and VM tests prove different
things; state which were run and which remain unverified.

Retain upstream C source/history for comparison. Executing fallbacks and export
shims remain tracked migration work, with explicit removal criteria. Integrate
upstream changes on a separate `rusix/integration/*` branch and reestablish Rust
parity before promotion. A conflict-free merge does not prove semantic parity.

## Attribution, commits, and review

Keep the kernel's `COPYING`, `LICENSES/`, original attribution, and applicable
SPDX identifiers intact. Follow the existing kernel licensing rules in
`Documentation/process/license-rules.rst`; translation does not erase the
source's provenance. For kernel patches, read the existing sign-off procedure
and Developer's Certificate of Origin in
`Documentation/process/submitting-patches.rst`. Use your own authorship
and `git commit -s` only when you can make that certification; do not invent
another person's sign-off or review approval.

Disclose substantial tool-generated content and tool-assisted findings in patch
descriptions, following `Documentation/process/generated-content.rst` and
`Documentation/process/coding-assistants.rst`. AI agents must not add
Signed-off-by tags. A human submitter must review the work and make any DCO
certification themselves. The initial project's assistance record is in
[ASSISTANCE.md](docs/ASSISTANCE.md).

Before requesting review, run relevant format/style checks and
`git diff --check`. For example, the current Rust helper uses:

```bash
rustfmt --check lib/math/int_sqrt_rust.rs rusix/tests/int_sqrt_host.rs
```

Use the pinned kernel's coding guidelines and `scripts/checkpatch.pl` for changed
kernel code. Explain intentional warnings; do not suppress them merely to obtain
a clean report. Include these items in the patch or PR description:

- The existing behavior, resulting behavior, and preserved boundary contract.
- Exact base/candidate commits, resolved configuration, tools, commands, and
  relevant raw logs/results, including failures and limitations.
- Original tests retained, added coverage, actual link/runtime evidence, and
  architecture/workload/performance scope.
- Unsafe invariants, remaining C/FFI, upstream changes, and unfinished gates.

Update `rusix/PROGRESS.md` and the affected migration record with evidence, not intent.
Do not commit binaries, tool installations, unrelated generated output, secrets,
or incidental local files. Preserve selected verification artifacts deliberately,
including their hashes and provenance, rather than uploading entire build trees.

Propose focused work and submit small patches or PRs
against `rusix/main` through your own contribution branch/fork. Kernel-upstream
maintainers are not automatically rusix reviewers; do not send project-specific
work to them without an upstream submission plan. Human contributors remain
responsible for understanding, testing, and reviewing AI-assisted changes.
