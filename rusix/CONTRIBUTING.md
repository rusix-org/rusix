# Contributing to rusix

Read [ADR 0002](docs/adr/0002.md), [progress](PROGRESS.md) and the relevant
[migration record](docs/MIGRATIONS.md). [AGENTS.md](AGENTS.md) defines implementation,
unsafe-code and verification discipline; follow it for assisted contributions.

## Checkout and verification

Use disk storage outside `/tmp`; Kbuild forbids spaces and colons in source paths:

```bash
git clone --branch rusix/main https://github.com/rusix-org/rusix.git rusix
cd rusix
git remote add upstream https://github.com/torvalds/linux.git
git switch -c rusix/your-topic
```

Run commands from this Git root and edit tracked `rusix/` directly. Never push to
`upstream`. Outputs default to sibling `<checkout-name>-out`; `RUSIX_OUTPUT_ROOT`
overrides this, and `RUSIX_TOOLS_ROOT` overrides `$RUSIX_OUTPUT_ROOT/.tools/root`.
Relative overrides use the invoking directory. Give each worktree separate output.
Differential checks need the pinned reference commit locally, even in shallow clones.

Use [the pinned container](ci/README.md) for kernel build, VM and measurement
profiles; that guide owns exact commands, pins and the local-only spending policy.
[TOOLCHAIN.md](docs/TOOLCHAIN.md) covers existing host setups. Quick host checks:

```bash
bash rusix/scripts/with-local-tools.sh bash rusix/scripts/check-toolchain.sh
python3 -m unittest discover -s rusix/tests -p 'test_*.py'
bash rusix/scripts/with-local-tools.sh python3 rusix/scripts/test-int-sqrt-host.py
rustfmt --check lib/math/int_sqrt_rust.rs rusix/tests/int_sqrt_host.rs
git diff --check
```

Recorded builds require clean committed source; use fresh outputs and VM labels,
retaining failed attempts. Never run guest probes or load experimental modules on
the host. The [BRD fixture](tests/brd-contract/README.md) documents its exact scope.
Current engineering-baseline results do not verify the pending 6.18.58 transition.

## Review

Submit focused patches against `rusix/main`, separating translation, behavior
changes and redesign. Apply ADR 0002's selected-fix/divergence rules. Describe:

- The concrete behavior change, preserved contract and unsafe invariants.
- Source/config/tool identities, commands, raw evidence and limitations.
- Selected implementation, remaining C/adapters and unfinished gates.

Update progress and the migration record. Commit selected evidence with hashes,
not installed tools, binaries or build trees. Use kernel formatting guidance and
`scripts/checkpatch.pl` for changed kernel code; explain intentional warnings.
Upstream submission needs its own relevant patch plan and review.

## Licensing and authorship

Preserve `COPYING`, `LICENSES/`, SPDX notices and attribution. Follow Git-root
`Documentation/process/license-rules.rst` and `submitting-patches.rst`. Humans
may use `git commit -s` only when able to certify the DCO; never invent sign-offs.

Disclose substantial generated content and tool-assisted findings under
`Documentation/process/generated-content.rst` and `coding-assistants.rst`.
Agents must not add human Signed-off-by certification. Human submitters remain
responsible for reviewing and testing assisted work; see [ASSISTANCE.md](docs/ASSISTANCE.md).
