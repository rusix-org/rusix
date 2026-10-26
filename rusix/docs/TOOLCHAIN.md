# Build and test environment

[The pinned container guide](../ci/README.md) owns tool versions, package pins,
commands and local-only execution policy. It replaces reliance on laptop tools.
Executed LTS and historical engineering results are indexed in
[verification](VERIFICATION.md); current work is in [progress](../PROGRESS.md).

For an existing host setup, `check-toolchain.sh` checks executables, Rust source
and upstream availability, not build/runtime correctness. Commands and path
overrides are in [CONTRIBUTING.md](../CONTRIBUTING.md).

Historical Arch extraction remains available through
`python3 rusix/scripts/install-local-tools.py`, using [packages.lock](packages.lock).
It verifies hashes without package hooks or system changes, but depends on host
libraries and does not supply a compiler. This is not the portable environment;
do not change global Rust defaults merely to satisfy a project build.

Optional i686 helper tests need the Rust target, 32-bit runtime and
`qemu-i386-static` (not supplied by the initial container):

```bash
rustup target add i686-unknown-linux-gnu
bash rusix/scripts/with-local-tools.sh python3 rusix/scripts/test-int-sqrt-host.py --32-bit --runner=qemu-i386
```

This is userspace helper ABI coverage, not a 32-bit kernel boot. Keep its source,
tool versions, exit status and failure logs with the evidence.
