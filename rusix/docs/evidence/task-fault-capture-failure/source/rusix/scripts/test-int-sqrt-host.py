#!/usr/bin/env python3
"""Differential host checks against actual pinned upstream C source."""
import argparse
import subprocess

from rusix_paths import resolve_paths

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--32-bit", dest="target32", action="store_true",
                    help="Build/run i686 tests, including the separate int_sqrt64 ABI")
parser.add_argument("--runner", choices=("native", "qemu-i386"), default="native",
                    help="Explicit execution mode; qemu-i386 requires --32-bit")
args = parser.parse_args()
if args.runner == "qemu-i386" and not args.target32:
    parser.error("--runner=qemu-i386 requires --32-bit")

paths = resolve_paths()
out = paths.output / "builds" / ("int-sqrt-host-i686" if args.target32 else "int-sqrt-host")
out.mkdir(parents=True, exist_ok=True)
baseline = "2926d88bb7fc4608fd942453d929c39e4e5ec006"
source = subprocess.check_output(
    ["git", "-C", str(paths.source), "show", f"{baseline}:lib/math/int_sqrt.c"],
    text=True,
)
# Replace only kernel header dependencies and rename the symbol. Preserve the
# complete upstream algorithm; do not maintain a hand-translated C oracle.
source = "\n".join(line for line in source.splitlines() if not line.startswith("#include"))
shim = """typedef __UINT32_TYPE__ u32;
typedef __UINT64_TYPE__ u64;
#define ULONG_MAX (__LONG_MAX__ * 2UL + 1UL)
#define BITS_PER_LONG (__SIZEOF_LONG__ * 8)
#define __fls(x) (BITS_PER_LONG - 1 - __builtin_clzl(x))
#define fls64(x) ((x) ? 64 - __builtin_clzll(x) : 0)
#define EXPORT_SYMBOL(x)
#define int_sqrt upstream_int_sqrt
#define int_sqrt64 upstream_int_sqrt64
"""
(out / "reference.c").write_text(shim + source)
clang_target = ["-m32"] if args.target32 else []
rust_target = ["--target", "i686-unknown-linux-gnu"] if args.target32 else []
rust_linker = []
test_runner = []
if args.target32:
    rust_linker = ["-Clinker=clang", "-Clink-arg=-Wl,-m,elf_i386"]
    local_root = paths.tools
    local_lib32 = local_root / "usr/lib32"
    if (local_lib32 / "Scrt1.o").exists():
        # clang needs the 32-bit startup objects as well as the libraries.
        # The linker sysroot resolves absolute paths inside libc.so's script
        # against this extraction, without modifying /usr or /lib.
        rust_linker += [f"-Clink-arg=-B{local_lib32}/",
                        f"-Clink-arg=-L{local_lib32}",
                        f"-Clink-arg=-Wl,--sysroot={local_root}"]
        test_runner = [str(local_lib32 / "ld-linux.so.2"),
                       "--library-path", str(local_lib32)]
if args.runner == "qemu-i386":
    test_runner.insert(0, "qemu-i386-static")
    print("Execution: qemu-i386 userspace emulation (not a 32-bit kernel boot)", flush=True)
else:
    print("Execution: native host userspace", flush=True)
subprocess.run(["clang", *clang_target, "-O2", "-Wall", "-Werror", "-c", str(out / "reference.c"),
                "-o", str(out / "reference.o")], check=True)
subprocess.run(["rustc", *rust_target, *rust_linker, "--edition=2021", "--test", "-Copt-level=2",
                "-Coverflow-checks=yes", str(paths.project / "tests/int_sqrt_host.rs"),
                "-C", f"link-arg={out / 'reference.o'}", "-o", str(out / "tests")],
               check=True)
subprocess.run([*test_runner, str(out / "tests")], check=True)
