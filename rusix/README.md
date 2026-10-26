# rusix

rusix is an experimental Linux fork pursuing an incremental rewrite of the kernel
in Rust, followed by migration of the remaining operating-system components.
It is at **Phase 0: integration bootstrap**. It is not ready for installation on
physical hardware, and no claim of full feature parity is made.

The actual kernel repository is `linux/`, branch `rusix/main`, based on upstream
commit `21a7f44fd0765fcc5194130b28767786eba1d1e7`. Linux's license files,
attribution, and source remain in that repository. The public repository is
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

## Workspace and reproduction

The root workspace's `.git` is a protected environment placeholder. Project
documents and scripts are therefore versioned under `linux/rusix/`, while their
canonical working copies live here. If you receive only the kernel repository,
place it at `WORKSPACE/linux/` and copy `linux/rusix/` contents into `WORKSPACE/`.
Do not run an unreviewed kernel on your host.

Install/check tools following [docs/TOOLCHAIN.md](docs/TOOLCHAIN.md), then:

```sh
bash scripts/with-local-tools.sh bash scripts/check-toolchain.sh
python3 scripts/test-int-sqrt-host.py
bash scripts/build-kernel.sh review
bash scripts/boot-kunit.sh builds/review review
```

The build uses two jobs and stores output on disk under `builds/`. The VM uses
512 MiB RAM, one emulated CPU, no network interface, and a 180-second timeout.
Logs and result JSON go under `logs/`. Commands in this section describe the
verification workflow; consult `PROGRESS.md` to see which have actually passed.

## Review standard

Every replacement must preserve its public contract and run the original tests
unchanged. New tests supplement those tests and compare against the original C
implementation where practical. Report exact source/config/toolchain versions,
runtime results, retained C, and unverified behavior. A successful narrow test
does not establish an entire subsystem's compatibility or absence of defects.

Keep patches small enough to review. Avoid mixing translations with algorithm
changes. Follow upstream kernel coding, licensing, and safety conventions. Before
committing, run `bash scripts/sync-project-docs.sh` and review the resulting diff
inside `linux/`. Do not commit local tools, generated build trees, or binaries.
