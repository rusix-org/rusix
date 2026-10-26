# VM-only BRD contract probe

`probe.c` is a static libc/pthreads userspace test, executed as `/init` only inside
an isolated x86_64 QEMU VM. Never execute it on the host or as container PID 1.
It writes and discards `/dev/ram0`, then reboots the guest. PID 1 and the exact
kernel-command-line token `rusix.brd_contract=1` guard accidental invocation;
they are not a security boundary against deliberate misuse.

The contract comes from the pinned `drivers/block/brd.c`, notably
`brd_rw_bvec`, `brd_insert_page`, and `brd_do_discard`, plus the ordinary Linux
block-device userspace interface. The unchanged C driver is the initial oracle.
This probe can later run unchanged against a selected Rust driver. It does not
implement or prove the Rust replacement.

## Environment and execution

Required profile: x86_64, 4096-byte pages, two online CPUs (0 and 1), builtin BRD,
64 MiB `/dev/ram0`, logical sectors of 512 bytes, `brd.rd_nr=1`,
`brd.rd_size=65536`, and `brd.max_part=1`. The kernel needs ELF/initramfs support,
procfs, debugfs, pthread/futex support, block direct I/O, and a serial console.
The runner stages `/init`, `/dev/console` (character 5:1), `/dev/ram0` (block 1:0),
and empty `/proc` and `/debug` directories. The probe mounts procfs/debugfs itself.
It does not load a host or guest module, create host devices, or mount a filesystem
on the test block device.

Compile from the checkout root, without running the resulting binary:

```bash
source rusix/scripts/repo-paths.sh
mkdir -p "$RUSIX_OUTPUT_ROOT/builds/brd-probe"
gcc -static -pthread -O2 -Wall -Wextra -Werror \
  rusix/tests/brd-contract/probe.c \
  -o "$RUSIX_OUTPUT_ROOT/builds/brd-probe/init"
llvm-readelf -h -l "$RUSIX_OUTPUT_ROOT/builds/brd-probe/init"
llvm-nm --undefined-only "$RUSIX_OUTPUT_ROOT/builds/brd-probe/init"
```

The ELF must be static x86_64, without an interpreter or unresolved symbols.
The VM runner, `rusix/scripts/test-brd-vm.py`, packages and executes it with a
bounded QEMU invocation. A successful compile is not a runtime result. Static
libc links the host toolchain's implementation; this is not yet the pinned,
independently supplied userspace environment required by Phase 1.

## Build and run the C baseline

From a clean committed checkout with the documented tools available:

```bash
bash rusix/scripts/build-kernel.sh --profile brd brd-c
source rusix/scripts/repo-paths.sh
python3 rusix/scripts/test-brd-vm.py "$RUSIX_OUTPUT_ROOT/builds/brd-c" brd-c-001 \
  --build-evidence "$RUSIX_OUTPUT_ROOT/logs/brd-c-build.REPLACE_ME"
```

Replace `brd-c-build.REPLACE_ME` with the exact evidence directory printed by the
build, and use a fresh run label for every attempt. Build and run must use the
same committed source revision and consistent output/tool overrides. The runner
requires matching build hashes and recorded C selection; it snapshots the kernel
and packages the guest itself. Results go to `logs/brd-c-001-brd.run` under the
output root. Regression checks: `python3 rusix/tests/test_brd_gate.py`.

## Required cases

The serial gate requires exactly these cases in order, each emitted as
`RUSIX_BRD_PASS <name>`, followed by `RUSIX_BRD_SUCCESS cases=6`.
Any `RUSIX_BRD_FAIL` rejects the run. Reboot/VM exit alone is never success.

| Case | Assertions |
| --- | --- |
| `geometry` | Page size, CPU availability, block node identity, capacity, logical/physical sector size, and initially zero allocated backing pages. |
| `sparse_read` | Direct reads at the start, middle, and end of the disk return zeros without allocating backing pages. |
| `crossing_write` | An 8192-byte patterned write at offset 3584 uses a buffer at offset 512 within its allocation, forcing different buffer/device page splits; all bytes read back correctly and unwritten edge bytes remain zero. Exactly three pages are allocated. |
| `discard_edges` | Four patterned pages are written at 1 MiB. Discarding the interval `[base+512, base+12800)` removes only the two fully covered pages, preserving both partial edge pages. A repeated discard is idempotent, including page accounting. |
| `concurrent_insert` | Two writers pinned to separate CPUs start together through a barrier, writing disjoint sectors in each of 64 fresh pages. Both sectors survive and untouched bytes stay zero. This exercises competing insertion but does not guarantee every run reaches the same internal race window. |
| `accounting` | Settled debugfs counts match all populated pages. A whole-device discard returns the count to zero; reads of all written regions remain zero and allocate no new pages. |

All data operations use `O_DIRECT`; no buffered cache can conceal driver content.
Counts are read only after operations settle. This tests disjoint concurrent
writes, not atomicity of overlapping writes. No pass is a claim about allocation
failure/NOWAIT, concurrent discard, busy removal, module lifecycle, partitions,
on-demand creation, highmem, arm64, ext4, performance, or full Phase 1 completion.
Those require separate baseline workloads and driver integration evidence.
