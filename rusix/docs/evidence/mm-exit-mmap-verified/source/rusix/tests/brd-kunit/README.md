# Rust BRD ownership KUnit checks

`configs/x86_64-brd-kunit.config` enables the Rust driver and KUnit together.
Use `bash rusix/scripts/build-kernel.sh --profile brd-kunit BUILD_NAME`, then
`bash rusix/scripts/boot-kunit.sh --brd BUILD_DIRECTORY EVIDENCE_LABEL`. The local
container entry point also accepts `brd-kunit`. The six-case userspace BRD
contract must still run with KUnit disabled. These nine kernel tests cover parameter policy,
page ownership across discard/reinsertion, XArray ownership on collisions and
destruction, and nested NOIO restoration. They do not establish full I/O parity.

Boot the resulting kernel with `kunit.filter_glob=rusix_*`: the four required
suites are `rusix_brd_policy`, `rusix_brd_store`, `rusix_xarray_insert`, and
`rusix_noio_scope`. This excludes the unrelated upstream Rust framework's
intentionally disabled test without modifying it or permitting skips. The math
compatibility suite uses a hyphen and is checked separately by the math runner.

For a built kernel, use fresh evidence paths outside the checkout and record
its revision, resolved config, image hashes and tool versions. Example local VM
commands (replace `BUILD` and `EVIDENCE` with those absolute paths):

```bash
set +e
bash rusix/scripts/with-local-tools.sh timeout --kill-after=5s 180s \
  qemu-system-x86_64 -machine q35 -accel tcg -cpu max -m 512M -smp 2 \
  -display none -serial stdio -monitor none -nic none -no-reboot \
  -kernel BUILD/arch/x86/boot/bzImage \
  -append 'console=ttyS0 kunit.enable=1 kunit.autorun=1 kunit.filter_glob=rusix_* kunit_shutdown=reboot panic=-1' \
  > EVIDENCE/console.log 2>&1
status=$?
printf '%s\n' "$status" > EVIDENCE/qemu.exit
set -e
test "$status" = 0
python3 tools/testing/kunit/kunit.py parse EVIDENCE/console.log --json=EVIDENCE/kunit.json
python3 rusix/scripts/validate-brd-kunit.py EVIDENCE/kunit.json
python3 rusix/tests/test_brd_kunit_gate.py
```

A parser or gate failure rejects the result. The JSON gate requires all nine
names exactly once and rejects non-pass cases or error/skip counters anywhere,
including additional suites. The gate checks parsed test coverage only; VM exit,
kernel diagnostics and build provenance remain separate verification obligations.
