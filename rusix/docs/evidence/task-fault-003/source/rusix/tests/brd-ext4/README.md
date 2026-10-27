# Ordinary ext4 userspace fixture

**C and Rust q35 VM runs pass** at `9d1c1ca5dd` with an identical fixture archive:
[paired evidence](../../docs/evidence/brd-q35/manifest.json). This is separate from the unchanged
six-case direct-I/O BRD contract. Buffered writes, per-file fsync, aligned direct reads/writes and remount checks
exercise the same staged rootfs and workload against
C and Rust BRD kernels. Never execute `init` or `workload.sh` on the host or as
container PID 1: the workload formats and writes `/dev/ram0`.

The static Rust PID1 requires PID 1 and the exact kernel token
`rusix.brd_ext4=1`, verifies block device 1:0, generates deterministic inputs,
runs the ordinary Debian shell/utilities, checks exit status, and reboots.
The child shell independently requires the token, parent PID 1 and authorization
environment. These prevent accidental use, not deliberate circumvention.

## Build and stage

Compile without running the output, inside the pinned toolchain container:

```sh
rustc --edition 2021 --target x86_64-unknown-linux-gnu \
  -C target-feature=+crt-static -C panic=abort -C opt-level=2 \
  rusix/tests/brd-ext4/init.rs -o /out/ext4-init
readelf -h -l -d /out/ext4-init
```

Require x86_64 static ELF with no `INTERP` or `NEEDED`. Compilation and ELF
inspection passed with the pinned container Rust 1.85.1. The executable has
never been run on the host. Guest execution is recorded in the paired evidence.

The fixture image builds successfully from the inspected local toolchain image
and its signed Debian snapshot sources (`20261025T000000Z`). Added e2fsprogs and
all dependencies are pinned in [ext4-packages.lock](ext4-packages.lock); the
Docker build and runner compare package inventories against that tracked file.
Select and record the inspected local base/final image IDs for each build. Reconstruct
the base using [CI tooling](../../ci/README.md) when unavailable. Image identity
passed to the runner is caller attestation; inventory checks verify versions,
while archived-file hashes record the actual staged bytes. No package
installation is performed by the guest fixture.

Stage a fresh `newc` archive, without creating host device nodes:

