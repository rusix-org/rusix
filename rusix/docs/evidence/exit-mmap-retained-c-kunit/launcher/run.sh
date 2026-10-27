#!/usr/bin/env bash
set -euo pipefail
base=/home/aaron/code/rusix
draft="$base/linux-out/exit-mmap-retained-c-kunit-draft"
output="$base/linux-out/exit-mmap-retained-c-kunit-001"
image=sha256:c02eb3929889b3f0cc035d57a02c844e0c74c71d24fbda1311249faeb8257f63
exec 9>"$base/linux-out/.wait-owner-remaining.lock"
flock -n 9 || { echo 'Another kernel matrix is active' >&2; exit 2; }
python3 -B "$draft/check.py"
[[ $(docker image inspect --format '{{.Id}}' "$image") == "$image" ]]
[[ -c /dev/kvm && -r /dev/kvm && -w /dev/kvm ]]
common=$(git -C "$base/linux-mm-exit-mmap" rev-parse --path-format=absolute --git-common-dir)
mkdir "$output"
mkdir "$output/tmp"
sha256sum "$draft"/{run.sh,boots.py,check.py,inputs.json,ready.json,README.md} > "$output/launcher.sha256"
cidfile="$output/container.cid"
cleanup() { if [[ -f "$cidfile" ]]; then local cid; cid=$(cat "$cidfile"); if [[ "$cid" =~ ^[0-9a-f]{64}$ ]]; then docker rm -f "$cid" >/dev/null 2>&1 || true; fi; fi; }
trap cleanup EXIT
set +e
timeout --signal=TERM --kill-after=30s 8m docker run --cidfile "$cidfile" \
 --network none --cap-drop ALL --security-opt no-new-privileges --read-only \
 --cpus 2 --memory 2g --memory-swap 2g --pids-limit 256 --user "$(id -u):$(id -g)" \
 --device /dev/kvm --group-add "$(stat -c %g /dev/kvm)" \
 --mount "type=bind,src=$common,dst=$common,readonly" \
 --mount "type=bind,src=$base/linux-mm-exit-mmap,dst=$base/linux-mm-exit-mmap,readonly" \
 --mount "type=bind,src=$base/linux-mm-exit-mmap-fix,dst=$base/linux-mm-exit-mmap-fix,readonly" \
 --mount "type=bind,src=$base/linux-out/mm-exit-mmap-verification-001/kunit-c,dst=$base/linux-out/mm-exit-mmap-verification-001/kunit-c,readonly" \
 --mount "type=bind,src=$base/linux-out/exit-mmap-fixture-gate-reinspection-002,dst=$base/linux-out/exit-mmap-fixture-gate-reinspection-002,readonly" \
 --mount "type=bind,src=$draft,dst=$draft,readonly" \
 --mount "type=bind,src=$output,dst=$output" \
 --env "TMPDIR=$output/tmp" --env PYTHONDONTWRITEBYTECODE=1 \
 --env "RUSIX_PINNED_POSTCHECK_IMAGE=$image" --env "RUSIX_OUTPUT_ROOT=$output" \
 --env RUSIX_TOOLS_ROOT=/opt/no-local-overrides --env RUSIX_QEMU_ACCEL=kvm \
 --workdir "$base/linux-mm-exit-mmap" \
 "$image" python3 -B "$draft/boots.py" > "$output/container.log" 2>&1
status=$?
printf '%s\n' "$status" > "$output/container.exit"
# A timeout can interrupt Python before its finally block. Stop any remaining
# owned container before the unconditional host-side audit of immutable inputs.
inspection_status=1
if [[ -f "$cidfile" ]]; then
    cid=$(cat "$cidfile")
    if [[ "$cid" =~ ^[0-9a-f]{64}$ ]]; then
        docker inspect "$cid" > "$output/container-inspect-before-stop.json" 2> "$output/container-inspect-before-stop.stderr"
        inspection_status=$?
        if [[ $inspection_status == 0 ]]; then
            running=$(python3 -c 'import json,sys; print(str(json.load(open(sys.argv[1]))[0]["State"]["Running"]).lower())' "$output/container-inspect-before-stop.json")
            if [[ "$running" == true ]]; then
                timeout --kill-after=5s 20s docker kill "$cid" > "$output/container-kill.log" 2>&1
                printf '%s\n' "$?" > "$output/container-kill.exit"
            fi
            docker inspect "$cid" > "$output/container-inspect.json" 2> "$output/container-inspect.stderr"
            inspection_status=$?
            if [[ $inspection_status == 0 ]]; then
                python3 -c 'import json,sys; s=json.load(open(sys.argv[1]))[0]["State"]; assert not s["Running"] and s["Pid"] == 0' "$output/container-inspect.json" > "$output/container-terminal.log" 2>&1
                inspection_status=$?
            fi
        fi
    fi
fi
printf '%s\n' "$inspection_status" > "$output/container-inspect.exit"
python3 -B "$draft/check.py" > "$output/host-after-check.json" 2> "$output/host-after-check.stderr"
audit_status=$?
printf '%s\n' "$audit_status" > "$output/host-after-check.exit"
final_status=$status
if [[ $inspection_status != 0 || $audit_status != 0 ]]; then final_status=1; fi
printf '%s\n' "$final_status" > "$output/launcher.exit"
exit "$final_status"
