# Bootstrap toolchain

On Aaron's Arch/Omarchy laptop, existing Clang/LLVM and rustup provide most tools.
Install missing packages without changing the host kernel or Rust defaults:

```sh
sudo pacman -S --needed rust-bindgen lld bc qemu-system-x86
rustup component add rust-src
bash scripts/check-toolchain.sh
```

Do not use `pacman -Sy` alone to refresh package metadata: avoid a partial system
upgrade. If packages cannot be downloaded or dependency versions conflict,
investigate before making broader system changes.

The pinned Linux source requires bindgen >= 0.71.1, LLVM >= 17.0.1 and, for
x86_64, rustc >= 1.85.0 (`linux/scripts/min-tool-version.sh`). Those minima alone
do not prove compatibility; `make LLVM=1 rustavailable`, a complete kernel build,
and runtime verification are separate gates.

`check-toolchain.sh` reports missing executable dependencies and Rust source,
then runs upstream's availability check. It does not prove a kernel builds or
boots. Capture its output with `set -o pipefail` if piping to `tee`.

Initial rustc: 1.99.0 (b940084d7 2026-09-28); Clang: 23.1.3. Preserve exact
versions with build evidence. Keep build outputs on disk under this workspace,
use `O=` for kernel output, and start at `-j2`. KVM was not exposed in the initial
environment; QEMU's TCG software emulator is the fallback.

The top-level documents/scripts are canonical. Run
`bash scripts/sync-project-docs.sh` to update tracked copies under `linux/rusix/`.
If restoring from the kernel repository alone, copy its `rusix/` contents to the
parent workspace containing `linux/` before continuing work.

## Local installation without sudo

The system install required an interactive password. The missing packages and
their dependencies were instead extracted under `.tools/root`, using the
existing system package database's SHA-256 digests. No package hooks were run and
no system package state was changed. `docs/packages.lock` records the resolved
names, versions, hashes, and download URLs. This depends on the host's existing
libraries and is not a portable hermetic toolchain.

To reproduce on this host:

```sh
mkdir -p .tools
cp docs/packages.lock .tools/packages.lock
python3 scripts/install-local-tools.py
bash scripts/with-local-tools.sh bash scripts/check-toolchain.sh
```

Run build commands through `bash scripts/with-local-tools.sh COMMAND ...`.
For local QEMU, pass `-L "$PWD/.tools/root/usr/share/qemu"` so firmware is found.
Preflight and `qemu-system-x86_64 --version` both succeeded after extraction;
the upstream Rust availability check reports `Rust is available!`.

For the 32-bit helper ABI checks, install the i686 Rust target and provide a
32-bit userspace runtime. The pinned local package manifest includes lib32-glibc
and lib32-gcc-libs; the harness uses their local startup objects and loader.
`qemu-i386-static` was already installed on this host. Run explicitly:

```sh
rustup target add i686-unknown-linux-gnu
bash scripts/with-local-tools.sh python3 scripts/test-int-sqrt-host.py --32-bit --runner=qemu-i386
```

This is 32-bit userspace emulation, not kernel/architecture validation. The native
mode also runs on hosts permitting 32-bit syscalls; this sandbox rejects them.
No automatic fallback hides native execution failures.

Recorded kernel builds require a clean committed `linux/` tree and synchronized
configuration/script copies. Each build creates a fresh `logs/NAME-build.*`
directory. Each VM boot requires an unused evidence label. The strict JSON gate
requires all 21 original square-root cases and all three x86_64 compatibility
cases to pass; `--baseline` permits the original kernel without the added suite.
