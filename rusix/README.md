# rusix

rusix is an experimental Linux fork pursuing an incremental rewrite of the kernel
in Rust, followed by migration of the remaining operating-system components.
It is at **Phase 0: integration bootstrap**. It is not ready for installation on
physical hardware, and no claim of full feature parity is made.

The kernel repository uses branch `rusix/main`, based on upstream
commit `21a7f44fd0765fcc5194130b28767786eba1d1e7`. Linux's license files,
attribution, and source remain at the repository root. The public repository is
[rusix-org/rusix](https://github.com/rusix-org/rusix), configured as `origin`;
it is a GitHub fork of `torvalds/linux`, which remains the `upstream` remote.
The initial public scope is the built and tested integer-square-root layer,
with further module and architecture checks explicitly outstanding. See
[the publication record](docs/PUBLICATION.md) for scope and readiness evidence.
The original local checkout remains shallow; the GitHub fork retains Linux's
upstream ancestry. This limits local historical inspection, not the public lineage.

Start with [PROGRESS.md](PROGRESS.md) for current evidence and unfinished work,
[AGENTS.md](AGENTS.md) for contribution/agent requirements, and
[docs/ROADMAP.md](docs/ROADMAP.md) for the full scope. Migration contracts live
in [docs/MIGRATIONS.md](docs/MIGRATIONS.md).

[The Phase 0 audit](docs/AUDIT-PHASE0.md) assesses the code actually published.
[The Phase 1 contract](docs/PHASE1.md) defines the next target: a reproducible,
repository-native migration base plus a complete Rust RAM-backed block driver
exercised through ordinary Linux userspace. None of its full exit gates is yet
claimed complete.

The accepted direction is [architecture decision 0001](docs/ARCHITECTURE.md):
Linux-compatible externally, Rust-native internally, migrating incrementally
toward complete Rust subsystems. C compatibility boundaries are temporary;
upstream C may remain as uncompiled reference material.

## Repository and reproduction

Project documents, configuration, tests, and tools are maintained directly under
`rusix/` in this repository. Run these commands from the checkout root; no parent
workspace or copied files are required. The checkout may have any name, including
when using a Git worktree. Do not run an unreviewed kernel on your host.

Install/check tools following [docs/TOOLCHAIN.md](docs/TOOLCHAIN.md), then:

```bash
bash rusix/scripts/with-local-tools.sh bash rusix/scripts/check-toolchain.sh
bash rusix/scripts/with-local-tools.sh python3 rusix/scripts/test-int-sqrt-host.py
# Record source changes in a local commit before the recorded kernel build.
bash rusix/scripts/build-kernel.sh review
source rusix/scripts/repo-paths.sh
bash rusix/scripts/boot-kunit.sh "$RUSIX_OUTPUT_ROOT/builds/review" review-001
```

Output defaults to a sibling directory named `<checkout-name>-out`. Set
`RUSIX_OUTPUT_ROOT` to choose another on-disk location; set `RUSIX_TOOLS_ROOT`
to reuse an existing extracted tool tree (default: `$RUSIX_OUTPUT_ROOT/.tools/root`).
Relative overrides resolve against the caller's current directory. Keep output
outside the source checkout and use separate output directories for worktrees.

The build uses two jobs. The VM uses 512 MiB RAM, one emulated CPU, no network
interface, and a 180-second timeout. Build trees and logs go under `builds/` and
`logs/` within the output root. Commands here describe the verification workflow;
consult `PROGRESS.md` for completed checks and their scope.

## Review standard

Every replacement must preserve its public contract and run the original tests
unchanged. New tests supplement those tests and compare against the original C
implementation where practical. Report exact source/config/toolchain versions,
runtime results, retained C, and unverified behavior. A successful narrow test
does not establish an entire subsystem's compatibility or absence of defects.

Keep patches small enough to review. Avoid mixing translations with algorithm
changes. Follow upstream kernel coding, licensing, and safety conventions. Edit
the tracked files directly and review `git diff` before committing.
Do not commit local tools, generated build trees, or binaries.
