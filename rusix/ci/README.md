# Pinned x86_64 build and verification container

**Run tests locally for now.** The GitHub workflow is disabled and manual-only to
limit credit use. Revisit hosted execution when Phase 1a is ready for outside
review; enabling or dispatching it requires an explicit request. Do not restore
push/PR triggers as routine maintenance. Existing hosted results are historical
evidence, not authorization for more runs.

This environment supplies its own compilers, Rust source, binding generator,
static C runtime, QEMU, and build tools. It does not use the original laptop's
Arch package extraction or host Rust installation. Docker is the host dependency.

From a clean committed checkout, build the image and run each profile into a
fresh output directory outside the source tree:

```bash
docker build --platform linux/amd64 -t rusix-toolchain:trixie-20261025 rusix/ci
bash rusix/ci/run-container.sh rusix-toolchain:trixie-20261025 ../rusix-ci-kunit kunit
bash rusix/ci/run-container.sh rusix-toolchain:trixie-20261025 ../rusix-ci-brd brd
bash rusix/ci/run-container.sh rusix-toolchain:trixie-20261025 ../rusix-ci-server server
```

The wrapper selects KVM only if `/dev/kvm` is accessible, otherwise TCG. Set
`RUSIX_QEMU_ACCEL=kvm` or `RUSIX_QEMU_ACCEL=tcg` to require one mode. A requested
KVM run fails if unavailable; a runtime KVM failure does not retry under TCG.
The selected mode is recorded. KVM uses the portable `qemu64` model; TCG uses
`max`. Host CPU passthrough exposed inconsistent speculation-control features
on the initial AMD/KVM setup. KVM exposes only that device to the container;
no privileged container or host kernel/module changes are required. The container
runs as the caller, with a read-only source mount, no network, two CPU slots, and
a 5 GiB memory limit. All generated output is written to the supplied disk path.
The wrapper also mounts external Git metadata read-only for linked worktrees.

Each profile runs toolchain preflight, native C/Rust differential checks, and
all `rusix/tests/test_*.py` regressions before building one kernel:

| Profile | Checks using that kernel |
| --- | --- |
| `kunit` | 21 upstream square-root cases and three compatibility cases |
| `brd` / `brd-rust` | Six block contract cases, six parameter/on-demand boots and five partition cases against C / Rust BRD |
| `brd-ext4-c` / `brd-ext4-rust` | The same block and parameter checks, plus six ordinary-userspace ext4 cases; requires the [fixture image](../tests/brd-ext4/README.md) with e2fsprogs |
| `brd-kunit` | Nine required BRD ownership/policy cases, then a separate boot requiring the current [completion contract inventory](../experiments/completion/README.md) |
| `completion-c` / `completion-rust` | The same BRD/core tests, paired with original C / opt-in Rust completion entry points; archive/object/symbol evidence verifies selection |
| `core-ext4-c` / `core-ext4-rust` | Ordinary ext4 userspace, block, parameter and partition suite with Rust BRD in both; only C / Rust completion selection differs. Requires the fixture image above and explicit core symbol proof. |
| `server` | Build and linked-ELF language measurement; archives vmlinux, map, config and JSON, without runtime or filesystem verification |

Choose any listed profile as the final `run-container.sh` argument, with a fresh
output directory. The wrapper records the image ID; the ext4 runner also binds
its staged ordinary utilities to that image. The i686 host test is separate
because this container does not include its target runtime.

VM runners explicitly select QEMU `q35`. BRD configurations enable ACPI and PCI
support for firmware enumeration and two CPUs. `CONFIG_BLOCK_LEGACY_AUTOLOAD=y`
enables the pinned block layer's registered-major probe path: opening an absent
RAM disk must invoke BRD's callback even though BRD itself is builtin. It is
required for the on-demand contract, not evidence of tested module loading.
See [PROGRESS.md](../PROGRESS.md) for verified configurations and runs. CPU-dependency and ACPI diagnostics
reject results rather than being suppressed.

## Pins and provenance

- Base: official Debian trixie amd64 manifest
  `sha256:4876fdea29cac1a33a3195f1eb1952feb1fca7dd6dd00be3e2f1879cf20d34d2`,
  published 2026-10-20. The tag is descriptive; Docker resolves the digest.
- All packages come from the signed Debian and Debian-security snapshots at
  `20261025T000000Z`. [Debian's snapshot service](https://snapshot.debian.org/)
  retains dated package archives. APT signature verification remains enabled;
  only expiration checking is disabled for these fixed historical snapshots.
- [packages.lock](packages.lock) lists every installed package version and
  architecture. The image build rejects a different resolved package inventory.
- Rust and rust-src: `1.85.1+dfsg1-1+deb13u1`; LLVM/Clang/LLD: `19.1.7`;
  bindgen: `0.71.1`; GCC: `14.2.0`; QEMU: `10.0.13`.
  The kernel's availability check remains required. Debian supplies the
  [matching Rust sources](https://packages.debian.org/trixie/rust-src) and
  [bindgen package](https://packages.debian.org/trixie/bindgen).
- GitHub Actions use verified official full commit references for checkout and
  artifact upload, with a read-only repository token and no persisted credentials.
  See [GitHub's workflow security guidance](https://docs.github.com/en/actions/reference/security/secure-use).

`run.sh` fixes the build user, host, version counter, and timestamp derived from
that source commit; container mount paths are `/src` and `/out`. This controls
several reproducibility inputs, but does not yet prove matching kernel/initramfs
hashes on two independent clean workers. Container image construction itself is
not claimed to produce a byte-identical image ID.

`logs/` records the image ID, package inventory, compiler versions, source commit,
configuration, selected accelerator, exact VM command where applicable, hashes
and exit codes.
Failed attempts retain their evidence and reserve their output directory. The
workflow uploads logs and relevant kernel/initramfs binaries on success or failure
with 30-day retention. Durable milestone summaries remain necessary after expiry.

To update the environment, deliberately change the base digest and snapshot,
resolve/review the new package inventory, and revalidate affected profiles locally. Do not bypass
an inventory or tool-version assertion to obtain a passing build.

The disabled hosted definition has one explicitly selected profile per manual
dispatch, defaulting to `brd-rust`; there is no automatic multi-job matrix.
Enabling or dispatching it still requires the explicit request described above.
