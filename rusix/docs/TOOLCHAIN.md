# Build and test environment

The pinned container is being established in [`rusix/ci`](../ci/README.md).
Its Dockerfile pins a Debian amd64 base digest, dated package snapshot, Rust and
Rust source, LLVM and bindgen versions. The container/CI instructions own exact
pins and invocation. Until a successful run is recorded, treat the environment
as implemented but unverified; neither a Dockerfile nor a workflow means CI is green.
Independent-machine bit-identical builds are deferred under [ADR 0002](adr/0002.md).

## Recorded bootstrap host

Existing evidence uses x86_64 Arch/Omarchy: Rust 1.99.0 with `rust-src`,
Clang/LLD 23.1.3, bindgen 0.73.2 and QEMU 11.1.2. These results use the
`21a7f44fd076` engineering source, not the pending Linux 6.18.58 transition.
Revalidate toolchain requirements against each adopted source revision.

Host dependencies include a C compiler/static libc for the BRD probe, LLVM tools,
Rust, bindgen/libclang, Make, flex/bison, bc, Python 3.11+, Perl, development
libraries, QEMU/firmware, and shell tools such as `flock`, `timeout` and
`sha256sum`. Preflight checks executables, Rust source and `make rustavailable`;
it does not certify compilation or runtime behavior.

```bash
bash rusix/scripts/with-local-tools.sh bash rusix/scripts/check-toolchain.sh
```

The wrapper prepends an existing local tool tree and otherwise uses `PATH`.
Output/tool overrides and build commands are in [CONTRIBUTING.md](../CONTRIBUTING.md).
Use disk output outside source, initially two build jobs. VM acceleration is an
explicit recorded input; TCG remains the fallback when KVM is unavailable.

## Historical local package extraction

`packages.lock` records packages extracted to the bootstrap host's local tree
without hooks, sudo or system package-state changes. This recipe depends on
compatible Arch host libraries and is not a portable SDK:

```bash
python3 rusix/scripts/install-local-tools.py
```

The installer checks SHA-256 digests, caches under
`$RUSIX_OUTPUT_ROOT/.tools/packages` and extracts to `RUSIX_TOOLS_ROOT`.
It does not supply all host libraries or the Rust compiler. Avoid system-wide
changes or changing global Rust defaults merely to satisfy a project build.

## Optional 32-bit helper checks

Install the i686 Rust target and provide a 32-bit runtime. The historical package
lock includes lib32-glibc/lib32-gcc-libs; `qemu-i386-static` is an additional host
dependency. Explicit emulation avoids hiding a native-execution failure:

```bash
rustup target add i686-unknown-linux-gnu
bash rusix/scripts/with-local-tools.sh python3 rusix/scripts/test-int-sqrt-host.py \
  --32-bit --runner=qemu-i386
```

This is helper ABI coverage in userspace, not a 32-bit kernel boot or an expansion
of the declared kernel target. Preserve versions, resolved configuration, source
identity, exit codes and failure logs with every recorded build/run.
