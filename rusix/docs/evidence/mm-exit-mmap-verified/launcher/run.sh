#!/usr/bin/env bash
# DRAFT ONLY: parent must review; never run alongside another kernel matrix.
set -euo pipefail
base=/home/aaron/code/rusix
source_tree="$base/linux-mm-exit-mmap-fix"
draft="$base/linux-out/mm-exit-mmap-verification-retry-draft"
run="$base/linux-out/mm-exit-mmap-verification-002"
expected=8b6ab8382784f5873e416d5bdadae62b4565bb2d
image=sha256:c02eb3929889b3f0cc035d57a02c844e0c74c71d24fbda1311249faeb8257f63
exec 9>"$base/linux-out/.wait-owner-remaining.lock"
flock -n 9 || { echo 'Another kernel matrix is active' >&2; exit 2; }
python3 -B "$draft/preflight.py" --require-fresh >/dev/null
[[ -c /dev/kvm && -r /dev/kvm && -w /dev/kvm ]]
[[ $(docker image inspect --format '{{.Id}}' "$image") == "$image" ]]
python3 - <<'PY'
import json, subprocess
ids = subprocess.check_output(['docker','ps','-q'], text=True).split()
if ids:
    for item in json.loads(subprocess.check_output(['docker','inspect',*ids], text=True)):
        if any(m.get('Destination') == '/src' and m.get('Source','').startswith('/home/aaron/code/rusix/linux') for m in item.get('Mounts', [])):
            raise SystemExit('Kernel container already active')
PY
mkdir "$run"
active_output=
owned_cidfile=
finish_owned() {
    status=$?
    trap - EXIT INT TERM
    if [[ -n "$owned_cidfile" && -f "$owned_cidfile" ]]; then
        cid=$(cat "$owned_cidfile")
        if [[ "$cid" =~ ^[0-9a-f]{64}$ ]]; then docker rm -f "$cid" >/dev/null 2>&1 || true; fi
    fi
    printf '%s\n' "$status" > "$run/matrix.exit"
    if [[ -n "$active_output" ]]; then
        printf '%s\n' "$status" > "$active_output/logs/launcher.exit"
        if [[ ! -e "$active_output/logs/container.exit" ]]; then printf '%s\n' "$status" > "$active_output/logs/container.exit"; fi
    fi
    exit "$status"
}
trap finish_owned EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
python3 -B "$draft/preflight.py" --lifecycle-prerequisite > "$run/lifecycle-prerequisite-before.json"
python3 -B "$draft/preflight.py" --retained-c-prerequisite > "$run/retained-c-prerequisite-before.json"
python3 -B "$draft/preflight.py" --prerequisite > "$run/config-prerequisite-before.json"
python3 -B "$draft/preflight.py" > "$run/source-before.json"
python3 -B "$draft/preflight.py" --launcher-hashes > "$run/launcher.sha256"
mkdir "$run/fixture-source"
for relative in rusix/tests/vma-lifecycle/init.rs rusix/tests/vma-lifecycle/probe.c rusix/tests/vma-lifecycle/README.md mm/exit_mmap_test.c rust/helpers/exit_mmap_test.c rust/kernel/mm/exit_tests.rs; do
    mkdir -p "$run/fixture-source/$(dirname "$relative")"
    cp "$source_tree/$relative" "$run/fixture-source/$relative"
