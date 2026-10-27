#!/usr/bin/env bash
set -euo pipefail
base=/home/aaron/code/rusix
out="$base/linux-out/exit-helper-archive-check-001"
image=sha256:c02eb3929889b3f0cc035d57a02c844e0c74c71d24fbda1311249faeb8257f63
finish(){ status=$?; trap - EXIT INT TERM; if [[ -f "$out/container.cid" ]];then cid=$(cat "$out/container.cid");if [[ "$cid" =~ ^[0-9a-f]{64}$ ]];then docker rm -f "$cid" >/dev/null 2>&1 || true;fi;fi; printf '%s\n' "$status" > "$out/launcher.exit";exit "$status"; }
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
[[ ! -e "$out/container.cid" ]]
printf '%s\n' "$image" > "$out/image.txt"
timeout --kill-after=15s 120s docker run --rm --cidfile "$out/container.cid" --network none --cap-drop ALL --security-opt no-new-privileges --read-only --cpus 1 --memory 512m --memory-swap 512m --user "$(id -u):$(id -g)" --env PYTHONDONTWRITEBYTECODE=1 --mount "type=bind,src=$base/linux-mm-exit-mmap,dst=/src,readonly" --mount "type=bind,src=$base/linux-out/mm-release-verification-003/rust/builds/ci-mm-release-rust/rust,dst=/artifacts,readonly" --mount "type=bind,src=$out,dst=/check,readonly" "$image" python3 -B /check/check.py > "$out/result.json" 2> "$out/stderr.log"
[[ ! -s "$out/stderr.log" ]]
