#!/bin/bash
set -euo pipefail
out=/home/aaron/code/rusix/linux-out/task-fault-fixtures-003
image=sha256:c02eb3929889b3f0cc035d57a02c844e0c74c71d24fbda1311249faeb8257f63
cleanup() { if [[ -f "$out/container.cid" ]]; then docker rm -f "$(cat "$out/container.cid")" >/dev/null 2>&1 || true; fi; }
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
docker image inspect "$image" > "$out/image-inspect.json"
set +e
timeout --signal=TERM --kill-after=15s 5m docker run --cidfile "$out/container.cid" \
 --network none --cap-drop ALL --security-opt no-new-privileges --read-only \
 --cpus 1 --memory 1g --memory-swap 1g --pids-limit 128 --user "$(id -u):$(id -g)" \
 --mount "type=bind,src=$out/source,dst=/source,readonly" \
 --mount "type=bind,src=$out/compile.py,dst=/out/compile.py,readonly" \
 --mount "type=bind,src=$out/evidence,dst=/out/evidence" \
 --mount "type=bind,src=$out/artifacts,dst=/out/artifacts" \
 --mount "type=bind,src=$out/tmp,dst=/out/tmp" --env TMPDIR=/out/tmp \
 "$image" python3 -B /out/compile.py > "$out/container.log" 2>&1
status=$?
printf '%s\n' "$status" > "$out/container.exit"
if [[ -f "$out/container.cid" ]]; then docker inspect "$(cat "$out/container.cid")" > "$out/container-inspect.json"; fi
exit "$status"
