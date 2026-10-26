# BRD parameter and on-demand device contract

Static Rust guest PID1, shared unchanged by C and Rust BRD kernels. **Never run
on the host or as container PID1.** No kernel behavior is implemented here.
All six variants pass for both implementations on q35 at `9d1c1ca5dd` with an
identical fixture archive: [paired evidence](../../docs/evidence/brd-q35/manifest.json).

Requires PID1 before actions, mounts proc, requires exactly one
`rusix.brd_parameters=1` token, then mounts sysfs and creates guest-only block
nodes. Supply unique decimal `rusix.expect_rd_nr`, `rusix.expect_rd_size` (KiB),
and `rusix.expect_max_part` values. Stage `/proc`, `/sys`, `/dev` and character
console 5:1 plus `/dev/kmsg` character 1:11. Markers use single printk records,
not serial-fragment reconstruction; ordinary output remains on the console. No other rootfs utilities/libraries are needed for the static ELF.
The runner bounds each fresh VM to 180 seconds and rejects failed, missing,
duplicate or reordered markers, nonzero exits, timeouts and kernel diagnostics.
It uses `q35` with ACPI/PCI configuration and requires `CONFIG_SYSFS=y` plus
`CONFIG_BLOCK_LEGACY_AUTOLOAD=y`. The latter enables the block layer's registered
major probe when an unopened RAM disk is absent, including for builtin BRD.

Exact ordered inventory, all prefixed `RUSIX_BRD_PARAMETERS_`: `START`,
`PASS parameters`, `PASS initial_devices`, `PASS on_demand`, `PASS independent_io`,
`PASS capacity`, `SUCCESS cases=5`. Any `FAIL` rejects the run.

Five normal boots: config defaults; `rd_nr=0 rd_size=4096 max_part=1`; `max_part=3`
normalized to 4; `max_part=257` clamped to 256; legacy `ramdisk_size=010000`
parsed as 4096 KiB. Non-default spacing/legacy boots use `rd_nr=1`; spacing
boots set `rd_size=4096`, legacy boot must omit `brd.rd_size`. All modern BRD
parameter tokens use the `brd.` prefix. Expectations are limited to count<=32,
size 4096..65536 KiB and spacing 1/4/256 to keep this fixture bounded.

Checks sysfs parameters and complete initial disk inventory before any opens.
Opening newly created major1/minorN nodes exercises on-demand creation; for a
config precreating ram1, an additional disk at index `rd_nr` ensures a fresh
probe. Checks minor spacing and capacity via both sysfs and BLKGETSIZE64.
Aligned O_DIRECT first/last-sector writes stay independent between ram0/ram1;
untouched middle sectors remain zero. Initial contents are checked before writes.

Capacity expectations come from pinned LTS `block/fops.c`:
`blkdev_read_iter` clips crossing reads, returns EOF at/beyond capacity;
`blkdev_write_iter` rejects nonempty writes starting there with ENOSPC. The
fixture verifies clipped length/data/untouched buffer suffix and both EOF/error
offsets, then confirms the final valid sector is unchanged. These are whole-block
userspace boundary checks, not a claim that the BRD callback independently
performs all validation. Parameter parsing/normalization and probe expectations
come from `drivers/block/brd.c`.

A sixth boot uses `rd_nr=0 max_part=1073741824`: normalization publishes signed
`INT_MIN`, major 1 remains registered, and opening ram0 fails with ENXIO without
publishing a disk. Its separate ordered cases are `parameters`,
`major_registered`, `initial_devices`, `open_enxio`, `final_devices`. It never
reads debugfs: the C failed-allocation path leaves an unsafe counter pointer.
Negative parameters, allocation failures and concurrent probe races remain
outside this fixture. [Partition discovery/I/O](../brd-partitions/README.md)
has its own fixture.

From a clean committed checkout, run against matching build evidence:

```bash
python3 rusix/scripts/test-brd-parameters-vm.py BUILD_DIRECTORY EVIDENCE_LABEL \
  --build-evidence BUILD_EVIDENCE_DIRECTORY
```

The local `brd` / `brd-rust` profiles run the six-case block probe and these six
boots plus the partition fixture. The `brd-ext4-c` / `brd-ext4-rust` profiles additionally run the six-case
ext4 workload on the same built kernel. Each boot gets a fresh RAM disk and its
own command, expectations, console, exit and result evidence; failures remain
preserved. The parameter fixture does not test partition tables or partition
I/O merely by checking normalized minor spacing.
