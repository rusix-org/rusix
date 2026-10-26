# Bootstrap toolchain

On Aaron's Arch/Omarchy laptop, existing Clang/LLVM and rustup provide most tools.
Install missing packages without changing the host kernel or Rust defaults:

```sh
sudo pacman -S --needed rust-bindgen lld bc qemu-system-x86
rustup component add rust-src
bash rusix/scripts/check-toolchain.sh
```

Do not use `pacman -Sy` alone to refresh package metadata: avoid a partial system
upgrade. If packages cannot be downloaded or dependency versions conflict,
investigate before making broader system changes.

The pinned Linux source requires bindgen >= 0.71.1, LLVM >= 17.0.1 and, for
x86_64, rustc >= 1.85.0 (`scripts/min-tool-version.sh`). Those minima alone
do not prove compatibility; `make LLVM=1 rustavailable`, a complete kernel build,
and runtime verification are separate gates.

`check-toolchain.sh` reports missing executable dependencies and Rust source,
then runs upstream's availability check. It does not prove a kernel builds or
boots. Capture its output with `set -o pipefail` if piping to `tee`.

Initial rustc: 1.99.0 (b940084d7 2026-09-28); Clang: 23.1.3. Preserve exact
versions with build evidence. Keep build outputs on disk outside the source tree,
use `O=` for kernel output, and start at `-j2`. KVM was not exposed in the initial
environment; QEMU's TCG software emulator is the fallback.

Run commands from the repository root. Project documents and scripts under
`rusix/` are canonical; no parent workspace or synchronization step is required.
Output defaults to the sibling `<checkout-name>-out` directory. To use another
on-disk location, export `RUSIX_OUTPUT_ROOT`; to reuse an extracted tool tree,
export `RUSIX_TOOLS_ROOT` (default: `$RUSIX_OUTPUT_ROOT/.tools/root`). Relative
overrides resolve against the caller's current directory.

## Local installation without sudo

The system install required an interactive password. The missing packages and
their dependencies were instead extracted into a local tool tree, using the
existing system package database's SHA-256 digests. No package hooks were run and
no system package state was changed. `rusix/docs/packages.lock` records the resolved
names, versions, hashes, and download URLs. This depends on the host's existing
libraries and is not a portable hermetic toolchain.

The installer reads the tracked manifest directly, caches packages under
`$RUSIX_OUTPUT_ROOT/.tools/packages`, and extracts to `RUSIX_TOOLS_ROOT`. It does
not provide the host compiler, rustup toolchain, or all host libraries.

To reproduce on a compatible Arch host:

```sh
python3 rusix/scripts/install-local-tools.py
bash rusix/scripts/with-local-tools.sh bash rusix/scripts/check-toolchain.sh
```

Run build commands through `bash rusix/scripts/with-local-tools.sh COMMAND ...`.
The boot script supplies the firmware directory from `RUSIX_TOOLS_ROOT` when
local firmware is present; otherwise QEMU uses its system defaults.
Preflight and `qemu-system-x86_64 --version` both succeeded after extraction;
the upstream Rust availability check reports `Rust is available!`.

For the 32-bit helper ABI checks, install the i686 Rust target and provide a
32-bit userspace runtime. The pinned local package manifest includes lib32-glibc
and lib32-gcc-libs; the harness uses their local startup objects and loader.
`qemu-i386-static` was already installed on this host. Run explicitly:

```sh
rustup target add i686-unknown-linux-gnu
bash rusix/scripts/with-local-tools.sh python3 rusix/scripts/test-int-sqrt-host.py --32-bit --runner=qemu-i386
```

This is 32-bit userspace emulation, not kernel/architecture validation. The native
mode also runs on hosts permitting 32-bit syscalls; this sandbox rejects them.
No automatic fallback hides native execution failures.

Recorded kernel builds require a clean committed source tree. Each build creates
a fresh `logs/NAME-build.*` directory under `RUSIX_OUTPUT_ROOT`. Each VM boot
requires an unused evidence label. The strict JSON gate
requires all 21 original square-root cases and all three x86_64 compatibility
cases to pass; `--baseline` permits the original kernel without the added suite.
