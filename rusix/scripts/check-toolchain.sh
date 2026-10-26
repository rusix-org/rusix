#!/usr/bin/env bash
# Read-only checks; does not install tools or change the default toolchain.
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/repo-paths.sh"
missing=0
for tool in make gcc clang ld.lld llvm-ar llvm-nm llvm-objcopy llvm-objdump \
    llvm-readelf llvm-strip rustc cargo rustfmt bindgen flex bison bc cpio \
    perl python3 pkg-config pahole qemu-system-x86_64; do
    if ! command -v "$tool"; then
        printf 'MISSING: %s\n' "$tool" >&2
        missing=1
    fi
done
if command -v rustc >/dev/null; then
    rustc --version --verbose
    rust_source="$(rustc --print sysroot)/lib/rustlib/src/rust/library/core/src/lib.rs"
    if [[ ! -f "$rust_source" ]]; then
        printf 'MISSING: rust-src at %s\n' "$rust_source" >&2
        missing=1
    fi
fi
if [[ ! -r /dev/kvm || ! -w /dev/kvm ]]; then
    echo 'KVM unavailable: use QEMU software emulation (-accel tcg).'
fi
if ! make -C "$RUSIX_SOURCE" LLVM=1 rustavailable; then
    missing=1
fi
exit "$missing"
