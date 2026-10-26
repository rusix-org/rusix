#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# Container entry point; use run-container.sh from the host.
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/../scripts/repo-paths.sh"
profile=${1:-}
case "$profile" in
    kunit|brd|brd-rust|brd-kunit|brd-ext4-c|brd-ext4-rust|core-ext4-c|core-ext4-rust|completion-c|completion-rust|completion-plain-c|completion-plain-rust|server|server-c) ;;
    *) echo 'Usage: bash rusix/ci/run.sh kunit|brd|brd-rust|brd-kunit|brd-ext4-c|brd-ext4-rust|core-ext4-c|core-ext4-rust|completion-c|completion-rust|completion-plain-c|completion-plain-rust|server|server-c' >&2; exit 2 ;;
esac
mkdir -p "$RUSIX_OUTPUT_ROOT/logs" "$RUSIX_OUTPUT_ROOT/tmp"
export TMPDIR="$RUSIX_OUTPUT_ROOT/tmp"
trap 'printf "%s\n" "$?" > "$RUSIX_OUTPUT_ROOT/logs/ci.exit"' EXIT
cp /opt/rusix/packages.lock /opt/rusix/toolchain.log "$RUSIX_OUTPUT_ROOT/logs/"
export KBUILD_BUILD_TIMESTAMP
KBUILD_BUILD_TIMESTAMP=$(git -C "$RUSIX_SOURCE" show -s --format=%cD HEAD)
export SOURCE_DATE_EPOCH
SOURCE_DATE_EPOCH=$(git -C "$RUSIX_SOURCE" show -s --format=%ct HEAD)
export KBUILD_BUILD_USER=rusix KBUILD_BUILD_HOST=ci KBUILD_BUILD_VERSION=1
{
    git -C "$RUSIX_SOURCE" rev-parse HEAD
    printf 'profile=%s\nacceleration=%s\n' "$profile" "$RUSIX_QEMU_ACCEL"
    printf 'KBUILD_BUILD_TIMESTAMP=%s\nSOURCE_DATE_EPOCH=%s\n' \
        "$KBUILD_BUILD_TIMESTAMP" "$SOURCE_DATE_EPOCH"
    printf '%s\n' 'KBUILD_BUILD_USER=rusix' 'KBUILD_BUILD_HOST=ci' 'KBUILD_BUILD_VERSION=1'
} > "$RUSIX_OUTPUT_ROOT/logs/ci-inputs.log"
bash "$RUSIX_PROJECT/scripts/check-toolchain.sh" \
    > "$RUSIX_OUTPUT_ROOT/logs/preflight.log" 2>&1
python3 "$RUSIX_PROJECT/scripts/test-int-sqrt-host.py" \
    > "$RUSIX_OUTPUT_ROOT/logs/host-native.log" 2>&1
for test in "$RUSIX_PROJECT"/tests/test_*.py; do
    name=$(basename "$test" .py)
    python3 "$test" > "$RUSIX_OUTPUT_ROOT/logs/$name.log" 2>&1
done
bash "$RUSIX_PROJECT/scripts/build-kernel.sh" --profile "$profile" "ci-$profile"
if [[ "$profile" == kunit ]]; then
    bash "$RUSIX_PROJECT/scripts/boot-kunit.sh" \
        "$RUSIX_OUTPUT_ROOT/builds/ci-kunit" ci-kunit
elif [[ "$profile" == brd-kunit || "$profile" == completion-c || "$profile" == completion-rust || "$profile" == completion-plain-c || "$profile" == completion-plain-rust ]]; then
    bash "$RUSIX_PROJECT/scripts/boot-kunit.sh" --brd \
        "$RUSIX_OUTPUT_ROOT/builds/ci-$profile" "ci-$profile"
    bash "$RUSIX_PROJECT/scripts/boot-kunit.sh" --completion \
        "$RUSIX_OUTPUT_ROOT/builds/ci-$profile" "ci-$profile-completion"
elif [[ "$profile" == brd || "$profile" == brd-rust ]]; then
    shopt -s nullglob
    evidence=("$RUSIX_OUTPUT_ROOT"/logs/ci-$profile-build.*)
    [[ ${#evidence[@]} == 1 ]] || {
        echo 'Expected one BRD build evidence directory in a fresh output.' >&2; exit 1;
    }
    python3 "$RUSIX_PROJECT/scripts/test-brd-vm.py" \
        "$RUSIX_OUTPUT_ROOT/builds/ci-$profile" "ci-$profile" --build-evidence "${evidence[0]}"
    python3 "$RUSIX_PROJECT/scripts/test-brd-parameters-vm.py" \
        "$RUSIX_OUTPUT_ROOT/builds/ci-$profile" "ci-$profile" --build-evidence "${evidence[0]}"
    python3 "$RUSIX_PROJECT/scripts/test-brd-partitions-vm.py" \
        "$RUSIX_OUTPUT_ROOT/builds/ci-$profile" "ci-$profile" --build-evidence "${evidence[0]}"
elif [[ "$profile" == brd-ext4-c || "$profile" == brd-ext4-rust || "$profile" == core-ext4-c || "$profile" == core-ext4-rust ]]; then
    shopt -s nullglob
    evidence=("$RUSIX_OUTPUT_ROOT"/logs/ci-$profile-build.*)
    [[ ${#evidence[@]} == 1 ]] || {
        echo "Expected one ext4 build evidence directory." >&2; exit 1;
    }
    python3 "$RUSIX_PROJECT/scripts/test-brd-vm.py" \
        "$RUSIX_OUTPUT_ROOT/builds/ci-$profile" "ci-$profile" --build-evidence "${evidence[0]}"
    python3 "$RUSIX_PROJECT/scripts/test-brd-ext4-vm.py" \
        "$RUSIX_OUTPUT_ROOT/builds/ci-$profile" "ci-$profile" --build-evidence "${evidence[0]}"
    python3 "$RUSIX_PROJECT/scripts/test-brd-parameters-vm.py" \
        "$RUSIX_OUTPUT_ROOT/builds/ci-$profile" "ci-$profile" --build-evidence "${evidence[0]}"
    python3 "$RUSIX_PROJECT/scripts/test-brd-partitions-vm.py" \
        "$RUSIX_OUTPUT_ROOT/builds/ci-$profile" "ci-$profile" --build-evidence "${evidence[0]}"
else
    shopt -s nullglob
    evidence=("$RUSIX_OUTPUT_ROOT"/logs/ci-$profile-build.*)
    [[ ${#evidence[@]} == 1 ]] || {
        echo 'Expected one server build evidence directory in a fresh output.' >&2; exit 1;
    }
    # Exact declared target has DEBUG_FS=n: run ext4/wake consumers directly,
    # keeping the separate block/accounting profile's debugfs gate intact.
    python3 "$RUSIX_PROJECT/scripts/test-brd-ext4-vm.py" \
        "$RUSIX_OUTPUT_ROOT/builds/ci-$profile" "ci-$profile" --build-evidence "${evidence[0]}"
    python3 "$RUSIX_PROJECT/scripts/measure-kernel-languages.py" \
        "$RUSIX_OUTPUT_ROOT/builds/ci-$profile" --build-evidence "${evidence[0]}" \
        --map "$RUSIX_OUTPUT_ROOT/builds/ci-$profile/vmlinux.map" \
        --vmlinux "$RUSIX_OUTPUT_ROOT/builds/ci-$profile/vmlinux" \
        --output "$RUSIX_OUTPUT_ROOT/logs/languages.json"
fi