| Guest path | Input |
| --- | --- |
| `/init` | Compiled static executable, mode 0755 |
| `/ext4-workload.sh` | `workload.sh`, readable by root |
| `/expected/SHA256SUMS`, `/expected/FINAL.sha256` | Checked-in digest manifests |
| `/bin/sh` | Pinned dash executable (dereference the container's symlink) |
| `/usr/bin/` | `mount`, `umount`, `blockdev`, `cat`, `cp`, `chmod`, `ln`, `truncate`, `dd`, `sync`, `sha256sum`, `stat`, `cmp`, `mv`, `rm` |
| `/usr/sbin/` | `mkfs.ext4` and `e2fsck` (dereference symlinks) |
| `/etc/mke2fs.conf` | Exact config from the fixture image; hash it |
| `/proc`, `/mnt/test`, `/expected`, `/dev`, `/etc` | Directories |
| `/dev/console`, `/dev/kmsg`, `/dev/ram0` | Character 5:1, character 1:11 and block 1:0 |
| `/dev/null`, `/dev/zero`, `/dev/random`, `/dev/urandom` | Character 1:3, 1:5, 1:8, 1:9 |

For **each** staged ordinary executable, inspect `readelf -l -d` inside the
fixture image. Copy its exact `PT_INTERP` path and recursively resolved
`DT_NEEDED` libraries, preserving absolute guest paths. On these trusted pinned
Debian executables, `ldd` can supply the resolved closure; reject `not found`,
relative resolutions, or paths outside the image. Dereference library symlinks
at the guest lookup path, or preserve every link and target. Do not copy the
host's libraries or merely guess libc is sufficient: ext4 and mount/coreutils
have additional library dependencies. The runner resolves the actual closure. Record hashes for every archived file and the final archive.
Use C locale; no host locale/NSS config is needed. `mount -n` avoids mtab writes.

Use a fresh 64 MiB BRD, two CPUs, bounded memory/time, serial console and no
network: `rdinit=/init console=ttyS0 rusix.brd_ext4=1 brd.rd_nr=1
brd.rd_size=65536 brd.max_part=1 kunit.enable=0`. Require builtin ext4 with journal,
ELF/script execution, initramfs, procfs, multiuser and the selected BRD. Do not use
`kunit_shutdown=reboot`. Do not reuse a running guest or filesystem image.

## Acceptance

Require one `RUSIX_EXT4_START`, these ordered pass markers, then exactly one
`RUSIX_EXT4_SUCCESS cases=6`. Reject every failure marker, panic, timeout,
missing/duplicate/reordered case or unsuccessful child/VM outcome; reboot alone
is insufficient. START/PASS/SUCCESS use one `/dev/kmsg` write per record, avoiding
tty/printk interleaving. The runner enables devkmsg, disables printk timestamps
and sets loglevel 7; it never reconstructs fragmented markers. Keep serial output and exact kernel/rootfs/tool provenance.

1. `mkfs`: ordinary `mkfs.ext4` creates the filesystem.
2. `initial_write`: patterned and sparse files, digests, mode and hardlink checks.
3. `remount_read`: unmount/remount preserves data and metadata.
4. `mutate`: truncate/overwrite, rename and unlink preserve expected contents.
5. `final_read`: read-only remount verifies final digests, mode and absent names.
6. `fsck`: offline `e2fsck -f -n` returns zero without repairs.

Payload byte `i` is `((i*73 + (i>>8)*19) XOR 0xa5) & 255`, for 1 MiB. Sparse
expected data is 1 MiB of zeros with payload bytes `[0,16384)` at offset 32768.
Both fixed SHA-256 digests were independently calculated with Python hashlib.
The test verifies input digests before formatting, and output digests after each
remount. It establishes ordinary userspace/ext4 behavior, not crash recovery,
power-loss durability, full filesystem coverage or performance parity.

## Runner

The companion runner implements this staging procedure and retains ELF/ldd
records, package inventory, source/image hashes and deterministic initramfs.
Inside the prepared fixture image, from a clean committed checkout:

```sh
export RUSIX_EXT4_IMAGE_ID=sha256:REPLACE_WITH_INSPECTED_FIXTURE_IMAGE_ID
export RUSIX_QEMU_ACCEL=tcg  # or kvm with /dev/kvm explicitly passed through
python3 rusix/scripts/test-brd-ext4-vm.py /out/builds/ext4-c ext4-c-001 \
  --build-evidence /out/logs/ext4-c-build.REPLACE_ME
```

Use `brd-ext4-c` or `brd-ext4-rust` build profiles with matching implementation
selection proof; the runner rejects ordinary BRD profiles without ext4. Set
`RUSIX_OUTPUT_ROOT=/out` consistently and use a fresh label/output directory.
Only QEMU receives the guest archive: no host mounts, device-node creation,
formatting or fixture execution occurs. The runner requires the fixture's
package inventory to match installed packages. Its host-only regression suite
is `python3 rusix/tests/test_brd_ext4_gate.py`.

For a local rebuild, select the inspected base explicitly:

```sh
base_id=$(docker image inspect --format '{{.Id}}' rusix-toolchain:trixie-20261025)
docker tag "$base_id" rusix-toolchain:ext4-base
docker build --pull=false --build-arg TOOLCHAIN_IMAGE=rusix-toolchain:ext4-base \
  -t rusix-ext4:trixie-20261025 -f rusix/tests/brd-ext4/Dockerfile rusix/tests/brd-ext4
```

Record `base_id` with the build log; `run-container.sh` records the actual final
image ID and runs that inspected identity. No preexisting laptop image is needed.

## Generic wake consumers

The guarded PID1 now runs `wake_probe.rs` after the filesystem workload. Four
additional required markers cover pipe poll, pipe/eventfd epoll delivery, one-shot
rearming, and DEL/close with a surviving registration. All descriptors are
nonblocking, waits finite, and x86_64 packed epoll fields accessed unaligned.
At `df5d5cb7f2c0`, all four pass with both C/Rust core selections and identical
fixtures. [Evidence](../../docs/evidence/wait-wake-ext4/manifest.json). Historical
six-case ext4 results above retain their narrower scope. The runner records `wake_cases` separately and hashes
the module with all other fixture inputs. Never execute the fixture on the host.


Two separately recorded `locked_cases` now require blocking eventfd and timerfd
reads after the four nonblocking cases. The observer samples sleeping read
syscalls before producer release; bounded controller cleanup retains descriptor
lifetimes. [The locked-wait record](../../experiments/wait-locked/README.md) owns
the exact observation and cleanup limits and links matched runtime evidence.
