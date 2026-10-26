# Bounded DOS partition contract

**Five cases pass for C and Rust on q35** at `9d1c1ca5dd`, with an identical
fixture archive: [paired evidence](../../docs/evidence/brd-q35/manifest.json).
Static Rust PID1 runs unchanged against C and Rust BRD. Never execute its binary on the host or as
container PID1: it writes an MBR and block data. It requires PID1 and the exact
`rusix.brd_partitions=1` authorization before creating guest block nodes/writing.

One fresh q35 VM uses two 4 MiB RAM disks, `brd.rd_nr=2 brd.rd_size=4096
brd.max_part=4`. The fixture writes one DOS primary partition of type 0x83,
starting at sector 2048 with length 2048 sectors, then invokes `BLKRRPART` before
opening the partition. The pinned `block/ioctl.c` whole-disk scan and
`block/partitions/msdos.c` LBA parsing define this interface. Required config
addition is `CONFIG_MSDOS_PARTITION=y`; sysfs, ELF/initramfs and normal BRD VM
settings are also required. No external partitioning utility is used.

The exact ordered `RUSIX_BRD_PARTITIONS_` inventory is `START`, five `PASS` lines,
then `SUCCESS cases=5`:

1. `discovery`: write a deterministic valid MBR and request partition rescan.
2. `geometry`: ram0p1 is major 1/minor 1, partition 1, with expected start and
   sysfs/ioctl size; ram1 is major 1/minor 4.
3. `translation`: partition first/last-sector writes appear at whole-disk
   offsets; a whole-disk write appears inside the partition; adjacent guard
   sectors remain unchanged.
4. `boundaries`: crossing reads and writes clip to the final sector; the write
   updates that sector through both views without changing adjacent guards.
   Reads at/beyond partition end return EOF and writes there return ENOSPC,
   leaving the newly written last sector and adjacent guards intact.
5. `independent_disk`: corresponding ram1 sectors remain zero, its later write
   leaves ram0p1 unchanged, and the original MBR survives all operations.

Stage `/init`, `/proc`, `/sys`, `/dev`, console character 5:1 and `/dev/kmsg`
character 1:11. Markers use single printk records without reconstruction. PID1
creates block nodes in the guest. All data I/O uses aligned direct-I/O buffers.
The runner compiles static Rust, rejects ELF interpreter/dynamic dependencies,
requires matching clean source/build evidence, copies the kernel, and records
source/config/artifact hashes, commands, versions, output and exit codes. It
rejects malformed markers, diagnostics and timeouts; VM reboot alone is no pass.

```bash
python3 rusix/scripts/test-brd-partitions-vm.py BUILD_DIRECTORY EVIDENCE_LABEL \
  --build-evidence BUILD_EVIDENCE_DIRECTORY
python3 rusix/tests/test_brd_partitions_gate.py
```

Supported build profiles are `brd`, `brd-rust`, `brd-ext4-c`, `brd-ext4-rust`,
with the required parser enabled. Build/CI integration is separate. This fixture
does not cover GPT, extended partitions, rescanning open partitions, partition
resize/removal, partition races or crash consistency. EOF/ENOSPC are block-layer
contracts, not proof that the BRD callback implements bounds checks itself.