done
common=$(git -C "$source_tree" rev-parse --path-format=absolute --git-common-dir)
# Calibration regenerates LLVM disassembly. Host LLVM must never inspect it:
# postchecks use the exact build image, retaining host-absolute remapping paths.
postcheck() {
    local label=$1 destination=$2
    shift 2
    owned_cidfile="$run/$label.cid"
    mkdir "$run/$label-tmp"
    printf '%s\n' "$image" > "$run/$label-image.txt"
    set +e
    timeout --signal=TERM --kill-after=30s 5m docker run --rm --cidfile "$owned_cidfile" \
      --network none --cap-drop ALL --security-opt no-new-privileges --read-only \
      --cpus 1 --memory 2g --memory-swap 2g --user "$(id -u):$(id -g)" \
      --mount "type=bind,src=$common,dst=$common,readonly" \
      --mount "type=bind,src=$source_tree,dst=$source_tree,readonly" \
      --mount "type=bind,src=$draft,dst=$draft,readonly" \
      --mount "type=bind,src=$run,dst=$run" \
      --env "TMPDIR=$run/$label-tmp" --env PYTHONDONTWRITEBYTECODE=1 \
      --env "RUSIX_PINNED_POSTCHECK_IMAGE=$image" --workdir "$source_tree" \
      "$image" python3 -B "$draft/check-results.py" "$@" \
      > "$destination" 2> "$run/$label.stderr"
    local status=$?
    set -e
    printf '%s\n' "$status" > "$run/$label.exit"
    [[ "$status" == 0 ]] || return "$status"
    [[ ! -s "$run/$label.stderr" ]] || { echo 'Postcheck diagnostics require review' >&2; return 1; }
}
for key in ordinary-c ordinary-rust kunit-c kunit-rust; do
    case "$key" in
        ordinary-c) profile=exit-mmap-c ;;
        ordinary-rust) profile=exit-mmap-rust ;;
        kunit-c) profile=exit-mmap-kunit-c ;;
        kunit-rust) profile=exit-mmap-kunit-rust ;;
    esac
    output="$run/$key"
    mkdir -p "$output/logs"
    active_output="$output"
    owned_cidfile="$output/logs/container.cid"
    python3 -B "$draft/preflight.py" > "$output/logs/source-before.json"
    cmp "$run/source-before.json" "$output/logs/source-before.json"
    printf '%s\n' "$image" > "$output/logs/container-image-id.txt"
    set +e
    timeout --signal=TERM --kill-after=30s 4h docker run --rm --cidfile "$owned_cidfile" \
      --network none --cap-drop ALL --security-opt no-new-privileges \
      --cpus 2 --memory 5g --memory-swap 5g --user "$(id -u):$(id -g)" \
      --device /dev/kvm --group-add "$(stat -c %g /dev/kvm)" \
      --mount "type=bind,src=$common,dst=$common,readonly" \
      --mount "type=bind,src=$source_tree,dst=/src,readonly" \
      --mount "type=bind,src=$output,dst=/out" \
      --env RUSIX_OUTPUT_ROOT=/out --env RUSIX_TOOLS_ROOT=/opt/no-local-overrides \
      --env RUSIX_QEMU_ACCEL=kvm --env "RUSIX_EXT4_IMAGE_ID=$image" --workdir /src \
      "$image" bash rusix/ci/run.sh "$profile" > "$output/logs/container.log" 2>&1
    status=$?
    set -e
    printf '%s\n' "$status" > "$output/logs/container.exit"
    [[ "$status" == 0 ]] || exit "$status"
    sha256sum -c "$run/launcher.sha256" > "$output/logs/launcher-after.log"
    postcheck "$key-postcheck" "$output/logs/postchecks.json" --key "$key"
    printf '0\n' > "$output/logs/launcher.exit"
done
postcheck pair-postcheck "$run/pair-result.json"
sha256sum -c "$run/launcher.sha256" > "$run/launcher-after.log"
python3 -B "$draft/preflight.py" > "$run/source-after.json"
cmp "$run/source-before.json" "$run/source-after.json"


python3 -B "$draft/preflight.py" --prerequisite > "$run/config-prerequisite-after.json"
cmp "$run/config-prerequisite-before.json" "$run/config-prerequisite-after.json"

python3 -B "$draft/preflight.py" --lifecycle-prerequisite > "$run/lifecycle-prerequisite-after.json"
cmp "$run/lifecycle-prerequisite-before.json" "$run/lifecycle-prerequisite-after.json"

python3 -B "$draft/preflight.py" --retained-c-prerequisite > "$run/retained-c-prerequisite-after.json"
cmp "$run/retained-c-prerequisite-before.json" "$run/retained-c-prerequisite-after.json"
