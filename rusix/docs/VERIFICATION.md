# First migration verification record — 2026-10-25

This record establishes a narrow integer-square-root migration milestone. It
does not establish full kernel compatibility, a completed rewrite, or absence
of defects. The original upstream suite and public header are unchanged.

## Committed comparison

| Role | Source commit | Linked implementation | VM result |
| --- | --- | --- | --- |
| C comparison | `b46d927d08a08ace97e110b71a757e4b13a251ff` | upstream `int_sqrt.c` | 26/26 pass |
| Rust replacement | `e87d0bc14604aabbf561ac1e9e32d1ca29406006` | `int_sqrt_rust.rs` | 26/26 pass |

Both recorded builds began with a clean source tree and used the same resolved
configuration, byte-for-byte. Each executed 21 original square-root inputs,
three added compatibility cases (each covers many inputs), and two existing Rust
kernel tests. The acceptance gate requires all expected square-root cases, rejects
skips/failures/omissions/duplicates, and has nine passing regression tests.

The only source difference between these two commits is the seven-line Kbuild
selection: CONFIG_RUST selects the Rust object and C export-metadata shim, while
non-Rust configurations retain the original C implementation.

These are historical commands for those revisions; use
[the contributor guide](../CONTRIBUTING.md) for current repository-native commands.

For each source revision, with its workspace copies restored from `linux/rusix/`,
the commands were:

```sh
bash scripts/build-kernel.sh baseline
bash scripts/boot-kunit.sh builds/baseline c-reviewed     # C revision only
bash scripts/boot-kunit.sh builds/baseline rust-reviewed  # Rust revision only
```

Run only the boot command appropriate to the selected revision. Use fresh labels
when repeating; the script rejects reused labels. The build directory is reusable
but must not be used concurrently. A fresh output directory can instead be named
in both commands. The minimal configuration is a test kernel, not a distribution
configuration. Builds include timestamps and counters: this demonstrates
repeatable behavior, not byte-identical reproducible binaries.

Raw build/configuration/toolchain records, full serial logs, JSON results,
commands, hashes, and exit statuses are committed under
[`evidence/int-sqrt/`](evidence/int-sqrt/manifest.json). Original local kernel
images are under `artifacts/c-reviewed/` and `artifacts/rust-reviewed/`; binaries
are not committed. The manifest records the observed hashes, not authenticity
signatures or independent third-party certification.

## Additional checks

- Native x86_64 host tests pass three cases covering 2,012,482 inputs against
  actual pinned upstream C and independent square bounds, with Rust overflow
  checks enabled.
- i686 host ABI tests pass five cases, including the distinct int_sqrt64 ABI,
  through explicitly selected qemu-i386 userspace emulation. Initial linker and
  sandbox-native execution failures are preserved alongside successful evidence.
  The local lib32 runtime resolves the linker failure; explicit emulation avoids
  the sandbox's rejection of 32-bit syscalls.
- The linked math archive contains the Rust implementation and no original C
  implementation object. vmlinux has one int_sqrt definition. The Rust object has
  no undefined symbols, including no panic/runtime-helper dependencies.
- The original C source, upstream test file, and include/linux/math.h compare
  unchanged against upstream `21a7f44fd0765fcc5194130b28767786eba1d1e7`.
- Independent agents reviewed ABI/arithmetic and build/export selection, and
  independently reviewed the verification tooling. Findings were addressed;
  these are AI-assisted reviews, not outside-maintainer approval.

## Warnings and unfinished verification

Both kernels emit the existing Rust spinlock test's deprecated-workqueue warning.
Build logs contain a jobserver warning. These are preserved, not suppressed.
The minimal kernel does not boot a userspace environment. No performance parity
claim, 32-bit kernel boot, other hardware validation, or module loading test has
been completed. Module export/CRC behavior, CFI/LTO configurations, and the
non-Rust selection need further verification before broad deployment claims.

Retained C includes the original fallback, metadata export shim, test oracle,
and almost the entire rest of Linux. Full rewrite completion remains far away.
