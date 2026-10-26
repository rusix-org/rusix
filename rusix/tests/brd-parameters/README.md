# BRD parameter and on-demand device contract

Static Rust guest PID1, shared unchanged by C and Rust BRD kernels. **Never run
on the host or as container PID1.** No kernel behavior is implemented here.
Compilation and VM execution are pending.

Requires PID1 before actions, mounts proc, requires exactly one
`rusix.brd_parameters=1` token, then mounts sysfs and creates guest-only block
nodes. Supply unique decimal `rusix.expect_rd_nr`, `rusix.expect_rd_size` (KiB),
and `rusix.expect_max_part` values. Stage `/proc`, `/sys`, `/dev` and character
console 5:1. No other rootfs utilities/libraries are needed for the static ELF.
The runner must bound guest execution and reject failure/duplicate/missing markers.

Exact ordered inventory, all prefixed `RUSIX_BRD_PARAMETERS_`: `START`,
`PASS parameters`, `PASS initial_devices`, `PASS on_demand`, `PASS independent_io`,
`PASS capacity`, `SUCCESS cases=5`. Any `FAIL` rejects the run.

Five boots: config defaults; `rd_nr=0 rd_size=4096 max_part=1`; `max_part=3`
normalized to4; `max_part=257` clamped to256; legacy `ramdisk_size=010000`
parsed as4096 KiB. Non-default spacing/legacy boots use `rd_nr=1`; spacing
boots set `rd_size=4096`, legacy boot must omit `brd.rd_size`. All modern BRD
parameter tokens use the `brd.` prefix. Expectations are limited to count<=32,
size4096..65536 KiB and spacing1/4/256 to keep this fixture bounded.

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
come from `drivers/block/brd.c`. Negative/overflow parameters, partitions,
allocation failures and concurrent probe races remain outside this fixture.
