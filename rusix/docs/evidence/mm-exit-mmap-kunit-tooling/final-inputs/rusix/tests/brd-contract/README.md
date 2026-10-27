# VM-only BRD contract probe

`probe.c` is static libc/pthreads userspace run as `/init` in isolated x86_64
QEMU. **Never execute it on the host or as container PID 1.** It writes/discards
`/dev/ram0` and reboots. PID 1 and `rusix.brd_contract=1` checks prevent accidental
invocation; they are not a security boundary against deliberate misuse.

[BRD.md](../../docs/BRD.md) owns the six-case contract and coverage gaps. The
unchanged C driver is the oracle; this fixture does not implement Rust BRD.
Required profile: 4 KiB pages, two online CPUs, builtin 64 MiB RAM disk, 512-byte
logical sectors, `brd.rd_nr=1 brd.rd_size=65536 brd.max_part=1`, ELF/initramfs,
procfs/debugfs, futex and serial console. The runner compiles static `/init`,
stages guest device nodes, verifies build/image provenance and bounds QEMU.

From a clean committed checkout with [documented tools](../../docs/TOOLCHAIN.md):

```bash
bash rusix/scripts/build-kernel.sh --profile brd brd-c
source rusix/scripts/repo-paths.sh
python3 rusix/scripts/test-brd-vm.py "$RUSIX_OUTPUT_ROOT/builds/brd-c" brd-c-001 \
  --build-evidence "$RUSIX_OUTPUT_ROOT/logs/brd-c-build.REPLACE_ME"
```

Use the exact printed build-evidence directory and a fresh run label. Build and
run must use the same revision and output/tool overrides. Evidence is retained
at `$RUSIX_OUTPUT_ROOT/logs/brd-c-001-brd.run`. For pinned container execution,
see [CI tooling](../../ci/README.md). Host gate regression command:
`python3 rusix/tests/test_brd_gate.py`.

The serial gate requires ordered passes for `geometry`, `sparse_read`,
`crossing_write`, `discard_edges`, `concurrent_insert`, `accounting`, followed by
`RUSIX_BRD_SUCCESS cases=6`; failure markers reject the run. VM exit alone is
insufficient. All data operations use direct I/O; counts are checked after
operations settle. This is the C driver baseline, not ext4 or Rust-driver parity.
