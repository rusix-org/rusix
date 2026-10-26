# VM-only integer-square-root module ABI probe

This fixture checks that a separately built C module can resolve the existing
`int_sqrt` export, calculate 17 native-width boundary cases, and unload normally.
It is test infrastructure, not a general init system. Never execute this `/init`
or load this module on the host.

`MODULE_LICENSE("BSD")` is intentional: pinned Linux treats it as non-GPL-
compatible, so modpost/loading exercises the original unrestricted export policy.
The kernel is expected to report a proprietary/out-of-tree-module taint.
Checkpatch reports one intentional unknown-license warning for this string.
Do not change it to a GPL-compatible tag merely to make the fixture pass.

## Build the Rust init

From the workspace root:

```sh
mkdir -p builds/module-fixture
rustc --edition=2021 --target x86_64-unknown-linux-gnu \
  -C opt-level=2 -C panic=abort -C relocation-model=static \
  -C link-arg=-nostartfiles -C link-arg=-static \
  -C link-arg=-Wl,--build-id=none \
  tests/module-smoke/init.rs -o builds/module-fixture/init
llvm-readelf -h -l builds/module-fixture/init
llvm-nm --undefined-only builds/module-fixture/init
```

The result must be an x86_64 static ELF executable with no interpreter and no
undefined symbols. `_start` aligns the process stack before entering Rust.
The init checks `getpid() == 1` before any module/reboot operation, but this guard
is not a substitute for a VM; never run it as host/container PID 1.

## Kernel and module requirements

Use a complete built kernel configured with `CONFIG_MODULES=y`,
`CONFIG_MODULE_UNLOAD=y`, `CONFIG_BLK_DEV_INITRD=y`, `CONFIG_BINFMT_ELF=y`, and a
working serial console. Build the module against that kernel's exact output tree
and `Module.symvers`; do not use `modules_prepare` as a substitute for a complete
build when verifying symbol versions. Enable module versioning in the kernel
when testing CRC compatibility. No force-load, ignored-vermagic, ignored-modversion,
or force-unload flags are supplied by the init.

Stage the `Makefile` and `int_sqrt_probe.c` in an output directory to keep generated
module files out of source control, then invoke Kbuild's external module target:

```sh
mkdir -p builds/module-fixture/module
cp tests/module-smoke/Makefile tests/module-smoke/int_sqrt_probe.c \
  builds/module-fixture/module/
bash scripts/with-local-tools.sh make -C linux \
  O="$PWD/builds/MODULE_KERNEL" M="$PWD/builds/module-fixture/module" LLVM=1 modules
```

Replace `MODULE_KERNEL` with the actual completed kernel output directory.
The parent verification runner packages a `newc` initramfs containing:

- `/init` executable, built as above;
- `/int_sqrt_probe.ko`, the uncompressed module;
- `/dev` directory and `/dev/console` character device, major 5 minor 1.

Boot in bounded QEMU with `rdinit=/init console=ttyS0`, one CPU, 512 MiB RAM,
no network, and `-no-reboot`. Do **not** use `kunit_shutdown=reboot`: that would
reboot before userspace runs. The parent runner must impose a timeout and reject
any `RUSIX_INIT_FAIL` or `RUSIX_MODULE_FAIL` marker, panic, or incomplete output.

Required success markers, in order:

```text
RUSIX_INIT_START
RUSIX_MODULE_CHECKS_PASS cases=17
RUSIX_INIT_LOAD_PASS
RUSIX_MODULE_UNLOAD_PASS
RUSIX_INIT_UNLOAD_PASS
RUSIX_MODULE_SMOKE_PASS
```

Successful QEMU exit alone is not sufficient: failure paths also request reboot.
If reboot returns, init reports failure and waits; the external VM timeout ends
the run. This proves only the selected x86_64 module boundary and tested values,
not cross-version module compatibility or other architectures.
