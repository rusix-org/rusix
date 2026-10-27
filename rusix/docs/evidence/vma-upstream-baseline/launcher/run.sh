#!/usr/bin/env bash
# Prepared only: root review required; never bypass the shared build/test lock.
set -euo pipefail
base=/home/aaron/code/rusix
run="$base/linux-out/vma-upstream-baseline-001"
draft="$base/linux-out/vma-upstream-baseline-draft"
tooling="$base/linux-out/vma-tooling-001"
image=sha256:3cb67848e1aad76fb1451ebd3b1952961ee9665f73620d4ca8a467aa5e5eb55e
exec 9>"$base/linux-out/.wait-owner-remaining.lock"
flock -n 9 || { echo 'Another matrix is active' >&2; exit 2; }
python3 -B "$draft/check.py" >/dev/null
[[ ! -e "$run/execution" ]]
[[ $(docker image inspect --format '{{.Id}}' "$image") == "$image" ]]
mkdir "$run/execution"
out="$run/execution"
owned_cidfile="$out/container.cid"
finish() {
    status=$?
    trap - EXIT INT TERM
    if [[ -f "$owned_cidfile" ]]; then
        cid=$(cat "$owned_cidfile")
        if [[ "$cid" =~ ^[0-9a-f]{64}$ ]]; then docker rm -f "$cid" >/dev/null 2>&1 || true; fi
    fi
    [[ -f "$out/container.exit" ]] || printf '%s\n' "$status" > "$out/container.exit"
    printf '%s\n' "$status" > "$out/launcher.exit"
    exit "$status"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
sha256sum "$draft/run.sh" "$draft/container.py" "$draft/check.py" "$draft/prepare-inputs.py" > "$out/launcher.sha256"
python3 -B "$draft/check.py" > "$out/inputs-before.json"
printf '%s\n' "$image" > "$out/image-id.txt"
set +e
timeout --signal=TERM --kill-after=30s 15m docker run --rm --cidfile "$owned_cidfile" \
    --network none --cap-drop ALL --security-opt no-new-privileges --read-only \
    --cpus 2 --memory 2g --memory-swap 2g --user "$(id -u):$(id -g)" \
    --mount "type=bind,src=$run/inputs,dst=/inputs,readonly" \
    --mount "type=bind,src=$draft,dst=/draft,readonly" \
    --mount "type=bind,src=$tooling,dst=/tooling,readonly" \
    --mount "type=bind,src=$out,dst=/out" \
    --env "RUSIX_VMA_BASELINE_IMAGE=$image" --env PYTHONDONTWRITEBYTECODE=1 \
    --env TMPDIR=/out --workdir /out \
    "$image" python3 -B /draft/container.py > "$out/container.log" 2>&1
status=$?
set -e
printf '%s\n' "$status" > "$out/container.exit"
[[ "$status" == 0 ]] || exit "$status"
sha256sum -c "$out/launcher.sha256" > "$out/launcher-after.log"
python3 -B "$draft/check.py" > "$out/inputs-after.json"
cmp "$out/inputs-before.json" "$out/inputs-after.json"
python3 -B "$draft/check.py" --results > "$out/acceptance.json"
