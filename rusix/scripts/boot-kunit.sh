#!/usr/bin/env bash
# Boot a built kernel in a bounded VM and parse its real serial output.
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/repo-paths.sh"
accel=${RUSIX_QEMU_ACCEL:-tcg}
case "$accel" in
    tcg) cpu=max ;;
    kvm) cpu=qemu64 ;;
    *) echo 'RUSIX_QEMU_ACCEL must be tcg or kvm.' >&2; exit 2 ;;
esac
baseline=()
mode=migration
filter='*sqrt*'
gate=validate-kunit-results.py
required=(KUNIT INT_SQRT_KUNIT_TEST SERIAL_8250_CONSOLE)
cpus=1
case "${1:-}" in
    --baseline) baseline=(--baseline); mode=baseline; shift ;;
    --completion)
        mode=completion
        filter=rusix_completion_contract
        gate=validate-completion-kunit.py
        required=(KUNIT RUST SMP SERIAL_8250_CONSOLE)
        cpus=2
        shift
        ;;
    --brd)
        mode=brd
        filter='rusix_*'
        gate=validate-brd-kunit.py
        required=(KUNIT RUSIX_BRD_RUST BLK_DEV_RAM SERIAL_8250_CONSOLE)
        cpus=2
        shift
        ;;
esac
if [[ $# != 2 || ! "$2" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo 'Usage: bash rusix/scripts/boot-kunit.sh [--baseline|--brd|--completion] BUILD_DIRECTORY EVIDENCE_LABEL' >&2
    exit 2
fi
build=$(cd -- "$1" && pwd)
label=$2
mkdir -p "$RUSIX_OUTPUT_ROOT/logs"
test -f "$build/arch/x86/boot/bzImage"
test -f "$build/.config"
for setting in "${required[@]}"; do
    if ! grep -qx "CONFIG_${setting}=y" "$build/.config"; then
        echo "Required setting absent: CONFIG_${setting}=y" >&2
        exit 1
    fi
done
# A label identifies one immutable boot attempt. Reject previous partial results
# too; otherwise a failed retry could leave a previous successful JSON alongside
# its new failure log. mkdir reserves the label atomically across script callers.
for suffix in inputs.sha256 console.log qemu.exit kunit.json parse.log parse.exit gate.log gate.exit; do
    if [[ -e "$RUSIX_OUTPUT_ROOT/logs/$label-$suffix" || -L "$RUSIX_OUTPUT_ROOT/logs/$label-$suffix" ]]; then
        echo "Evidence label already used: $label (choose a new label)" >&2
        exit 1
    fi
done
run="$RUSIX_OUTPUT_ROOT/logs/$label-boot.run"
if ! mkdir "$run"; then
    echo "Evidence label already reserved: $label (choose a new label)" >&2
    exit 1
fi
printf '%s\n' "$mode" > "$run/mode.txt"
sha256sum "$RUSIX_PROJECT/scripts/boot-kunit.sh" "$RUSIX_PROJECT/scripts/$gate" \
    > "$run/scripts.sha256"
if [[ "$mode" == completion ]]; then
    sha256sum "$RUSIX_PROJECT/scripts/validate-brd-kunit.py" >> "$run/scripts.sha256"
fi
sha256sum "$build/arch/x86/boot/bzImage" "$build/.config" > "$RUSIX_OUTPUT_ROOT/logs/$label-inputs.sha256"
firmware=()
if [[ -f "$RUSIX_TOOLS_ROOT/usr/share/qemu/qboot.rom" ]]; then
    firmware=(-L "$RUSIX_TOOLS_ROOT/usr/share/qemu" -bios qboot.rom)
fi
# Select math suites by default, BRD ownership with --brd, or completion
# semantics with --completion. Each mode has an independent required inventory.
# Exclude unrelated framework suites (including an intentionally disabled test)
# without relaxing either acceptance gate or modifying upstream tests.
# With system packages only, let QEMU find its own firmware at its default path.
command=(bash "$RUSIX_PROJECT/scripts/with-local-tools.sh" timeout --kill-after=5s 180s
    qemu-system-x86_64 -accel "$accel" -cpu "$cpu" -m 512M -smp "$cpus"
    "${firmware[@]}"
    -display none -serial stdio -monitor none -nic none -no-reboot
    -kernel "$build/arch/x86/boot/bzImage"
    -append "console=ttyS0 kunit.enable=1 kunit.autorun=1 kunit.filter_glob=$filter kunit_shutdown=reboot panic=-1")
printf '%q ' "${command[@]}" > "$run/command.sh"
printf '\n' >> "$run/command.sh"
bash "$RUSIX_PROJECT/scripts/with-local-tools.sh" qemu-system-x86_64 --version > "$run/qemu-version.txt"
set +e
"${command[@]}" > "$RUSIX_OUTPUT_ROOT/logs/$label-console.log" 2>&1
status=$?
set -e
printf '%s\n' "$status" > "$RUSIX_OUTPUT_ROOT/logs/$label-qemu.exit"
if [[ $status != 0 ]]; then
    tail -40 "$RUSIX_OUTPUT_ROOT/logs/$label-console.log" >&2
    exit "$status"
fi
if grep -q 'CPU feature dependency check failure' "$RUSIX_OUTPUT_ROOT/logs/$label-console.log"; then
    echo 'Guest CPU feature dependencies are inconsistent.' >&2
    exit 1
fi
set +e
python3 "$RUSIX_SOURCE/tools/testing/kunit/kunit.py" parse \
    "$RUSIX_OUTPUT_ROOT/logs/$label-console.log" --json="$RUSIX_OUTPUT_ROOT/logs/$label-kunit.json" \
    > "$RUSIX_OUTPUT_ROOT/logs/$label-parse.log" 2>&1
status=$?
set -e
printf '%s\n' "$status" > "$RUSIX_OUTPUT_ROOT/logs/$label-parse.exit"
cat "$RUSIX_OUTPUT_ROOT/logs/$label-parse.log"
[[ $status == 0 ]] || exit "$status"
set +e
python3 "$RUSIX_PROJECT/scripts/$gate" "$RUSIX_OUTPUT_ROOT/logs/$label-kunit.json" \
    "${baseline[@]}" > "$RUSIX_OUTPUT_ROOT/logs/$label-gate.log" 2>&1
status=$?
set -e
printf '%s\n' "$status" > "$RUSIX_OUTPUT_ROOT/logs/$label-gate.exit"
cat "$RUSIX_OUTPUT_ROOT/logs/$label-gate.log"
exit "$status"
