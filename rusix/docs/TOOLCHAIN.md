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
