#!/usr/bin/env bash
# Boot a built kernel in a bounded VM and parse its real serial output.
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [[ ! -e "$root/linux/.git" && -e "$root/../../linux/.git" ]]; then
    root=$(cd -- "$root/../.." && pwd)
fi
baseline=()
if [[ ${1:-} == --baseline ]]; then
    baseline=(--baseline)
    shift
fi
if [[ $# != 2 || ! "$2" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo 'Usage: bash scripts/boot-kunit.sh [--baseline] BUILD_DIRECTORY EVIDENCE_LABEL' >&2
    exit 2
fi
build=$(cd -- "$1" && pwd)
label=$2
mkdir -p "$root/logs"
test -f "$build/arch/x86/boot/bzImage"
test -f "$build/.config"
for setting in KUNIT INT_SQRT_KUNIT_TEST SERIAL_8250_CONSOLE; do
    if ! grep -qx "CONFIG_${setting}=y" "$build/.config"; then
        echo "Required setting absent: CONFIG_${setting}=y" >&2
        exit 1
    fi
done
# A label identifies one immutable boot attempt. Reject previous partial results
# too; otherwise a failed retry could leave a previous successful JSON alongside
# its new failure log. mkdir reserves the label atomically across script callers.
for suffix in inputs.sha256 console.log qemu.exit kunit.json parse.log parse.exit gate.log gate.exit; do
    if [[ -e "$root/logs/$label-$suffix" || -L "$root/logs/$label-$suffix" ]]; then
        echo "Evidence label already used: $label (choose a new label)" >&2
        exit 1
    fi
done
run="$root/logs/$label-boot.run"
if ! mkdir "$run"; then
    echo "Evidence label already reserved: $label (choose a new label)" >&2
    exit 1
fi
printf '%s\n' "${baseline[*]:-migration}" > "$run/mode.txt"
sha256sum "$root/scripts/boot-kunit.sh" "$root/scripts/validate-kunit-results.py" \
    > "$run/scripts.sha256"
sha256sum "$build/arch/x86/boot/bzImage" "$build/.config" > "$root/logs/$label-inputs.sha256"
firmware=()
if [[ -f "$root/.tools/root/usr/share/qemu/qboot.rom" ]]; then
    firmware=(-L "$root/.tools/root/usr/share/qemu" -bios qboot.rom)
fi
# With system packages only, let QEMU find its own firmware at its default path.
command=(bash "$root/scripts/with-local-tools.sh" timeout --kill-after=5s 180s
    qemu-system-x86_64 -accel tcg -cpu max -m 512M -smp 1
    "${firmware[@]}"
    -display none -serial stdio -monitor none -nic none -no-reboot
    -kernel "$build/arch/x86/boot/bzImage"
    -append 'console=ttyS0 kunit.enable=1 kunit.autorun=1 kunit_shutdown=reboot panic=-1')
printf '%q ' "${command[@]}" > "$run/command.sh"
printf '\n' >> "$run/command.sh"
bash "$root/scripts/with-local-tools.sh" qemu-system-x86_64 --version > "$run/qemu-version.txt"
set +e
"${command[@]}" > "$root/logs/$label-console.log" 2>&1
status=$?
set -e
printf '%s\n' "$status" > "$root/logs/$label-qemu.exit"
if [[ $status != 0 ]]; then
    tail -40 "$root/logs/$label-console.log" >&2
    exit "$status"
fi
set +e
python3 "$root/linux/tools/testing/kunit/kunit.py" parse \
    "$root/logs/$label-console.log" --json="$root/logs/$label-kunit.json" \
    > "$root/logs/$label-parse.log" 2>&1
status=$?
set -e
printf '%s\n' "$status" > "$root/logs/$label-parse.exit"
cat "$root/logs/$label-parse.log"
[[ $status == 0 ]] || exit "$status"
set +e
python3 "$root/scripts/validate-kunit-results.py" "$root/logs/$label-kunit.json" \
    "${baseline[@]}" > "$root/logs/$label-gate.log" 2>&1
status=$?
set -e
printf '%s\n' "$status" > "$root/logs/$label-gate.exit"
cat "$root/logs/$label-gate.log"
exit "$status"
