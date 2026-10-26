# Contributing to rusix

rusix aims for Linux-compatible external behavior and Rust-native internals.
Read [architecture decision 0001](docs/ARCHITECTURE.md), [AGENTS.md](AGENTS.md),
[PROGRESS.md](PROGRESS.md), and the [migration inventory](docs/MIGRATIONS.md)
before choosing work. Build toward complete Rust subsystems; preserve required
boundaries while replacing unnecessary C conventions inside those subsystems.

**Publication is currently held.** Aaron requested `rusix-org/rusix` as the public
repository, but no source push is permitted until the first working layer and
its documentation/contribution guidelines are ready. Repository creation alone
does not lift that hold. The clone instructions below apply after source is
published; they are not evidence that the remote already contains these files.

## Set up the workspace

The kernel Git repository must currently be named `linux/` inside a separate
workspace. Project scripts, configuration, and documents are tracked in its
`rusix/` directory, with working copies in the parent workspace. From a new,
empty directory on disk (not `/tmp`), after publication:

```sh
mkdir rusix-work
cd rusix-work
git clone --branch rusix/main https://github.com/rusix-org/rusix.git linux
git -C linux remote add upstream https://github.com/torvalds/linux.git
cp -a linux/rusix/AGENTS.md linux/rusix/README.md \
  linux/rusix/PROGRESS.md linux/rusix/CONTRIBUTING.md .
cp -a linux/rusix/docs linux/rusix/scripts linux/rusix/configs linux/rusix/tests .
git -C linux switch -c rusix/your-topic
```

These commands copy only project files; they do not copy `.git`, local tools, or
generated build trees. Do not repeat restoration over uncommitted workspace
edits. The initial development checkout was shallow; verify the pinned upstream
commit recorded in `PROGRESS.md` is available before running differential tests.
Never push to the Linux `upstream` remote.

All commands below run from the workspace root. Source changes go in `linux/`.
Edit the workspace copies of project documents/scripts/configuration/tests, then
run `bash scripts/sync-project-docs.sh` to update their tracked copies. Inspect
the resulting diff before committing. `builds/`, `.tools/`, and `logs/` belong
outside the kernel repository. Preserve other contributors' changes and use a
separate workspace/output directory for concurrent work.

## Toolchain and first checks

The currently exercised environment is x86_64 Linux, using LLVM and Rust, with
QEMU TCG for VM execution. Other hosts and distributions are not yet verified.
See [TOOLCHAIN.md](docs/TOOLCHAIN.md) and the pinned kernel's
`linux/Documentation/rust/quick-start.rst` for requirements. Expect GNU Make, a
host C compiler, the LLVM tools, Rust and `rust-src`, bindgen/libclang, flex,
bison, bc, cpio, Python, Perl, development libraries, and QEMU with firmware.
The scripts also use standard shell tools including `flock`, `timeout`, and
`sha256sum`.

Use suitable distribution packages or an explicitly configured local toolchain.
The `.tools` extraction recipe and `docs/packages.lock` were resolved against
Aaron's Arch/Omarchy host libraries; they are **not** a portable SDK or container
image. Do not install those packages blindly on another distribution. The local
installer requires Python 3.11 or newer. Keep toolchain changes project-local
where practical, and record exact versions rather than only minimum versions.

```sh
bash scripts/with-local-tools.sh bash scripts/check-toolchain.sh
python3 tests/test_kunit_gate.py
bash scripts/with-local-tools.sh python3 scripts/test-int-sqrt-host.py
```

The wrapper uses local tools if present and otherwise falls through to `PATH`.
Passing the preflight or host tests does not prove that a kernel builds or boots.
The optional i686 userspace checks require additional tools described in
`TOOLCHAIN.md`; they do not establish a 32-bit kernel boot.

After syncing and committing your source changes locally, build and boot:

```sh
bash scripts/build-kernel.sh review
bash scripts/boot-kunit.sh builds/review review-001
```

The recorded build requires a clean kernel Git tree and matching workspace/
tracked configuration and build script. A local work-in-progress commit makes
the exact candidate reproducible; it is not permission to publish it. The build
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
`linux/Documentation/process/license-rules.rst`; translation does not erase the
source's provenance. For kernel patches, read the existing sign-off procedure
and Developer's Certificate of Origin in
`linux/Documentation/process/submitting-patches.rst`. Use your own authorship
and `git commit -s` only when you can make that certification; do not invent
another person's sign-off or review approval.

Disclose substantial tool-generated content and tool-assisted findings in patch
descriptions, following `linux/Documentation/process/generated-content.rst` and
`linux/Documentation/process/coding-assistants.rst`. AI agents must not add
Signed-off-by tags. A human submitter must review the work and make any DCO
certification themselves. The initial project's assistance record is in
[ASSISTANCE.md](docs/ASSISTANCE.md).

Before requesting review, run relevant format/style checks and
`git -C linux diff --check`. For example, the current Rust helper uses:

```sh
rustfmt --check linux/lib/math/int_sqrt_rust.rs tests/int_sqrt_host.rs
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

Update `PROGRESS.md` and the affected migration record with evidence, not intent.
Do not commit binaries, tool installations, unrelated generated output, secrets,
or incidental local files. Preserve selected verification artifacts deliberately,
including their hashes and provenance, rather than uploading entire build trees.

After publication opens, propose focused work and submit small patches or PRs
against `rusix/main` through your own contribution branch/fork. Kernel-upstream
maintainers are not automatically rusix reviewers; do not send project-specific
work to them without an upstream submission plan. Human contributors remain
responsible for understanding, testing, and reviewing AI-assisted changes.
