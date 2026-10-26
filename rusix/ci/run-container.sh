#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# Run one complete CI profile locally, without host toolchain installations.
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/../scripts/repo-paths.sh"
if [[ $# != 3 ]]; then
    echo 'Usage: bash rusix/ci/run-container.sh IMAGE OUTPUT_DIRECTORY kunit|brd|brd-rust|brd-kunit|brd-ext4-c|brd-ext4-rust|core-ext4-c|core-ext4-rust|completion-c|completion-rust|completion-plain-c|completion-plain-rust|server' >&2
    exit 2
fi
image=$1
output=$(realpath -m -- "$2")
profile=$3
case "$profile" in kunit|brd|brd-rust|brd-kunit|brd-ext4-c|brd-ext4-rust|core-ext4-c|core-ext4-rust|completion-c|completion-rust|completion-plain-c|completion-plain-rust|server) ;; *) echo 'Profile must be kunit, brd, brd-rust, brd-kunit, brd-ext4-c, brd-ext4-rust, core-ext4-c, core-ext4-rust, completion-c, completion-rust, completion-plain-c, completion-plain-rust or server.' >&2; exit 2 ;; esac
case "$output/" in
    "$RUSIX_SOURCE/"*) echo 'Container output must be outside the source checkout.' >&2; exit 2 ;;
esac
if [[ -e "$output/builds" || -L "$output/builds" ]]; then
    echo 'Output already contains a builds path; choose a fresh directory.' >&2
    exit 1
fi
mkdir -p "$output/logs"
# Reserve the output before Docker is started. Do not erase a previous failure.
mkdir "$output/.ci-run" || { echo 'Output already used; choose a fresh directory.' >&2; exit 1; }
accel=${RUSIX_QEMU_ACCEL:-auto}
if [[ "$accel" == auto ]]; then
    if [[ -c /dev/kvm && -r /dev/kvm && -w /dev/kvm ]]; then accel=kvm; else accel=tcg; fi
fi
extra=()
case "$accel" in
    kvm)
        [[ -c /dev/kvm && -r /dev/kvm && -w /dev/kvm ]] || {
            echo 'KVM requested but /dev/kvm is not accessible.' >&2; exit 1;
        }
        extra+=(--device /dev/kvm --group-add "$(stat -c %g /dev/kvm)")
        ;;
    tcg) ;;
    *) echo 'RUSIX_QEMU_ACCEL must be auto, kvm or tcg.' >&2; exit 2 ;;
esac
# A linked worktree's .git points outside the checkout. Mount its metadata at
# the same absolute path; ordinary clones already include .git under /src.
common=$(git -C "$RUSIX_SOURCE" rev-parse --path-format=absolute --git-common-dir)
if [[ "$common" != "$RUSIX_SOURCE/.git" ]]; then
    extra+=(--mount "type=bind,src=$common,dst=$common,readonly")
fi
image_id=$(docker image inspect --format '{{.Id}}' "$image")
printf '%s\n' "$image_id" > "$output/logs/container-image-id.txt"
printf '%s\n' "$accel" > "$output/logs/container-acceleration.txt"
docker run --rm --network none --cap-drop ALL --security-opt no-new-privileges \
    --cpus 2 --memory 5g --memory-swap 5g \
    --user "$(id -u):$(id -g)" "${extra[@]}" \
    --mount "type=bind,src=$RUSIX_SOURCE,dst=/src,readonly" \
    --mount "type=bind,src=$output,dst=/out" \
    --env RUSIX_OUTPUT_ROOT=/out --env RUSIX_TOOLS_ROOT=/opt/no-local-overrides \
    --env "RUSIX_QEMU_ACCEL=$accel" --env "RUSIX_EXT4_IMAGE_ID=$image_id" --workdir /src \
    "$image_id" bash rusix/ci/run.sh "$profile"
