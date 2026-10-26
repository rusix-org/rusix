# Contributing to rusix

Read [ADR 0002](docs/adr/0002.md), [current progress](PROGRESS.md) and the relevant
[migration record](docs/MIGRATIONS.md). The ADR owns compatibility/divergence
policy; [AGENTS.md](AGENTS.md) owns execution and unsafe-code requirements.

## Checkout and tools

Use disk storage, outside `/tmp`, with no spaces or colons in the checkout path:

```bash
git clone --branch rusix/main https://github.com/rusix-org/rusix.git rusix
cd rusix
git remote add upstream https://github.com/torvalds/linux.git
git switch -c rusix/your-topic
```

Commands below run from this Git root. Edit tracked `rusix/` directly; no parent
copies or synchronization. Outputs default to sibling `<checkout-name>-out`.
`RUSIX_OUTPUT_ROOT` overrides output; `RUSIX_TOOLS_ROOT` overrides extracted
local tools (default `$RUSIX_OUTPUT_ROOT/.tools/root`). Relative overrides resolve
against the invoking directory. Worktrees need separate output directories.
Never push to the Linux `upstream` remote.

See [TOOLCHAIN.md](docs/TOOLCHAIN.md) for host requirements and
[the container instructions](ci/README.md) for the pinned environment under
validation. A container definition is not evidence of a successful hosted run.
Differential tests require the pinned source commit to be available locally;
shallow clones may need more history.

## Reproduce the current checks

```bash
bash rusix/scripts/with-local-tools.sh bash rusix/scripts/check-toolchain.sh
python3 rusix/tests/test_kunit_gate.py
python3 rusix/tests/test_repo_paths.py
python3 rusix/tests/test_brd_gate.py
bash rusix/scripts/with-local-tools.sh python3 rusix/scripts/test-int-sqrt-host.py
```

After recording source changes in a local commit, build and boot the KUnit profile:

```bash
bash rusix/scripts/build-kernel.sh review
source rusix/scripts/repo-paths.sh
bash rusix/scripts/boot-kunit.sh "$RUSIX_OUTPUT_ROOT/builds/review" review-001
```

For the C BRD contract, build its profile and pass the exact evidence directory
printed by the build (replace `REPLACE` below):

```bash
bash rusix/scripts/build-kernel.sh --profile brd review-brd
python3 rusix/scripts/test-brd-vm.py "$RUSIX_OUTPUT_ROOT/builds/review-brd" brd-001 \
  --build-evidence "$RUSIX_OUTPUT_ROOT/logs/review-brd-build.REPLACE"
```

Recorded builds require clean committed source. Each build reserves fresh logs;
each VM attempt needs a new label. Builds use two jobs; VMs are bounded to
512 MiB and 180 seconds, with no network and one CPU for KUnit or two for BRD.
The BRD runner compiles a static guest probe; never execute it on the host.
Do not load experimental modules or alter the host bootloader/kernel.

Current results belong to the engineering baseline, not the pending 6.18.58
transition. Preserve failed results and warnings. Preflight, host tests and VM
checks establish different scopes; consult the evidence before claiming parity.

## Migration and review

Before implementation, inspect the reference C, callers, Kconfig/Kbuild and tests.
Specify behavior and ownership/context assumptions; check existing upstream Rust
APIs and mailing-list proposals before introducing new abstractions. Separate
translation, intentional behavior changes and redesign. Preserve baseline tests,
add meaningful missing coverage, run paired C/Rust checks and prove Rust selection.
Record retained C and adapter removal criteria. Apply the ADR's selected-fix and
divergence rules rather than automatic whole-tree rebases.

Keep patches focused and submit against `rusix/main`. A review description needs:

- The concrete behavior change and preserved contract.
- Exact source/config/tool identities, commands, raw results and limitations.
- Unsafe invariants, selected implementation, retained C and unfinished gates.

Update `PROGRESS.md` and the migration record. Do not commit installed tools,
build trees, binaries or incidental local files; archive selected evidence with
hashes. Run relevant formatting/style checks and `git diff --check`. For the
current Rust helper:

```bash
rustfmt --check lib/math/int_sqrt_rust.rs rusix/tests/int_sqrt_host.rs
```

Use `scripts/checkpatch.pl` for changed kernel code. Explain intentional warnings.
Upstream maintainers are not automatically rusix reviewers; upstream submission
requires its own relevant, reviewable patch plan.

## Licensing and authorship

Preserve `COPYING`, `LICENSES/`, SPDX identifiers and original attribution. Follow
`Documentation/process/license-rules.rst` and `submitting-patches.rst`.
Human contributors use their own authorship and `git commit -s` only when they
can certify the DCO; never invent another person's approval or sign-off.

Disclose substantial generated content and tool-assisted findings under
`Documentation/process/generated-content.rst` and `coding-assistants.rst`.
Agents must not add human Signed-off-by certification. Human submitters remain
responsible for understanding, reviewing and testing assisted work; see
[ASSISTANCE.md](docs/ASSISTANCE.md).
