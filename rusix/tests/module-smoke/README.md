# VM-only integer-square-root module ABI probe

**Prepared fixture; kernel/module runtime verification remains pending.** It
checks a separately built C module resolves `int_sqrt`, passes 17 native-width
cases and unloads. Never run `/init` or load the module on the host/container.
The PID 1 guard is insufficient protection outside an isolated VM.

`MODULE_LICENSE("BSD")` intentionally exercises the unrestricted export: Linux
treats this tag as non-GPL-compatible, causing proprietary/out-of-tree taint and
one intentional checkpatch license warning. Do not change it to obtain a pass.

From the checkout root, build and inspect the static init without executing it:

```sh
source rusix/scripts/repo-paths.sh
mkdir -p "$RUSIX_OUTPUT_ROOT/builds/module-fixture"
rustc --edition=2021 --target x86_64-unknown-linux-gnu \
  -C opt-level=2 -C panic=abort -C relocation-model=static \
  -C link-arg=-nostartfiles -C link-arg=-static \
  -C link-arg=-Wl,--build-id=none \
  rusix/tests/module-smoke/init.rs -o "$RUSIX_OUTPUT_ROOT/builds/module-fixture/init"
llvm-readelf -h -l "$RUSIX_OUTPUT_ROOT/builds/module-fixture/init"
llvm-nm --undefined-only "$RUSIX_OUTPUT_ROOT/builds/module-fixture/init"
```

Require x86_64 ELF, no interpreter or undefined symbols. Use a completely built
kernel with `MODULES=y`, `MODULE_UNLOAD=y`, `BLK_DEV_INITRD=y`, `BINFMT_ELF=y` and
serial console; enable module versioning for CRC testing. Build against its exact
output and `Module.symvers`, not just `modules_prepare`. The init supplies no
force-load, ignored-version or force-unload flags.

```sh
mkdir -p "$RUSIX_OUTPUT_ROOT/builds/module-fixture/module"
cp rusix/tests/module-smoke/Makefile rusix/tests/module-smoke/int_sqrt_probe.c \
  "$RUSIX_OUTPUT_ROOT/builds/module-fixture/module/"
bash rusix/scripts/with-local-tools.sh make -C "$RUSIX_SOURCE" \
  O="$RUSIX_OUTPUT_ROOT/builds/MODULE_KERNEL" M="$RUSIX_OUTPUT_ROOT/builds/module-fixture/module" LLVM=1 modules
```

Replace `MODULE_KERNEL` with the completed output directory. The pending runner
must package a `newc` initramfs with executable `/init`, uncompressed
`/int_sqrt_probe.ko`, `/dev` and `/dev/console` (character 5:1). Boot bounded QEMU
with `rdinit=/init console=ttyS0`, one CPU, 512 MiB, no network and `-no-reboot`.
Omit `kunit_shutdown=reboot`, which would bypass userspace. Reject timeout,
panic, any `RUSIX_INIT_FAIL`/`RUSIX_MODULE_FAIL`, or missing/out-of-order markers:

```text
RUSIX_INIT_START
RUSIX_MODULE_CHECKS_PASS cases=17
RUSIX_INIT_LOAD_PASS
RUSIX_MODULE_UNLOAD_PASS
RUSIX_INIT_UNLOAD_PASS
RUSIX_MODULE_SMOKE_PASS
```

VM exit alone is insufficient: failure paths also reboot. Scope is the selected
x86_64 export boundary and values, not cross-version module ABI or other hardware.
